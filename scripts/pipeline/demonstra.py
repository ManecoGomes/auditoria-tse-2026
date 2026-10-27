#!/usr/bin/env python3
"""Bateria do plano sobre os logs do 1o turno, POR UNIDADE DA FEDERACAO.

Cada UF e processada uma vez e cacheada em resultados/1t/demo/{UF}.json.
O bloco nacional e a soma dos per-UF. Rodar de novo so reprocessa UF nova
ou UF cujo ZIP mudou de tamanho — publicacao incremental de verdade.
"""
import csv, glob, io, json, os, re, zipfile, collections, datetime, signal, sys, time

# Watchdog: o volume externo ja deixou este processo pendurado com 0,03 s de CPU por
# mais de uma hora (2026-10-27, 00h e 08h). Se qualquer passo travar, o processo
# morre sozinho — exit 4 — em vez de segurar o publicador e o lock para sempre.
def _watchdog(sig, frm):
    print("ERRO: watchdog — processo travado por 3h, abortando (exit 4)", flush=True)
    os._exit(4)
signal.signal(signal.SIGALRM, _watchdog)
signal.alarm(3*3600)

P   = os.path.expanduser("~/Claude/Projetos/eleição")
# turno: argv[1] (1 ou 2). O 2o turno grava em demo2t/ e demonstracao_2t.json; o 1o
# mantem os nomes historicos. DEMONSTRA_ACERVO/DEMONSTRA_UFS existem so para ensaio.
T   = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("1", "2") else "1"
ACV = os.environ.get("DEMONSTRA_ACERVO") or f"/Volumes/SSD1TB/acervo-tse/2026-{T}t"
AC  = f"{ACV}/originais"
BOL = f"{ACV}/boletins"
DEMO= "/Volumes/SSD1TB/acervo-tse/auditoria/demo" + ("2t" if T == "2" else "")  # fora do Google Drive: ele truncava os CSV
PRAZO = 17 if T == "1" else 19     # prazo legal do turno (19h no 2T por decisao de 25/10/2026)
SAIDA_JSON = f"{P}/pipeline/demonstracao_{T}t.json"
SAIDA_CSV  = f"{P}/pipeline/demonstracao_secoes" + ("_2t" if T == "2" else "") + ".csv"
SO_UFS = set(filter(None, os.environ.get("DEMONSTRA_UFS", "").split(",")))
os.makedirs(DEMO, exist_ok=True)

# deslocamento para hora de Brasilia
VERSAO = 9   # bump invalida o cache quando o esquema muda (9: corte em 17h, votos discrepantes, 2026-10-27)

OFF = {"AC":2, "AM":1, "MT":1, "MS":1, "RO":1, "RR":1}

NOME = {"AC":"Acre","AL":"Alagoas","AM":"Amazonas","AP":"Amapá","BA":"Bahia",
 "CE":"Ceará","DF":"Distrito Federal","ES":"Espírito Santo","GO":"Goiás",
 "MA":"Maranhão","MG":"Minas Gerais","MS":"Mato Grosso do Sul","MT":"Mato Grosso",
 "PA":"Pará","PB":"Paraíba","PE":"Pernambuco","PI":"Piauí","PR":"Paraná",
 "RJ":"Rio de Janeiro","RN":"Rio Grande do Norte","RO":"Rondônia","RR":"Roraima",
 "RS":"Rio Grande do Sul","SC":"Santa Catarina","SE":"Sergipe","SP":"São Paulo",
 "TO":"Tocantins","ZZ":"Exterior"}

URNA = re.compile(rb"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}\t\w+\t(\d+)\t", re.M)
VOTO = re.compile(rb"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\t.*Voto confirmado para \[Presidente\]", re.M)
BUG  = re.compile(rb"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\t.*Gerando arquivo de resultado \[bu\.dat\] \+ \[In", re.M)
HAB  = re.compile(rb"Eleitor foi habilitado")
COMP = re.compile(rb"O voto do eleitor foi computado")
CONT = b"Urna de conting"   # urna reserva: preparada, jamais usada

def Pt(b): return datetime.datetime.strptime(b.decode(), "%d/%m/%Y %H:%M:%S")

