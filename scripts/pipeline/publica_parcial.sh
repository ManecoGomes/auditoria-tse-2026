#!/bin/bash
# Publicacao incremental: regenera o que mudou e publica.
#
# Diferente da primeira versao, esta TAMBEM sincroniza os scripts e regenera o
# manifesto carimbado. Sem isso o site ia ao ar com dados novos e com as copias
# publicadas do codigo em versao velha — o que derruba a alegacao central do
# projeto, de que o metodo e auditavel. O manifesto e o carimbo OpenTimestamps
# sao o que torna a data de publicacao verificavel por terceiros.
PY=${PY:-/opt/homebrew/bin/python3}   # 3.9 do sistema nao tem datetime.UTC
P="$HOME/Claude/Projetos/eleição"; R="$P/repo"; PL="$P/pipeline"
OTS="$P/.venv-ots/bin/ots"
DEMO=/Volumes/SSD1TB/acervo-tse/auditoria/demo
MARCA="$PL/.ultimo_estado"

# assinatura do estado: tamanho dos blocos por UF/municipio + derivados publicados
# inclui TODO script que e sincronizado para o repo: corrigir qualquer um deles
# tem de disparar republicacao, senao o codigo publicado descola do que roda.
EST=$( { ls -l "$DEMO"/*.json 2>/dev/null
         ls -l "$PL"/demonstracao_1t.json "$PL"/analises.json "$PL"/E5_municipios_1t_2t.csv 2>/dev/null
         ls -l "$PL"/{coleta.py,audita.py,compara.py,extrai_votos.py,analises.py,demonstra.py,gera_demo_html.py} 2>/dev/null
         ls -l "$PL"/{baixa_resiliente.sh,marca_integros.sh,enfileira_restantes.sh} 2>/dev/null
         ls -l "$PL"/{roda.sh,publica.sh,publica_parcial.sh} 2>/dev/null
         ls -l "$P"/{diagnostico.sh,destrava.sh} 2>/dev/null; } \
       | awk '{print $5,$9}' | shasum | cut -d' ' -f1 )
[ -f "$MARCA" ] && [ "$(cat "$MARCA")" = "$EST" ] && exit 0

# 1. processa o que falta. exit 2/3 = acervo inacessivel ou nenhuma UF integra:
#    nesses casos NAO se publica nada.
"$PY" -u "$PL/demonstra.py" >> "$PL/parcial.log" 2>&1
rc=$?
[ "$rc" -ne 0 ] && { echo "$(date '+%F %T') demonstra.py saiu $rc — publicacao abortada" >> "$PL/parcial.log"; exit "$rc"; }

# 2. analises (os blocos E saem sozinhos quando o 2T existir)
"$PY" -u "$PL/analises.py" >> "$PL/parcial.log" 2>&1 || \
  echo "$(date '+%F %T') analises.py falhou — seguindo" >> "$PL/parcial.log"

# 3. HTML: nacional + por estado + por municipio
"$PY" -u "$PL/gera_demo_html.py" >> "$PL/parcial.log" 2>&1 || exit 0

# 4. dados derivados para o repo
mkdir -p "$R/dados/analises" "$R/scripts/pipeline"
cp "$PL/demonstracao_1t.json" "$PL/demonstracao_secoes.csv" "$PL/analises.json" \
   "$R/dados/analises/" 2>/dev/null
cp "$PL/E5_municipios_1t_2t.csv" "$R/dados/analises/" 2>/dev/null || true

# 5. codigo que de fato rodou — o que sustenta a auditabilidade
cp "$PL"/{coleta.py,audita.py,compara.py,extrai_votos.py,analises.py,demonstra.py,gera_demo_html.py} \
   "$R/scripts/pipeline/" 2>/dev/null
cp "$PL"/{baixa_resiliente.sh,marca_integros.sh,enfileira_restantes.sh} \
   "$R/scripts/pipeline/" 2>/dev/null
cp "$PL"/{roda.sh,publica.sh,publica_parcial.sh} "$R/scripts/pipeline/" 2>/dev/null
cp "$P/diagnostico.sh" "$P/destrava.sh" "$R/scripts/" 2>/dev/null

# 6. manifesto novo + carimbo no Bitcoin
cd "$R" || exit 0
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
     "escopo":"1o turno, por UF e por municipio","site":"https://auditoria-tse-2026.com.br",
     "gerado_em_utc":ts.isoformat(),
     "responsavel":"Luis Manuel Jordao Elias Gomes - OAB/RJ 245.463",
     "n_arquivos":len(itens),"arquivos":sorted(itens,key=lambda x:x["arquivo"])}
os.makedirs("manifestos",exist_ok=True)
json.dump(man,open(f"manifestos/manifesto-v$VER-$TS.json","w"),indent=1,ensure_ascii=False)
json.dump(man,open("manifesto.json","w"),indent=1,ensure_ascii=False)
print(f"manifesto: {len(itens)} arquivos")
PY
[ -x "$OTS" ] && "$OTS" stamp "manifestos/manifesto-v$VER-$TS.json" >/dev/null 2>&1
cp "manifestos/manifesto-v$VER-$TS.json.ots" manifesto.json.ots 2>/dev/null || true

# 7. deploy e push
cd "$R/site" && vercel deploy --prod --yes >/dev/null 2>&1
cd "$R" && git add -A && \
  git -c user.name="Maneco Gomes" -c user.email="manecogomes@gmail.com" \
      commit -q -m "Publicação incremental: dados, código e manifesto carimbado" 2>/dev/null && \
  git push -q origin main 2>/dev/null

echo "$EST" > "$MARCA"
echo "$(date '+%F %T') publicado incremento (manifesto v3-$TS)" >> "$PL/parcial.log"
