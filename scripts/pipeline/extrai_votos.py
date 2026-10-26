#!/usr/bin/env python3
"""Extrai votos por candidato por secao (Presidente). uso: extrai_votos.py <turno>"""
import csv, io, json, os, sys, zipfile, re, hashlib
csv.field_size_limit(10**9)
T=sys.argv[1]; AC=f"/Volumes/SSD1TB/acervo-tse/2026-{T}t/boletins"
OUT=os.path.expanduser(f"~/Claude/Projetos/eleição/pipeline/resultados/{T}t/votos")
os.makedirs(OUT,exist_ok=True)
def uf_de(n):
    m=re.search(r"_(?:1t|2t)_([A-Z]{2})_",n); return m.group(1) if m else None
for z in sorted(os.listdir(AC)):
    if not z.endswith(".zip"): continue
    uf=uf_de(z)
    if not uf or os.path.exists(f"{OUT}/{uf}.csv"): continue
    tse=f"{AC}/{z}.sha512.tse"
    if os.path.exists(tse):
        esp=open(tse).read().split()[0].lower(); h=hashlib.sha512()
        with open(f"{AC}/{z}","rb") as fh:
            for b in iter(lambda:fh.read(1<<22),b""): h.update(b)
        if h.hexdigest()!=esp:
            print(f"{uf}: HASH DIVERGE — pulado",flush=True); continue
    linhas=[]
    with zipfile.ZipFile(f"{AC}/{z}") as zf:
        nm=[n for n in zf.namelist() if n.lower().endswith(".csv")][0]
        with zf.open(nm) as raw:
            for row in csv.DictReader(io.TextIOWrapper(raw,encoding="latin-1",newline=""),delimiter=";"):
                try:
                    if row.get("CD_CARGO_PERGUNTA")!="1": continue
                    linhas.append((row["CD_MUNICIPIO"],row["NR_ZONA"],row["NR_SECAO"],
                                   row["NR_VOTAVEL"],row["DS_TIPO_VOTAVEL"],
                                   int(row["QT_VOTOS"] or 0),int(row["QT_COMPARECIMENTO"] or 0)))
                except (ValueError,KeyError,TypeError): pass
    with open(f"{OUT}/{uf}.csv","w",newline="") as f:
        w=csv.writer(f); w.writerow(["municipio","zona","secao","numero","tipo","votos","comparecimento"])
        w.writerows(linhas)
    print(f"{uf}: {len(linhas)} linhas de votação",flush=True)
print("EXTRACAO_CONCLUIDA")
