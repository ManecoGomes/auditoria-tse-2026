#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrai dos boletins (bweb do TSE) uma linha por seção com votos de Presidente e os carimbos
de tempo: abertura, encerramento, emissão do BU (hora local da urna) e recepção do BU na
totalização (DT_BU_RECEBIDO). Base dos testes K4–K6 (emenda de 28/10/2026).

uso: extrai_bu_tempo.py <turno 1|2>
Saída: pipeline/resultados/{t}t/bu_tempo/{UF}.csv
"""
import csv, glob, io, os, sys, zipfile

T = sys.argv[1]
P = os.path.expanduser("~/Claude/Projetos/eleição")
BOL = f"/Volumes/SSD1TB/acervo-tse/2026-{T}t/boletins"
OUT = f"{P}/pipeline/resultados/{T}t/bu_tempo"
os.makedirs(OUT, exist_ok=True)
COLS = ["uf", "municipio", "nome", "zona", "secao", "local", "aptos", "comparecimento", "v13", "v22", "outros_nominais", "brancos", "nulos",
        "urna", "tipo_urna", "abertura", "encerramento", "emissao_bu", "recebido"]

for z in sorted(glob.glob(f"{BOL}/bweb_{T}t_*.zip")):
    uf = z.split(f"_{T}t_")[1][:2]
    out = f"{OUT}/{uf}.csv"
    if os.path.exists(out) and os.path.getsize(out) > 1000: print(uf, "cache", flush=True); continue
    zf = zipfile.ZipFile(z); nome = [n for n in zf.namelist() if n.endswith(".csv")][0]
    r = csv.reader(io.TextIOWrapper(zf.open(nome), encoding="latin-1"), delimiter=";")
    h = next(r); ix = {k: i for i, k in enumerate(h)}
    g = lambda row, k: row[ix[k]]
    secs = {}
    for row in r:
        if g(row, "DS_CARGO_PERGUNTA") != "Presidente": continue
        k = (int(g(row, "CD_MUNICIPIO")), int(g(row, "NR_ZONA")), int(g(row, "NR_SECAO")))
        e = secs.get(k)
        if e is None:
            e = secs[k] = {"uf": uf, "municipio": k[0], "nome": g(row, "NM_MUNICIPIO"), "zona": k[1], "secao": k[2], "local": g(row, "NR_LOCAL_VOTACAO"),
                           "aptos": int(g(row, "QT_APTOS") or 0), "comparecimento": int(g(row, "QT_COMPARECIMENTO") or 0), "v13": 0, "v22": 0, "outros_nominais": 0,
                           "brancos": 0, "nulos": 0, "urna": g(row, "NR_URNA_EFETIVADA"), "tipo_urna": g(row, "DS_TIPO_URNA"), "abertura": g(row, "DT_ABERTURA"),
                           "encerramento": g(row, "DT_ENCERRAMENTO"), "emissao_bu": g(row, "DT_EMISSAO_BU"), "recebido": g(row, "DT_BU_RECEBIDO")}
        tipo = g(row, "DS_TIPO_VOTAVEL"); num = g(row, "NR_VOTAVEL"); v = int(g(row, "QT_VOTOS") or 0)
        if tipo == "Nominal":
            if num == "13": e["v13"] += v
            elif num == "22": e["v22"] += v
            else: e["outros_nominais"] += v
        elif tipo == "Branco": e["brancos"] += v
        elif tipo == "Nulo": e["nulos"] += v
    with open(out + ".tmp", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader()
        for k in sorted(secs): w.writerow(secs[k])
    os.replace(out + ".tmp", out)
    print(uf, len(secs), "seções", flush=True)
print("EXTRACAO_BU_TEMPO_CONCLUIDA", flush=True)
