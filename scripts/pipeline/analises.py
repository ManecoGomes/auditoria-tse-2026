#!/usr/bin/env python3
"""Analises comparativas do plano pre-registrado (A2, C4, E, F).

Roda com o que existe: com so o 1o turno, entrega a linha de base por
municipio e a geografia; quando o 2o turno chegar, os blocos E passam a
sair automaticamente, municipio por municipio, sem editar nada aqui.
"""
import csv, glob, json, os, statistics, collections, datetime

P    = os.path.expanduser("~/Claude/Projetos/eleição")
R    = f"{P}/pipeline/resultados"
DEMO = {1: "/Volumes/SSD1TB/acervo-tse/auditoria/demo",
        2: "/Volumes/SSD1TB/acervo-tse/auditoria/demo2t"}
AGORA = datetime.datetime.now(datetime.timezone.utc).isoformat()   # 3.9 nao tem datetime.UTC

def i(v, d=0):
    try: return int(v)
    except (TypeError, ValueError): return d

def votos_secao(t):
    """{(mun,zona,sec): {numero: votos, '_comp': comparecimento}} do boletim."""
    d = {}
    for f in sorted(glob.glob(f"{R}/{t}t/votos/*.csv")):
        for r in csv.DictReader(open(f)):
            k = (i(r["municipio"]), i(r["zona"]), i(r["secao"]))
            e = d.setdefault(k, {"_comp": i(r.get("comparecimento"))})
            if r.get("tipo") == "Nominal":
                e[r["numero"]] = e.get(r["numero"], 0) + i(r.get("votos"))
    return d

def horas_secao(t):
    """{(mun,zona,sec): {...}} do CSV por secao gerado por demonstra.py.

    Le do acervo (fonte real) e tolera o esquema antigo, sem as faixas de hora.
    """
    d = {}
    alvos = sorted(glob.glob(f"{DEMO[t]}/*_secoes.csv")) + sorted(glob.glob(f"{R}/{t}t/logs/*_secoes.csv"))
    for f in alvos:
        uf = os.path.basename(f).split("_")[0]
        ok = f"/Volumes/SSD1TB/acervo-tse/2026-{t}t/originais/bu_imgbu_logjez_rdv_vscmr_2026_{t}t_{uf}.zip.ok"
        if glob.glob(f"{DEMO[t]}/*_secoes.csv") and not os.path.exists(ok):
            continue   # so entra UF com acervo provado integro
        for r in csv.DictReader(open(f)):
            k = (i(r["municipio"]), i(r["zona"]), i(r["secao"]))
            e = {"uf": r.get("uf", uf), "municipio_nome": r.get("municipio_nome", ""),
                 "votos": i(r.get("votos")), "apos17h": i(r.get("apos17h")),
                 "apos_lacre": i(r.get("apos_lacre"))}
            e["de17_a_19h"] = i(r["de17_a_19h"]) if r.get("de17_a_19h") not in (None, "") else e["apos17h"]
            e["apos_19h"]   = i(r.get("apos_19h"))
            d[k] = e
    return d

def municipios(t):
    """{(uf,cod): bloco} a partir dos JSON por municipio de cada UF."""
    out = {}
    for f in sorted(glob.glob(f"{DEMO[t]}/*_municipios.json")):
        try: j = json.load(open(f))
        except Exception: continue
        for cod, b in j.get("municipios", {}).items():
            out[(j["uf"], int(cod))] = b
    return out

OUT = {"gerado_utc": AGORA, "blocos": {}}

v1, v2 = votos_secao(1), votos_secao(2)
h1, h2 = horas_secao(1), horas_secao(2)
m1, m2 = municipios(1), municipios(2)
print(f"boletim 1T:{len(v1)} 2T:{len(v2)} | log 1T:{len(h1)} 2T:{len(h2)} | "
      f"municipios 1T:{len(m1)} 2T:{len(m2)}", flush=True)
OUT["cobertura"] = {"secoes_boletim_1t": len(v1), "secoes_boletim_2t": len(v2),
                    "secoes_log_1t": len(h1), "secoes_log_2t": len(h2),
                    "municipios_1t": len(m1), "municipios_2t": len(m2)}

# ---------- A2: triangulacao boletim x log, por turno disponivel ----------
for t, (vv, hh) in ((1, (v1, h1)), (2, (v2, h2))):
    if not (vv and hh): continue
    dif, n = [], 0
    for k, h in hh.items():
        if k not in vv: continue
        n += 1; dd = h["votos"] - vv[k]["_comp"]
        if dd: dif.append({"secao": "-".join(map(str, k)), "log": h["votos"],
                           "bu": vv[k]["_comp"], "dif": dd})
    OUT["blocos"][f"A2_triangulacao_{t}t"] = {
        "secoes_comparadas": n, "divergentes": len(dif),
        "pct": round(100*len(dif)/n, 4) if n else None,
        "log_menor_que_bu": sum(1 for e in dif if e["dif"] < 0),
        "log_maior_que_bu": sum(1 for e in dif if e["dif"] > 0),
        "exemplos": dif[:50]}
    print(f"A2 {t}T: {len(dif)}/{n} seções com divergência log x boletim", flush=True)