# C4b — janelas horarias da reta final (acrescentado em 2026-10-27, ANTES da publicacao
# dos arquivos do 2o turno; emenda datada ao plano, nao teste pre-registrado).
# A mesma regua nos dois turnos, para a secao ser controle de si mesma (decisao do Maneco, 27/10):
#   antes : voto ate 16h59m59s — o dia normal, ate o prazo legal do 1o turno (17h)
#           a1630 : subfaixa informativa, a ultima meia hora antes das 17h
#   final : voto de 17h em diante — no 2o turno, as DUAS HORAS A MAIS da prorrogacao (ate 19h) e o
#           que passou das 19h; no 1o turno, so a fila remanescente
#   f17 / f18 / f19 / f1930 : subfaixas — 17h-17h59, 18h-18h59, 19h-19h29, 19h30 em diante
JAN = ("antes", "a1630", "final", "f17", "f18", "f19", "f1930")
# voto DISCREPANTE: intervalo abaixo de FRAC da mediana da PROPRIA secao antes das 17h
# (a regua e o dia normal daquela urna). Sem mediana (secao sem votos antes), usa o piso de 20 s.
FRAC_DISC = 0.25
INICIO_FINAL = 17*60
INICIO_SERIE = 16*60+30     # a serie de 10 min comeca meia hora antes, para mostrar a rampa
def janelas(t):
    hm = t.hour*60 + t.minute
    if hm < INICIO_FINAL: return ("antes", "a1630") if hm >= 16*60+30 else ("antes",)
    sub = ("f17" if hm < 18*60 else "f18" if hm < 19*60 else "f19" if hm < 19*60+30 else "f1930")
    return ("final", sub)
def bin10(t):
    """Rotulo HH:MM do bloco de 10 min (so para a serie da reta final)."""
    return f"{t.hour:02d}:{(t.minute//10)*10:02d}"

def resumo_janela(cnt, votos_n):
    """Estatisticas de um Counter intervalo->frequencia (0..600 s) de uma janela."""
    n = sum(cnt.values())
    if not n:
        return {"votos": votos_n, "intervalos": 0, "media_s": None, "mediana_s": None,
                "abaixo_de_20s": 0, "pct_abaixo_20s": None, "media_ate_120s": None}
    soma = sum(k*v for k, v in cnt.items())
    r20 = sum(v for k, v in cnt.items() if k < 20)
    n120 = sum(v for k, v in cnt.items() if k <= 120)
    s120 = sum(k*v for k, v in cnt.items() if k <= 120)
    return {"votos": votos_n, "intervalos": n, "media_s": round(soma/n, 2),
            "mediana_s": mediana_ponderada(cnt), "abaixo_de_20s": r20,
            "pct_abaixo_20s": round(100*r20/n, 4),
            "media_ate_120s": round(s120/n120, 2) if n120 else None}

def mediana_ponderada(cnt):
    """Mediana de um Counter valor->frequencia, sem materializar os elementos."""
    tot = sum(cnt.values())
    if not tot: return None
    alvo = [(tot+1)//2] if tot % 2 else [tot//2, tot//2+1]
    vals, i, acc = [], 0, 0
    for k in sorted(cnt):
        acc += cnt[k]
        while i < len(alvo) and alvo[i] <= acc:
            vals.append(k); i += 1
        if i >= len(alvo): break
    return sum(vals)/len(vals)

def zips_integros():
    """UFs com sidecar .ok valido — criterio UNICO, o mesmo do downloader.

    O sidecar <zip>.ok guarda o tamanho em bytes no instante em que
    zipfile.testzip() passou. Exigi-lo elimina a corrida que fazia esta
    funcao ler um ZIP ainda em download e declarar a UF corrompida.
    """
    out = []
    for z in sorted(glob.glob(f"{AC}/*_[12]t_*.zip")):
        m = re.search(r"_[12]t_([A-Z]{2})\.zip", z)
        if not m: continue
        uf, ok = m.group(1), z + ".ok"
        if SO_UFS and uf not in SO_UFS: continue
        if not os.path.exists(ok):
            print(f"  {uf}: sem sidecar .ok (em download ou nao verificado) — ignorado", flush=True); continue
        try:
            if open(ok).read().strip() != str(os.path.getsize(z)):
                print(f"  {uf}: sidecar .ok desatualizado (ZIP mudou de tamanho) — ignorado", flush=True); continue
        except Exception:
            print(f"  {uf}: sidecar .ok ilegivel — ignorado", flush=True); continue
        out.append((uf, z))
    return out

def comparecimento_do_bu(uf):
    """A2: comparecimento por secao, do boletim ja extraido."""
    f = f"{P}/pipeline/resultados/{T}t/votos/{uf}.csv"
    d = {}
    if os.path.exists(f):
        for r in csv.DictReader(open(f)):
            d[(int(r["municipio"]), int(r["zona"]), int(r["secao"]))] = int(r["comparecimento"] or 0)
    return d

def urna_do_bu(uf):
    """A4: NR_URNA_EFETIVADA por secao, direto do bweb."""
    d = {}
    zb = glob.glob(f"{BOL}/bweb_[12]t_{uf}_*.zip")
    if not zb: return d
    try:
        with zipfile.ZipFile(zb[0]) as zf:
            nm = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
            with zf.open(nm) as raw:
                for r in csv.DictReader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";"):
                    if r.get("CD_CARGO_PERGUNTA") != "1": continue
                    k = (int(r["CD_MUNICIPIO"]), int(r["NR_ZONA"]), int(r["NR_SECAO"]))
                    if k not in d: d[k] = r["NR_URNA_EFETIVADA"].lstrip("0")
    except Exception as e:
        print(f"  {uf}: bweb ilegivel ({e})", flush=True)
    return d

