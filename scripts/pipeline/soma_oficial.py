#!/usr/bin/env python3
"""A3 — soma dos boletins de secao contra a totalizacao oficial do TSE, nos dois turnos.
Fontes oficiais (acervo /Volumes/SSD1TB/acervo-tse/oficial, SHA-512 em SHA512SUMS):
  votacao_candidato_munzona_2026.zip  (dataset resultados-2026; cada linha aparece 2x, com CD_SIT_TOT_TURNO
                                       distinto — deduplica-se por turno/UF/municipio/zona/candidato)
  Relatorio_Resultado_Totalizacao_2026_BR.zip (PDFs do SISTOT: totais de comparecimento, validos, brancos, nulos)
Boletins: bweb_{t}t_{UF}_*.zip (hash SHA-512 conferido com o .sha512 do TSE), cargo Presidente.
Saida: pipeline/resultados/a3_soma_oficial.json"""
import csv, io, json, zipfile, glob, collections, os, re, subprocess, datetime
P = os.path.expanduser("~/Claude/Projetos/eleição"); OF = "/Volumes/SSD1TB/acervo-tse/oficial"
NOMES = {"13": "LULA (PT)", "22": "FLAVIO BOLSONARO (PL)", "95": "Branco", "96": "Nulo"}

def boletins(t):
    tot = collections.Counter(); comp = aptos = 0; secs = set(); por_uf = collections.defaultdict(collections.Counter)
    for z in sorted(glob.glob(f"/Volumes/SSD1TB/acervo-tse/2026-{t}t/boletins/bweb_{t}t_*.zip")):
        uf = z.split(f"_{t}t_")[1][:2]
        zf = zipfile.ZipFile(z); n = [x for x in zf.namelist() if x.lower().endswith(".csv")][0]
        with zf.open(n) as raw:
            for r in csv.DictReader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";"):
                if r["CD_CARGO_PERGUNTA"] != "1": continue
                k = (uf, r["CD_MUNICIPIO"], r["NR_ZONA"], r["NR_SECAO"])
                if k not in secs:
                    secs.add(k); comp += int(r["QT_COMPARECIMENTO"] or 0); aptos += int(r["QT_APTOS"] or 0)
                v = int(r["QT_VOTOS"] or 0); tot[r["NR_VOTAVEL"]] += v; por_uf[uf][r["NR_VOTAVEL"]] += v
    return {"secoes": len(secs), "comparecimento": comp, "aptos": aptos, "por_votavel": dict(tot),
            "por_uf": {u: dict(c) for u, c in por_uf.items()}}

def oficial_munzona():
    z = zipfile.ZipFile(f"{OF}/votacao_candidato_munzona_2026.zip")
    chaves = {}; nomes = {}
    for n in z.namelist():
        if not n.endswith(".csv"): continue
        with z.open(n) as raw:
            for r in csv.DictReader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";"):
                if r["CD_CARGO"] != "1": continue
                k = (r["NR_TURNO"], r["SG_UF"], r["CD_MUNICIPIO"], r["NR_ZONA"], r["NR_CANDIDATO"])
                chaves[k] = int(r["QT_VOTOS_NOMINAIS"] or 0)  # linhas repetidas trazem o mesmo valor
                nomes[r["NR_CANDIDATO"]] = f"{r['NM_URNA_CANDIDATO']} ({r['SG_PARTIDO']})"
    tot = {"1": collections.Counter(), "2": collections.Counter()}; por_uf = {"1": collections.defaultdict(collections.Counter), "2": collections.defaultdict(collections.Counter)}
    for (t, uf, m, zn, c), v in chaves.items(): tot[t][c] += v; por_uf[t][uf][c] += v
    return {t: {"por_candidato": dict(tot[t]), "por_uf": {u: dict(c) for u, c in por_uf[t].items()}} for t in tot}, nomes

