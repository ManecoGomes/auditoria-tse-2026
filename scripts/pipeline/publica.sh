#!/bin/bash
# Publica os resultados do 2o turno: site, GitHub, Drive e carimbo de tempo.
PY=${PY:-/opt/homebrew/bin/python3}   # 3.9 do sistema nao tem datetime.UTC
set -e
P="$HOME/Claude/Projetos/eleição"; R="$P/repo"; PL="$P/pipeline"
OTS="$P/.venv-ots/bin/ots"

# --- PDF do relatorio ---
bash "$P/../Eleicoes2026/build_pdf.sh" "$P/relatorio/RELATORIO-2T.md" \
     "$P/relatorio/Auditoria_TSE_2T_2026.pdf" 2>/dev/null || true

# --- repo: relatorio, dados derivados, scripts do pipeline ---
mkdir -p "$R/relatorio" "$R/dados/2t" "$R/scripts/pipeline"
cp "$P/relatorio/RELATORIO-2T.md" "$R/relatorio/" 2>/dev/null || true
cp "$P/relatorio/Auditoria_TSE_2T_2026.pdf" "$R/relatorio/" 2>/dev/null || true
cp "$P/relatorio/O-QUE-FOI-FEITO.md" "$R/relatorio/" 2>/dev/null || true
cp "$P/relatorio/PLANO-2T.md" "$R/relatorio/" 2>/dev/null || true
mkdir -p "$R/dados/analises"
cp "$PL/analises.json" "$PL/resumo_2t.json" "$R/dados/analises/" 2>/dev/null || true
cp "$PL/resultados/E4_ecologica.csv" "$R/dados/analises/" 2>/dev/null || true
cp "$PL"/{extrai_votos.py,analises.py} "$R/scripts/pipeline/" 2>/dev/null || true
cp -r "$PL/resultados/2t" "$R/dados/" 2>/dev/null || true
cp "$PL"/{coleta.py,audita.py,compara.py} "$R/scripts/pipeline/" 2>/dev/null || true

# --- site: pagina do 2o turno ---
pandoc -f gfm -t html "$P/relatorio/RELATORIO-2T.md" -o /tmp/rel2t.html
"$PY" - <<'PY'
import os,datetime
P=os.path.expanduser("~/Claude/Projetos/eleição")
base=open(f"{P}/repo/site/relatorio.html").read()
corpo=open("/tmp/rel2t.html").read()
i=base.index('<header class="top">'); j=base.index('<footer>')
head=base[:i]; foot=base[j:]
head=head.replace("Relatório completo","Auditoria do 2º turno").replace(
  "Documento técnico integral, com metodologia, resultados e limitações.",
  "Resultado do 2º turno confrontado com a régua do 1º.")
novo=head+f'<header class="top"><div class="kicker">Auditoria independente · Eleições Gerais 2026</div><h1>Auditoria do 2º turno</h1><p class="sub">Resultado confrontado com a régua do 1º turno.</p><nav><a href="index.html">Resumo</a><a href="relatorio.html">1º turno</a><a href="relatorio-2t.html" class="on">2º turno</a><a href="verificar.html">Como verificar</a><a href="dados.html">Dados e hashes</a></nav></header><div class="scroll">{corpo}</div>'+foot
open(f"{P}/repo/site/relatorio-2t.html","w").write(novo)
print("relatorio-2t.html gerado")
PY

# --- manifesto novo + carimbo ---
cd "$R"
TS=$(date -u +%Y%m%dT%H%MZ)
# versao do manifesto: proxima na sequencia ja publicada, nunca hardcoded.
# Gravar "v3" depois de existir um "v4" quebra a monotonicidade da cadeia —
# foi o que aconteceu em 2026-10-27, com dois manifestos v3 apos um v4.
VER=$("$PY" -c "
import glob,re
ns=[int(m.group(1)) for f in glob.glob('manifestos/manifesto-v*-*.json')
    for m in [re.search(r'manifesto-v(\\d+)-', f)] if m]
print(max(ns)+1 if ns else 1)")
"$PY" - <<PY
import hashlib,json,os,datetime
base=os.getcwd(); itens=[]
for r,d,fs in os.walk(base):
    if ".git" in r or "/manifestos" in r: continue
    for f in sorted(fs):
        p=os.path.join(r,f); rel=os.path.relpath(p,base)
        h=hashlib.sha512()
        with open(p,"rb") as fh:
            for b in iter(lambda:fh.read(1<<20),b""): h.update(b)
        itens.append({"arquivo":rel,"bytes":os.path.getsize(p),"sha512":h.hexdigest()})
ts=datetime.datetime.now(datetime.timezone.utc)
man={"titulo":"Auditoria de horarios - Eleicoes Gerais 2026","versao":$VER,
     "escopo":"1o e 2o turnos","site":"https://auditoria-tse-2026.com.br",
     "gerado_em_utc":ts.isoformat(),
     "responsavel":"Luis Manuel Jordao Elias Gomes - OAB/RJ 245.463",
     "n_arquivos":len(itens),"arquivos":sorted(itens,key=lambda x:x["arquivo"])}
os.makedirs("manifestos",exist_ok=True)
json.dump(man,open(f"manifestos/manifesto-v$VER-$TS.json","w"),indent=1,ensure_ascii=False)
json.dump(man,open("manifesto.json","w"),indent=1,ensure_ascii=False)
PY
"$OTS" stamp "manifestos/manifesto-v$VER-$TS.json" || true
cp "manifestos/manifesto-v$VER-$TS.json.ots" manifesto.json.ots 2>/dev/null || true

# --- deploy e push ---
cd "$R/site" && vercel deploy --prod --yes > /dev/null 2>&1
cd "$R" && git add -A && \
  git -c user.name="Maneco Gomes" -c user.email="manecogomes@gmail.com" \
      commit -q -m "Auditoria do 2º turno: resultado, dados e manifesto v3" && git push -q origin main

# --- Drive ---
D="gdrive:Auditoria-TSE-2026"
rclone copy "$R/relatorio"        "$D/1-Relatorio"            --transfers 3 -q || true
rclone copy "$R/manifestos"       "$D/2-Manifestos-e-carimbos" --transfers 3 -q || true
rclone copy "$R/scripts"          "$D/3-Scripts"               --transfers 3 -q || true
rclone copy "$R/dados"            "$D/4-Dados-derivados"       --transfers 3 -q || true
rclone copy /Volumes/SSD1TB/acervo-tse/2026-2t/boletins \
            "$D/5-Fontes-originais-TSE/Boletins-2o-turno" --drive-chunk-size 128M --transfers 3 -q || true
echo "PUBLICACAO CONCLUIDA"