def nomes_municipios(uf):
    """{CD_MUNICIPIO: NM_MUNICIPIO} do boletim — o TSE so publica o codigo no log."""
    d = {}
    zb = glob.glob(f"{BOL}/bweb_[12]t_{uf}_*.zip")
    if not zb: return d
    try:
        with zipfile.ZipFile(zb[0]) as zf:
            nm = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
            with zf.open(nm) as raw:
                for r in csv.DictReader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";"):
                    c = r.get("CD_MUNICIPIO")
                    if c and c.isdigit() and int(c) not in d:
                        d[int(c)] = (r.get("NM_MUNICIPIO") or "").strip().title()
    except Exception as e:
        print(f"  {uf}: nomes de municipio indisponiveis ({e})", flush=True)
    return d


def acc_novo():
    """Acumulador de um escopo (UF ou municipio)."""
    return {"permin": collections.Counter(), "inter": collections.Counter(),
            "ultimo": collections.Counter(), "urnas": set(),
            "nsec": 0, "tv": 0, "th": 0, "tc": 0, "apos17": 0, "a17_19": 0,
            "apos19": 0, "aposlacre": 0, "comp_a2": 0, "comp_a4": 0,
            "dif_voto": [], "dif_urna": [], "a2_menor": 0, "a2_maior": 0,
            "a2_dmin": 0, "a2_dmax": 0, "ex_ok": None,
            "jan": {j: collections.Counter() for j in JAN},
            "jan_votos": collections.Counter(), "reta_rapida": 0, "reta_com_10": 0,
            "s10": collections.defaultdict(lambda: [0, 0, 0, 0]),  # bin -> [intervalos, soma_s, <20s, votos]
            "disc": collections.Counter()}   # discrepantes: antes / final / f1630... (intervalos abaixo do limiar da secao)


def fecha_c4b(a, dist=False):
    jan = {j: resumo_janela(a["jan"][j], a["jan_votos"][j]) for j in JAN}
    ma, mr = jan["antes"]["media_s"], jan["final"]["media_s"]
    for j in JAN:
        jan[j]["discrepantes"] = a["disc"][j]
        jan[j]["pct_discrepantes"] = round(100*a["disc"][j]/jan[j]["intervalos"], 4) if jan[j]["intervalos"] else None
    out = {"inicio_final": "17:00", "janelas": jan,
           "limiar_discrepante": f"intervalo abaixo de {int(FRAC_DISC*100)}% da mediana da própria seção antes das 17h (ou de 20 s, se a seção não tem base)",
           "votos_discrepantes_final": a["disc"]["final"],
           "aceleracao": round(ma/mr, 3) if (ma and mr) else None,
           "secoes_final_com_10_votos": a["reta_com_10"],
           "secoes_final_rapida": a["reta_rapida"]}
    if dist:
        out["distribuicao"] = {j: {str(k): v for k, v in sorted(a["jan"][j].items())}
                               for j in ("antes", "final")}
        out["serie_10min"] = {b: {"intervalos": v[0], "media_s": round(v[1]/v[0], 2) if v[0] else None,
                                  "abaixo_de_20s": v[2], "votos": v[3]}
                              for b, v in sorted(a["s10"].items())}
    return out


def acc_fecha(a, uf, nome, dist=False):
    """Mesmas formulas do bloco nacional, aplicadas a um escopo qualquer."""
    rap = sum(q for s_, q in a["inter"].items() if s_ < 20)
    tot_int = sum(a["inter"].values()); tv = a["tv"]
    return {
      "uf": uf, "nome": nome,
      "secoes": a["nsec"], "votos_presidente": tv,
      "habilitacoes": a["th"], "computados": a["tc"],
      "C1_secoes_com_voto_apos_lacre": a["aposlacre"],
      "C2_votos_apos_17h": a["apos17"],
      "C2_pct": round(100*a["apos17"]/tv, 4) if tv else 0,
      "C2_de17_a_19h": a["a17_19"], "C2_apos_19h": a["apos19"],
      "C3_curva_por_minuto": dict(sorted(a["permin"].items())),
      "C4_intervalos": {"amostra": tot_int, "mediana_s": mediana_ponderada(a["inter"]),
                        "abaixo_de_20s": rap,
                        "pct_abaixo_20s": round(100*rap/tot_int, 4) if tot_int else 0,
                        "distribuicao": {str(k): v for k, v in sorted(a["inter"].items())}},
      "C4b_reta_final": fecha_c4b(a, dist),
      "B4_ultimo_voto_por_hora": dict(sorted(a["ultimo"].items())),
      "C6_hab_menos_comput": a["th"]-a["tc"],
      "A2_triangulacao": {"secoes_comparadas": a["comp_a2"], "divergentes": len(a["dif_voto"]),
                          "pct": round(100*len(a["dif_voto"])/a["comp_a2"], 4) if a["comp_a2"] else None,
                          "log_menor_que_bu": a["a2_menor"], "log_maior_que_bu": a["a2_maior"],
                          "delta_min": a["a2_dmin"], "delta_max": a["a2_dmax"],
                          "exemplos": a["dif_voto"][:30]},
      "A4_identidade_da_urna": {"secoes_comparadas": a["comp_a4"], "divergentes": len(a["dif_urna"]),
                                "contingencia_sem_voto": sum(1 for e in a["dif_urna"] if e["contingencia"]),
                                "sem_explicacao": sum(1 for e in a["dif_urna"] if not e["contingencia"]),
                                "exemplos": a["dif_urna"][:30], "exemplo_conferido": a["ex_ok"]},
      "urnas_distintas": len(a["urnas"]),
    }