# ---------- F1: geografia do voto tardio, por municipio ----------
for t, hh in ((1, h1), (2, h2)):
    if not hh: continue
    mun = collections.defaultdict(lambda: [0, 0, 0, ""])
    for k, h in hh.items():
        a = mun[(h["uf"], k[0])]
        a[0] += h["de17_a_19h"] + h["apos_19h"]; a[1] += h["votos"]; a[2] += 1
        if h.get("municipio_nome"): a[3] = h["municipio_nome"]
    pct = [{"uf": u, "municipio": c, "nome": a[3], "secoes": a[2], "votos": a[1],
            "pct_tardio": round(100*a[0]/a[1], 3)}
           for (u, c), a in mun.items() if a[1] > 500]
    pct.sort(key=lambda x: -x["pct_tardio"])
    OUT["blocos"][f"F1_geografia_{t}t"] = {
        "municipios": len(pct),
        "mediana_pct_tardio": round(statistics.median([p["pct_tardio"] for p in pct]), 3) if pct else None,
        "top20_mais_tardio": pct[:20], "top20_menos_tardio": pct[-20:][::-1]}
    print(f"F1 {t}T: {len(pct)} municípios com mais de 500 votos", flush=True)

# ---------- E: comparacao entre turnos (ativa quando o 2T existir) ----------
if v1 and v2:
    comuns = set(v1) & set(v2)
    comp = [(v2[k]["_comp"], v1[k]["_comp"]) for k in comuns if v1[k]["_comp"]]
    OUT["blocos"]["E1_comparecimento"] = {
        "secoes_comuns": len(comuns),
        "variacao_mediana_pct": round(statistics.median([100*(a-b)/b for a, b in comp]), 3) if comp else None}
    print(f"E1: {len(comuns)} seções comuns aos dois turnos", flush=True)

# ---------- E5: municipio por municipio, 1T contra 2T ----------
if m1 and m2:
    linhas = []
    for key in sorted(set(m1) & set(m2)):
        b1, b2 = m1[key], m2[key]
        t1, t2 = b1["votos_presidente"], b2["votos_presidente"]
        linhas.append({
            "uf": key[0], "municipio": key[1], "nome": b2.get("nome") or b1.get("nome"),
            "secoes_1t": b1["secoes"], "secoes_2t": b2["secoes"],
            "votos_1t": t1, "votos_2t": t2,
            "var_votos_pct": round(100*(t2-t1)/t1, 3) if t1 else None,
            "pct_apos17h_1t": b1["C2_pct"], "pct_apos17h_2t": b2["C2_pct"],
            "apos_lacre_1t": b1["C1_secoes_com_voto_apos_lacre"],
            "apos_lacre_2t": b2["C1_secoes_com_voto_apos_lacre"],
            "abaixo20s_1t": b1["C4_intervalos"]["abaixo_de_20s"],
            "abaixo20s_2t": b2["C4_intervalos"]["abaixo_de_20s"],
            "mediana_s_1t": b1["C4_intervalos"]["mediana_s"],
            "mediana_s_2t": b2["C4_intervalos"]["mediana_s"],
            "a2_divergentes_1t": b1["A2_triangulacao"]["divergentes"],
            "a2_divergentes_2t": b2["A2_triangulacao"]["divergentes"]})
    with open(f"{P}/pipeline/E5_municipios_1t_2t.csv", "w", newline="") as f:
        if linhas:
            w = csv.DictWriter(f, fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)
    piora = [l for l in linhas if l["apos_lacre_2t"] > l["apos_lacre_1t"]
             or l["abaixo20s_2t"] > l["abaixo20s_1t"]]
    OUT["blocos"]["E5_municipios"] = {
        "municipios_comuns": len(linhas),
        "com_indicador_pior_no_2t": len(piora),
        "exemplos_piora": piora[:50],
        "csv": "E5_municipios_1t_2t.csv"}
    print(f"E5: {len(linhas)} municípios comuns, {len(piora)} com indicador pior no 2T", flush=True)
else:
    OUT["blocos"]["E5_municipios"] = {
        "estado": "aguardando o 2º turno",
        "municipios_1t_prontos": len(m1),
        "nota": ("A linha de base por município do 1º turno está pronta. Os blocos E "
                 "comparam os mesmos municípios entre turnos e saem sozinhos quando o "
                 "TSE publicar os arquivos do 2º turno.")}

json.dump(OUT, open(f"{P}/pipeline/analises.json", "w"), indent=1, ensure_ascii=False)
print("ANALISES_CONCLUIDAS:", json.dumps({k: (v.get("municipios") or v.get("secoes_comparadas")
      or v.get("municipios_comuns") or v.get("estado")) for k, v in OUT["blocos"].items()},
      ensure_ascii=False))