def oficial_pdf(t):
    cd = {"1": "6257", "2": "6258"}[t]
    z = zipfile.ZipFile(f"{OF}/Relatorio_Resultado_Totalizacao_2026_BR.zip")
    pdf = [n for n in z.namelist() if n.startswith(cd)][0]
    txt = subprocess.run(["pdftotext", "-layout", "-", "-"], input=z.read(pdf), capture_output=True).stdout.decode("utf-8", "replace")
    def num(rot):
        m = re.search(rot + r"[^\n]*?([\d.]+)\s*$", txt, re.M)
        return int(m.group(1).replace(".", "")) if m else None
    return {"arquivo": pdf, "comparecimento": num(r"2\.3 Comparecimento"), "validos": num(r"Votos v\xe1lidos"),
            "nulos": num(r"b\) Votos nulos"), "nulos_urna": num(r"Votos nulos na urna"), "nulos_tecnico": num(r"Votos nulos t\xe9cnico"),
            "brancos": num(r"c\) Votos em branco"), "secoes_urna": num(r"2\.1\.1 Se\xe7\xf5es apuradas em urnas"),
            "secoes_sa": num(r"2\.1\.2 Se\xe7\xf5es apuradas pelo Sistema"), "aptos": num(r"2\.2\.2\.1 Aptos nas se\xe7\xf5es apuradas")}

def main():
    mz, nomes = oficial_munzona(); res = {"gerado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "turnos": {}}
    for t in ("1", "2"):
        bu = boletins(t); pdf = oficial_pdf(t); of = mz[t]
        cands = sorted(set(of["por_candidato"]) | {c for c in bu["por_votavel"] if c not in ("95", "96")}, key=lambda c: -of["por_candidato"].get(c, 0))
        linhas = []
        for c in cands:
            a = bu["por_votavel"].get(c, 0); b = of["por_candidato"].get(c, 0)
            linhas.append({"numero": c, "nome": nomes.get(c, NOMES.get(c, c)), "boletins": a, "oficial": b, "diferenca": a - b})
        validos_bu = sum(v for c, v in bu["por_votavel"].items() if c not in ("95", "96"))
        ufs = []
        for uf in sorted(bu["por_uf"]):
            r = {"uf": uf}
            for c in ("13", "22"):
                r[c] = {"boletins": bu["por_uf"][uf].get(c, 0), "oficial": of["por_uf"].get(uf, {}).get(c, 0)}
                r[c]["diferenca"] = r[c]["boletins"] - r[c]["oficial"]
            ufs.append(r)
        res["turnos"][t] = {"boletins": {"secoes": bu["secoes"], "comparecimento": bu["comparecimento"], "aptos": bu["aptos"],
                                         "validos_nominais": validos_bu, "brancos": bu["por_votavel"].get("95", 0), "nulos": bu["por_votavel"].get("96", 0)},
                            "oficial_pdf": pdf, "candidatos": linhas, "por_uf": ufs,
                            "confere": {"comparecimento": bu["comparecimento"] == pdf["comparecimento"],
                                        "brancos": bu["por_votavel"].get("95", 0) == pdf["brancos"],
                                        "nulos_na_urna": bu["por_votavel"].get("96", 0) == pdf["nulos_urna"],
                                        "candidatos_todos_iguais": all(l["diferenca"] == 0 for l in linhas),
                                        "validos_oficial_menos_boletins": (pdf["validos"] or 0) - validos_bu,
                                        "nota": "validos oficiais = nominais dos boletins menos os 'nulos tecnicos' (votos a candidatura indeferida, anulados na totalizacao)"}}
        vt = pdf["validos"] or 1
        for l in linhas: l["pct_validos_oficial"] = round(100 * l["oficial"] / vt, 2)
    json.dump(res, open(f"{P}/pipeline/resultados/a3_soma_oficial.json", "w"), ensure_ascii=False, indent=1)
    for t, r in res["turnos"].items():
        print(f"{t}T: boletins comp={r['boletins']['comparecimento']:,} oficial={r['oficial_pdf']['comparecimento']:,} | confere={r['confere']}")
        for l in r["candidatos"][:3]: print("   ", l["numero"], l["nome"], l["boletins"], l["oficial"], l["diferenca"], l["pct_validos_oficial"])
if __name__ == "__main__": main()