def processa(uf, z):
    """Processa uma UF, acumulando em paralelo o escopo da UF e de cada municipio."""
    off = datetime.timedelta(hours=OFF.get(uf, 0))
    UFA = acc_novo()
    MUN = collections.defaultdict(acc_novo)
    bu   = comparecimento_do_bu(uf)
    ubu  = urna_do_bu(uf)
    nomes = nomes_municipios(uf)
    linhas_csv = 0
    csvp = f"{DEMO}/{uf}_secoes.csv"
    OZ = zipfile.ZipFile(z)
    nomes_log = [n for n in OZ.namelist() if n.endswith("-log.jez")]
    with open(csvp, "w", newline="") as fcsv:
        w = csv.writer(fcsv)
        w.writerow(["uf","municipio","municipio_nome","zona","secao","urna_serie","votos",
                    "apos17h","de17_a_19h","apos_19h","apos_lacre","ultimo_voto",
                    "votos_ate_17h","votos_17h_em_diante","media_s_antes","media_s_final",
                    "mediana_s_final","abaixo_20s_final","mediana_s_antes","limiar_discrepante_s",
                    "discrepantes_antes","discrepantes_final"])
        for i, nome in enumerate(nomes_log):
            try:
                with zipfile.ZipFile(io.BytesIO(OZ.read(nome))) as inn:
                    d = inn.read("logd.dat")
            except Exception:
                continue
            r = nome.split("-")[0][8:]
            try: key = (int(r[0:5]), int(r[5:9]), int(r[9:]))
            except Exception: key = None
            # escopos que recebem esta secao: a UF sempre, o municipio quando identificavel
            escopos = [UFA] + ([MUN[key[0]]] if key else [])
            for a in escopos: a["nsec"] += 1
            mu = URNA.search(d)
            serie = mu.group(1).decode().lstrip("0") if mu else ""
            if serie:
                for a in escopos: a["urnas"].add(serie)
            votos = sorted(Pt(m.group(1)) + off for m in VOTO.finditer(d))
            nh, nc = len(HAB.findall(d)), len(COMP.findall(d))
            for a in escopos:
                a["th"] += nh; a["tc"] += nc; a["tv"] += len(votos)
            # A4 vale mesmo sem voto
            if key and key in ubu and serie and ubu[key]:
                cont = bool(CONT in d and not votos)
                for a in escopos:
                    a["comp_a4"] += 1
                    if a["ex_ok"] is None and serie == ubu[key] and votos:
                        a["ex_ok"] = {"secao": f"{key[0]}/{key[1]}/{key[2]}", "urna_log": serie,
                                      "urna_bu": ubu[key], "votos": len(votos)}
                    if serie != ubu[key]:
                        a["dif_urna"].append({"secao":f"{key[0]}-{key[1]}-{key[2]}","urna_log":serie,
                                              "urna_bu":ubu[key],"contingencia":cont})
            if not votos:
                continue
            for t in votos:
                k = t.strftime("%H:%M")
                for a in escopos: a["permin"][k] += 1
            hu = max(votos).strftime("%H")+"h"
            for a in escopos: a["ultimo"][hu] += 1
            sj = {"antes": collections.Counter(), "final": collections.Counter()}
            for x, y in zip(votos, votos[1:]):
                sg = int((y-x).total_seconds())
                if 0 <= sg <= 600:
                    js = janelas(y)
                    sj[js[0]][sg] += 1
                    for a in escopos:
                        a["inter"][sg] += 1
                        for j in js: a["jan"][j][sg] += 1
                    if y.hour*60 + y.minute >= INICIO_SERIE:
                        b = bin10(y)
                        for a in escopos:
                            e = a["s10"][b]; e[0] += 1; e[1] += sg
                            if sg < 20: e[2] += 1
            sv = collections.Counter()
            for t in votos:
                js = janelas(t)
                for j in js: sv[j] += 1
                if t.hour*60 + t.minute >= INICIO_SERIE:
                    for a in escopos: a["s10"][bin10(t)][3] += 1
            for a in escopos:
                for j, q in sv.items(): a["jan_votos"][j] += q
            ra, rr = resumo_janela(sj["antes"], sv["antes"]), resumo_janela(sj["final"], sv["final"])
            med_a = ra["mediana_s"]
            limiar = max(FRAC_DISC*med_a, 0) if med_a else 20
            dsec = collections.Counter()
            for x, y in zip(votos, votos[1:]):
                sg = int((y-x).total_seconds())
                if 0 <= sg < limiar and sg <= 600:
                    for j in janelas(y): dsec[j] += 1
            for a in escopos:
                for j, q in dsec.items(): a["disc"][j] += q
            if sv["final"] >= 10:
                for a in escopos:
                    a["reta_com_10"] += 1
                    if rr["mediana_s"] is not None and rr["mediana_s"] < 20: a["reta_rapida"] += 1
            apl = 0
            g = BUG.search(d)
            if g:
                tbu = Pt(g.group(1)) + off
                if any(t > tbu for t in votos):
                    apl = 1
                    for a in escopos: a["aposlacre"] += 1
            a17 = sum(1 for t in votos if t.hour >= 17)
            a1719 = sum(1 for t in votos if 17 <= t.hour < 19)
            a19 = sum(1 for t in votos if t.hour >= 19)
            for a in escopos:
                a["apos17"] += a17; a["a17_19"] += a1719; a["apos19"] += a19
            if key:
                w.writerow([uf, key[0], nomes.get(key[0], ""), key[1], key[2], serie, len(votos),
                            a17, a1719, a19, apl, max(votos).isoformat(),
                            sv["antes"], sv["final"], ra["media_s"], rr["media_s"],
                            rr["mediana_s"], rr["abaixo_de_20s"], med_a, round(limiar, 1),
                            dsec["antes"], dsec["final"]])
                linhas_csv += 1
                if key in bu:
                    for a in escopos:
                        a["comp_a2"] += 1
                        if len(votos) != bu[key]:
                            delta = len(votos) - bu[key]
                            if delta < 0: a["a2_menor"] += 1
                            else:         a["a2_maior"] += 1
                            a["a2_dmin"] = min(a["a2_dmin"], delta)
                            a["a2_dmax"] = max(a["a2_dmax"], delta)
                            a["dif_voto"].append({"secao":f"{key[0]}-{key[1]}-{key[2]}",
                                                  "log":len(votos),"bu":bu[key],"delta":delta})
            if (i+1) % 5000 == 0: print(f"    {uf} {i+1}/{len(nomes_log)}", flush=True)
    OZ.close()

    # ---- municipios: bloco completo por municipio, em arquivo proprio da UF ----
    porm = {}
    for cod, a in MUN.items():
        b = acc_fecha(a, uf, nomes.get(cod) or f"Município {cod}")
        b["municipio"] = cod
        porm[str(cod)] = b
    json.dump({"uf": uf, "nome": NOME.get(uf, uf), "_versao": VERSAO, "turno": int(T),
               "gerado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "municipios": porm},
              open(f"{DEMO}/{uf}_municipios.json", "w"), ensure_ascii=False)

    out = acc_fecha(UFA, uf, NOME.get(uf, uf), dist=True)
    out["_zip_bytes"] = os.path.getsize(z)
    out["gerado_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out["_csv_linhas"] = linhas_csv
    out["_versao"] = VERSAO
    # resumo compacto por municipio (sem curva nem distribuicao) para as tabelas
    out["municipios_resumo"] = sorted(
        ({"municipio": b["municipio"], "nome": b["nome"], "secoes": b["secoes"],
          "votos": b["votos_presidente"],
          "mediana_s": b["C4_intervalos"]["mediana_s"],
          "abaixo_20s": b["C4_intervalos"]["abaixo_de_20s"],
          "apos_lacre": b["C1_secoes_com_voto_apos_lacre"],
          "contingencia": b["A4_identidade_da_urna"]["contingencia_sem_voto"],
          "urna_sem_explicacao": b["A4_identidade_da_urna"]["sem_explicacao"],
          "a2_divergentes": b["A2_triangulacao"]["divergentes"],
          "apos17h": b["C2_votos_apos_17h"], "pct_apos17h": b["C2_pct"],
          "votos_final": b["C4b_reta_final"]["janelas"]["final"]["votos"],
          "media_antes": b["C4b_reta_final"]["janelas"]["antes"]["media_s"],
          "atend_antes": b["C4b_reta_final"]["janelas"]["antes"]["media_ate_120s"],
          "media_final": b["C4b_reta_final"]["janelas"]["final"]["media_s"],
          "atend_final": b["C4b_reta_final"]["janelas"]["final"]["media_ate_120s"],
          "mediana_final": b["C4b_reta_final"]["janelas"]["final"]["mediana_s"],
          "abaixo20_final": b["C4b_reta_final"]["janelas"]["final"]["abaixo_de_20s"],
          "final_rapida": b["C4b_reta_final"]["secoes_final_rapida"],
          "disc_antes": b["C4b_reta_final"]["janelas"]["antes"]["discrepantes"],
          "disc_final": b["C4b_reta_final"]["janelas"]["final"]["discrepantes"]}
         for b in porm.values()), key=lambda x: x["nome"])
    out["municipios"] = len(porm)
    return out


# ---------- 1. processa cada UF, reaproveitando cache ----------
def acervo_visivel():
    try: return os.path.isdir(AC) and bool(glob.glob(f"{AC}/*_[12]t_*.zip"))
    except OSError: return False

# O volume externo tem estalos transitorios (3 ocorrencias em 2026-10-27). Tentar
# 6x com 10 s de intervalo transforma um estalo em nao-evento; so depois e erro.
for _t in range(6):
    if acervo_visivel(): break
    print(f"  acervo nao visivel em {AC} — tentativa {_t+1}/6, aguardando 10 s", flush=True)
    time.sleep(10)
else:
    # acervo indisponivel de verdade (volume desmontado): sair com erro impede a
    # cadeia de publicacao de ir ao ar com nada.
    print(f"ERRO: acervo inacessivel em {AC} apos 60 s — abortando sem tocar na publicacao", flush=True)
    raise SystemExit(2)

UFS = zips_integros()
print("UFs com ZIP utilizavel:", [u for u, _ in UFS], flush=True)
dados = {}
for uf, z in UFS:
    cache = f"{DEMO}/{uf}.json"
    if os.path.exists(cache):
        try:
            c = json.load(open(cache))
            if c.get("_zip_bytes") == os.path.getsize(z) and c.get("_versao") == VERSAO:
                dados[uf] = c; print(f"  {uf}: cache reaproveitado ({c['secoes']} seções)", flush=True); continue
        except Exception: pass
    print(f"  {uf}: processando…", flush=True)
    try:
        d = processa(uf, z)
    except Exception as e:
        print(f"  {uf}: FALHOU ({type(e).__name__}: {e}) — seguindo", flush=True); continue
    json.dump(d, open(cache, "w"), ensure_ascii=False)
    dados[uf] = d
    print(f"  {uf}: {d['secoes']} seções | {d['votos_presidente']} votos | "
          f"A2 {d['A2_triangulacao']['divergentes']} dif | A4 {d['A4_identidade_da_urna']['divergentes']} dif", flush=True)

if not dados:
    print("nenhuma UF com integridade provada — abortando sem tocar na publicacao", flush=True)
    raise SystemExit(3)

# ---------- 2. nacional = soma dos per-UF ----------
def soma_counter(chave):
    c = collections.Counter()
    for d in dados.values():
        for k, v in d[chave].items(): c[k] += v
    return c

permin = soma_counter("C3_curva_por_minuto")
ultimo = soma_counter("B4_ultimo_voto_por_hora")
inter  = collections.Counter()
for d in dados.values():
    for k, v in d["C4_intervalos"]["distribuicao"].items(): inter[int(k)] += v
S = lambda k: sum(d[k] for d in dados.values())
tv = S("votos_presidente"); tot_int = sum(inter.values())
rap = sum(q for s, q in inter.items() if s < 20)
ca2 = sum(d["A2_triangulacao"]["secoes_comparadas"] for d in dados.values())
da2 = sum(d["A2_triangulacao"]["divergentes"] for d in dados.values())
a2m = sum(d["A2_triangulacao"].get("log_menor_que_bu", 0) for d in dados.values())
a2M = sum(d["A2_triangulacao"].get("log_maior_que_bu", 0) for d in dados.values())
a2dmin = min([d["A2_triangulacao"].get("delta_min", 0) for d in dados.values()] or [0])
a2dmax = max([d["A2_triangulacao"].get("delta_max", 0) for d in dados.values()] or [0])
ca4 = sum(d["A4_identidade_da_urna"]["secoes_comparadas"] for d in dados.values())
da4 = sum(d["A4_identidade_da_urna"]["divergentes"] for d in dados.values())
k4c = sum(d["A4_identidade_da_urna"].get("contingencia_sem_voto", 0) for d in dados.values())
k4s = sum(d["A4_identidade_da_urna"].get("sem_explicacao", 0) for d in dados.values())
ordem = sorted(dados)

# C4b nacional: soma das distribuicoes por UF (antes/final), dos votos por janela e da serie
_jd = {j: collections.Counter() for j in ("antes", "final")}
_jv = collections.Counter(); _r10 = 0; _rr = 0
_s10 = collections.defaultdict(lambda: [0, 0.0, 0, 0])
for d in dados.values():
    c4b = d.get("C4b_reta_final") or {}
    for j, dist in (c4b.get("distribuicao") or {}).items():
        for k, v in dist.items(): _jd[j][int(k)] += v
    for j, r in (c4b.get("janelas") or {}).items(): _jv[j] += r.get("votos", 0)
    _r10 += c4b.get("secoes_final_com_10_votos", 0); _rr += c4b.get("secoes_final_rapida", 0)
    for b, e in (c4b.get("serie_10min") or {}).items():
        x = _s10[b]; x[0] += e["intervalos"]; x[1] += e["intervalos"]*(e["media_s"] or 0)
        x[2] += e["abaixo_de_20s"]; x[3] += e["votos"]
_disc = collections.Counter()
for d in dados.values():
    for j, r in ((d.get("C4b_reta_final") or {}).get("janelas") or {}).items(): _disc[j] += r.get("discrepantes", 0)
_jan = {j: resumo_janela(_jd[j], _jv[j]) for j in ("antes", "final")}
for j in ("a1630", "f17", "f18", "f19", "f1930"):
    # subfaixas nao tem distribuicao nacional: media ponderada pelos intervalos de cada UF
    _n = sum((d.get("C4b_reta_final") or {}).get("janelas", {}).get(j, {}).get("intervalos", 0) for d in dados.values())
    _s = sum((d.get("C4b_reta_final") or {}).get("janelas", {}).get(j, {}).get("intervalos", 0)
             * ((d.get("C4b_reta_final") or {}).get("janelas", {}).get(j, {}).get("media_s") or 0) for d in dados.values())
    _r = sum((d.get("C4b_reta_final") or {}).get("janelas", {}).get(j, {}).get("abaixo_de_20s", 0) for d in dados.values())
    _jan[j] = {"votos": _jv[j], "intervalos": _n, "media_s": round(_s/_n, 2) if _n else None,
               "mediana_s": None, "abaixo_de_20s": _r,
               "pct_abaixo_20s": round(100*_r/_n, 4) if _n else None, "media_ate_120s": None}
for j in _jan:
    _jan[j]["discrepantes"] = _disc[j]
    _jan[j]["pct_discrepantes"] = round(100*_disc[j]/_jan[j]["intervalos"], 4) if _jan[j]["intervalos"] else None
_ma, _mr = _jan["antes"]["media_s"], _jan["final"]["media_s"]
C4B = {"inicio_final": "17:00", "janelas": _jan,
       "limiar_discrepante": f"intervalo abaixo de {int(FRAC_DISC*100)}% da mediana da própria seção antes das 17h (ou de 20 s, se a seção não tem base)",
       "votos_discrepantes_final": _disc["final"],
       "aceleracao": round(_ma/_mr, 3) if (_ma and _mr) else None,
       "secoes_final_com_10_votos": _r10, "secoes_final_rapida": _rr,
       "distribuicao": {j: {str(k): v for k, v in sorted(_jd[j].items())} for j in ("antes", "final")},
       "serie_10min": {b: {"intervalos": x[0], "media_s": round(x[1]/x[0], 2) if x[0] else None,
                           "abaixo_de_20s": x[2], "votos": x[3]} for b, x in sorted(_s10.items())}}

NAC = {
 "gerado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "ufs": ordem, "secoes": S("secoes"), "votos_presidente": tv,
 "habilitacoes": S("habilitacoes"), "computados": S("computados"),
 "C1_secoes_com_voto_apos_lacre": S("C1_secoes_com_voto_apos_lacre"),
 "C2_votos_apos_17h": S("C2_votos_apos_17h"),
 "C2_pct": round(100*S("C2_votos_apos_17h")/tv, 4) if tv else 0,
 "C2_de17_a_19h": S("C2_de17_a_19h"), "C2_apos_19h": S("C2_apos_19h"),
 "municipios": S("municipios"),
 "C3_curva_por_minuto": dict(sorted(permin.items())),
 "C4_intervalos": {"amostra": tot_int, "mediana_s": mediana_ponderada(inter),
                   "abaixo_de_20s": rap,
                   "pct_abaixo_20s": round(100*rap/tot_int, 4) if tot_int else 0,
                   "distribuicao": {str(k): v for k, v in sorted(inter.items())}},
 "C4b_reta_final": C4B,
 "B4_ultimo_voto_por_hora": dict(sorted(ultimo.items())),
 "C6_hab_menos_comput": S("C6_hab_menos_comput"),
 "A2_triangulacao": {"secoes_comparadas": ca2, "divergentes": da2,
                     "pct": round(100*da2/ca2, 4) if ca2 else None,
                     "log_menor_que_bu": a2m, "log_maior_que_bu": a2M,
                     "delta_min": a2dmin, "delta_max": a2dmax,
                     "exemplos": [e for d in dados.values() for e in d["A2_triangulacao"]["exemplos"]][:30]},
 "A4_identidade_da_urna": {"secoes_comparadas": ca4, "divergentes": da4,
                           "contingencia_sem_voto": k4c, "sem_explicacao": k4s,
                           "exemplo_conferido": next((d["A4_identidade_da_urna"].get("exemplo_conferido")
                               for d in dados.values() if d["A4_identidade_da_urna"].get("exemplo_conferido")), None),
                           "exemplos": [e for d in dados.values() for e in d["A4_identidade_da_urna"]["exemplos"]][:30]},
 "urnas_distintas": S("urnas_distintas"),
 "por_uf": {uf: {k: v for k, v in dados[uf].items() if k != "_zip_bytes"} for uf in ordem},
}
NAC["turno"] = int(T); NAC["prazo_legal"] = PRAZO
json.dump(NAC, open(SAIDA_JSON, "w"), indent=1, ensure_ascii=False)

# ---------- 3. CSV unico de secoes + CSV das secoes rapidas na janela final ----------
RAPIDAS = SAIDA_CSV.replace("demonstracao_secoes", "secoes_rapidas_janela_final")
fr = open(RAPIDAS, "w", newline=""); wr = csv.writer(fr)
with open(SAIDA_CSV, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["uf","municipio","municipio_nome","zona","secao","urna_serie","votos",
                "apos17h","de17_a_19h","apos_19h","apos_lacre","ultimo_voto",
                "votos_ate_17h","votos_17h_em_diante","media_s_antes","media_s_final",
                "mediana_s_final","abaixo_20s_final","mediana_s_antes","limiar_discrepante_s",
                "discrepantes_antes","discrepantes_final"])
    wr.writerow(["uf","municipio","municipio_nome","zona","secao","urna_serie","votos",
                 "votos_17h_em_diante","media_s_antes","media_s_final","mediana_s_final",
                 "abaixo_20s_final","mediana_s_antes","limiar_discrepante_s","discrepantes_antes",
                 "discrepantes_final","motivo"])
    n_rap = 0
    for uf in ordem:
        p = f"{DEMO}/{uf}_secoes.csv"
        esperado = dados[uf].get("_csv_linhas")
        if not os.path.exists(p):
            print(f"  AVISO {uf}: CSV de seções ausente — fora do CSV público", flush=True); continue
        with open(p) as g:
            next(g, None)
            n = 0
            for linha in g:
                f.write(linha); n += 1
                c = next(csv.reader([linha]))
                try:
                    vf, med, a20 = int(c[13] or 0), (float(c[16]) if c[16] else None), int(c[17] or 0)
                    lim, da, df = (float(c[19]) if c[19] else None), int(c[20] or 0), int(c[21] or 0)
                except (IndexError, ValueError):
                    continue
                motivo = []
                if a20 > 0: motivo.append(f"{a20} intervalo(s) abaixo de 20 s a partir das 17h")
                if vf >= 10 and med is not None and med < 20: motivo.append(f"mediana de {med:.0f} s com {vf} votos a partir das 17h")
                if df > 0: motivo.append(f"{df} voto(s) abaixo de {lim:.0f} s (25% da mediana do dia desta seção) a partir das 17h; antes das 17h havia {da}")
                if motivo:
                    wr.writerow(c[0:7] + [c[13], c[14], c[15], c[16], c[17], c[18], c[19], c[20], c[21], "; ".join(motivo)]); n_rap += 1
        if esperado is not None and n != esperado:
            print(f"  AVISO {uf}: CSV tem {n} linhas, esperado {esperado} — arquivo alterado "
                  f"depois da escrita (apague {DEMO}/{uf}.json para refazer)", flush=True)

fr.close()
print(f"  secoes rapidas na janela final: {n_rap} -> {os.path.basename(RAPIDAS)}", flush=True)
print(json.dumps({"ufs": ordem, "municipios": NAC["municipios"],
                  "secoes": NAC["secoes"], "votos": tv,
                  "A2_divergentes": da2, "A4_divergentes": da4,
                  "C1_apos_lacre": NAC["C1_secoes_com_voto_apos_lacre"],
                  "C4_abaixo_20s": rap,
                  "C4b_media_antes_s": _ma, "C4b_media_final_s": _mr,
                  "C4b_secoes_final_rapida": _rr,
                  "C4b_votos_discrepantes_final": _disc["final"],
                  "C4b_votos_discrepantes_antes": _disc["antes"]}, ensure_ascii=False, indent=1))
