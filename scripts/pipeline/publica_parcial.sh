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

# --- lock: NUNCA dois publicadores ao mesmo tempo (macOS nao tem flock; mkdir e atomico) ---
# Dois publicadores concorrentes = dois deploys, dois commits em corrida e duas
# versoes de manifesto disputando o mesmo numero. Aconteceu em 2026-10-27 09h.
LOCK="$PL/.publica.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  LPID=$(cat "$LOCK/pid" 2>/dev/null)
  if [ -n "$LPID" ] && kill -0 "$LPID" 2>/dev/null; then
    echo "$(date '+%F %T') publicador ja em execucao (pid $LPID) — saindo" >> "$PL/parcial.log"; exit 0
  fi
  # lock orfao (dono morreu): assume
  rm -rf "$LOCK"; mkdir "$LOCK" || exit 0
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

# assinatura do estado: tamanho dos blocos por UF/municipio + derivados publicados
# inclui TODO script que e sincronizado para o repo: corrigir qualquer um deles
# tem de disparar republicacao, senao o codigo publicado descola do que roda.
EST=$( { ls -l "$DEMO"/*.json 2>/dev/null
         ls -l "$PL"/demonstracao_1t.json "$PL"/analises.json "$PL"/E5_municipios_1t_2t.csv 2>/dev/null
         ls -l "$PL"/{coleta.py,audita.py,compara.py,extrai_votos.py,analises.py,demonstra.py,gera_demo_html.py} 2>/dev/null
         ls -l "$PL"/{forense.py,tardios.py,soma_oficial.py,gera_forense.py,remonta_2t.py,paginas_extra.py,pianista.py,gera_pianista.py} 2>/dev/null
         ls -l /Volumes/SSD1TB/acervo-tse/auditoria/forense/*/*.json "$PL"/resultados/{a3_soma_oficial.json,tardios.json} 2>/dev/null
         ls -l "$PL"/{baixa_resiliente.sh,marca_integros.sh,enfileira_restantes.sh} 2>/dev/null
         ls -l "$PL"/{roda.sh,publica.sh,publica_parcial.sh} 2>/dev/null
         ls -l "$P"/{diagnostico.sh,destrava.sh} 2>/dev/null
         ls -l /Volumes/SSD1TB/acervo-tse/2026-1t/originais/*.{ok,bad,sha512.local} 2>/dev/null; } \
       | awk '{print $5,$9}' | shasum | cut -d' ' -f1 )
# O CONTEUDO dos sidecars numericos tambem entra na assinatura. Tamanho+nome nao
# bastam: um sidecar reparado pode ter exatamente o mesmo tamanho do lixo que ele
# substituiu — o .esperado do PE em 2026-10-27 tinha 11 bytes antes (" bweb_1t_AM")
# e 11 bytes depois ("4297820068"), e o conserto nao dispararia republicacao.
ESTS=$( for s in /Volumes/SSD1TB/acervo-tse/2026-1t/originais/*.ok \
                 /Volumes/SSD1TB/acervo-tse/2026-1t/originais/*.bad \
                 /Volumes/SSD1TB/acervo-tse/2026-1t/originais/*.truncado \
                 /Volumes/SSD1TB/acervo-tse/2026-1t/originais/*.esperado; do
          [ -f "$s" ] && echo "$(basename "$s") $(tr -d '[:space:]' < "$s")"
        done 2>/dev/null | shasum | cut -d' ' -f1 )
EST="$EST-$ESTS"
[ -f "$MARCA" ] && [ "$(cat "$MARCA")" = "$EST" ] && exit 0

# 1. processa o que falta. exit 2/3 = acervo inacessivel ou nenhuma UF integra:
#    nesses casos NAO se publica nada.
if [ "${SEM_DEMONSTRA:-0}" = "1" ]; then
  echo "$(date '+%F %T') SEM_DEMONSTRA=1: pulando demonstra/analises (so paginas, manifesto e deploy)" >> "$PL/parcial.log"
  rc=0
else
"$PY" -u "$PL/demonstra.py" >> "$PL/parcial.log" 2>&1
rc=$?
fi
# 2T: roda a mesma bateria quando ja houver UF do 2T provada integra (ZIP remontado por secao ou oficial)
if [ "${SEM_DEMONSTRA:-0}" != "1" ] && ls /Volumes/SSD1TB/acervo-tse/2026-2t/originais/*_2t_*.zip.ok >/dev/null 2>&1; then
  "$PY" -u "$PL/demonstra.py" 2 >> "$PL/parcial.log" 2>&1 || echo "$(date '+%F %T') demonstra.py 2 falhou (segue so com o 1T)" >> "$PL/parcial.log"
fi
(exit $rc)
rc=$?
[ "$rc" -ne 0 ] && { echo "$(date '+%F %T') demonstra.py saiu $rc — publicacao abortada" >> "$PL/parcial.log"; exit "$rc"; }

# 2. analises (os blocos E saem sozinhos quando o 2T existir)
[ "${SEM_DEMONSTRA:-0}" = "1" ] || "$PY" -u "$PL/analises.py" >> "$PL/parcial.log" 2>&1 || \
  echo "$(date '+%F %T') analises.py falhou — seguindo" >> "$PL/parcial.log"

# 3. HTML: nacional + por estado + por municipio
"$PY" -u "$PL/gera_demo_html.py" >> "$PL/parcial.log" 2>&1 || exit 0
# 3b. emenda de 28/10: forense dos logs, soma oficial, votos tardios (tolera dados parciais)
"$PY" -u "$PL/tardios.py" >> "$PL/parcial.log" 2>&1 || echo "$(date '+%F %T') tardios.py falhou — seguindo" >> "$PL/parcial.log"
"$PY" -u "$PL/gera_forense.py" >> "$PL/parcial.log" 2>&1 || echo "$(date '+%F %T') gera_forense.py falhou — seguindo" >> "$PL/parcial.log"
"$PY" -u "$PL/gera_pianista.py" >> "$PL/parcial.log" 2>&1 || echo "$(date '+%F %T') gera_pianista.py falhou — seguindo" >> "$PL/parcial.log"
cp "$P/relatorio/EMENDA-2026-10-28.md" "$R/relatorio/" 2>/dev/null || true

# 4. dados derivados para o repo
mkdir -p "$R/dados/analises" "$R/scripts/pipeline"
cp "$PL/secoes_rapidas_janela_final.csv" "$R/dados/analises/" 2>/dev/null || true
cp "$PL/demonstracao_2t.json" "$PL/demonstracao_secoes_2t.csv" "$PL/secoes_rapidas_janela_final_2t.csv" "$R/dados/analises/" 2>/dev/null || true
cp /Volumes/SSD1TB/acervo-tse/2026-2t/registro_secoes_*.json "$R/dados/2t/" 2>/dev/null || true
cp "$PL/coleta_secoes.py" "$R/scripts/pipeline/" 2>/dev/null || true
cp "$P/relatorio/PESQUISA-PUBLICACAO-2T.md" "$R/relatorio/" 2>/dev/null || true
cp "$PL/demonstracao_1t.json" "$PL/demonstracao_secoes.csv" "$PL/analises.json" \
   "$R/dados/analises/" 2>/dev/null
cp "$PL/E5_municipios_1t_2t.csv" "$R/dados/analises/" 2>/dev/null || true

# 4b. manifesto do ACERVO bruto -> GitHub. Os ZIPs do TSE (30-200 GB) nao cabem
#     no GitHub; o que vai e a prova de custodia: por UF, bytes, sha512 e status de
#     integridade, lido dos sidecars (.ok/.bad/.sha512.local) — instantaneo.
"$PY" - <<'PYA'
import glob,json,os,re,datetime
AC="/Volumes/SSD1TB/acervo-tse/2026-1t/originais"

def num(p):
    """Sidecar numerico lido com tolerancia: devolve (valor, lixo).
    Um sidecar ilegivel NAO pode derrubar a prova de custodia. Em 2026-10-27 o
    .esperado do PE foi gravado com 11 bytes de lixo (" bweb_1t_AM") no volume
    externo; o int() cru matava este bloco inteiro e, como nao havia checagem de
    status, o publicador seguia e carimbava manifesto novo com o
    acervo-1t-custodia.json congelado (15 UFs enquanto o disco tinha 28)."""
    if not os.path.exists(p): return None,None
    try: t=open(p).read().strip()
    except OSError as e: return None,f"erro de leitura: {e}"
    return (int(t),None) if re.fullmatch(r"\d+",t) else (None,t[:40])
R=os.path.expanduser("~/Claude/Projetos/eleição/repo")
itens=[]
for z in sorted(glob.glob(f"{AC}/bu_imgbu_logjez_rdv_vscmr_2026_1t_*.zip")):
    uf=re.search(r"_1t_([A-Z]{2})\.zip",z).group(1)
    tam=os.path.getsize(z)
    vok,sujo_ok=num(z+".ok"); vbad,sujo_bad=num(z+".bad"); esp,sujo_esp=num(z+".esperado")
    ok=(vok==tam); bad=(vbad==tam)
    trunc=(esp is not None and tam<esp)
    sujos={k:v for k,v in (("ok",sujo_ok),("bad",sujo_bad),("esperado",sujo_esp)) if v}
    if sujos: print(f"AVISO {uf}: sidecar ilegivel {sujos} — tratado como ausente")
    # sidecar pode ser hash puro (novo) ou "hash  caminho" (formato antigo do shasum)
    sha=None
    if os.path.exists(z+".sha512.local"):
        tok=open(z+".sha512.local").read().split()
        sha=tok[0] if tok and len(tok[0])==128 else None
    itens.append({"uf":uf,"arquivo":os.path.basename(z),"bytes":tam,
                  "integridade":"ok" if ok else ("truncado" if trunc else ("crc_falhou" if bad else "em_download_ou_nao_verificado")),
                  "bytes_esperados":esp,
                  "sidecars_ilegiveis":sujos or None,
                  "sha512":sha if ok else None,
                  "fonte":"https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/"+os.path.basename(z)})
man={"titulo":"Acervo bruto do TSE - logs de urna 1o turno - manifesto de custodia",
     "nota":"Os ZIPs ficam em disco local (NVMe). O TSE nao publica hash destes arquivos; "
            "o sha512 aqui foi calculado no instante em que zipfile.testzip() passou.",
     "gerado_em_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
     "ufs_integras":sum(1 for i in itens if i["integridade"]=="ok"),"ufs_no_disco":len(itens),
     "arquivos":itens}
os.makedirs(f"{R}/dados",exist_ok=True)
json.dump(man,open(f"{R}/dados/acervo-1t-custodia.json","w"),indent=1,ensure_ascii=False)
print(f"acervo-1t-custodia.json: {man['ufs_integras']} íntegras de {len(itens)} no disco")
PYA
CUST=$?
# Publicar manifesto carimbado afirmando metodo auditavel com a prova de custodia
# velha e pior do que nao publicar: aborta. Antes deste if o heredoc podia morrer
# em silencio (nao ha set -e) e a publicacao seguia — foi o que aconteceu das
# 14h50 as 20h08 de 2026-10-27, cinco deploys com custodia congelada.
if [ "$CUST" -ne 0 ]; then
  echo "$(date '+%F %T') CUSTODIA FALHOU (exit $CUST) — publicacao abortada, acervo-1t-custodia.json nao foi regenerado" >> "$PL/parcial.log"
  exit 5
fi

# 5. codigo que de fato rodou — o que sustenta a auditabilidade
cp "$PL"/{coleta.py,audita.py,compara.py,extrai_votos.py,analises.py,demonstra.py,gera_demo_html.py} \
   "$R/scripts/pipeline/" 2>/dev/null
cp "$PL"/{baixa_resiliente.sh,marca_integros.sh,enfileira_restantes.sh} \
   "$R/scripts/pipeline/" 2>/dev/null
cp "$PL"/{roda.sh,publica.sh,publica_parcial.sh} "$R/scripts/pipeline/" 2>/dev/null
cp "$PL/sha512_backfill.sh" "$R/scripts/pipeline/" 2>/dev/null
cp "$PL/repara_zip.py" "$R/scripts/pipeline/" 2>/dev/null
cp "$PL"/{forense.py,tardios.py,soma_oficial.py,gera_forense.py,remonta_2t.py,paginas_extra.py,pianista.py,gera_pianista.py} "$R/scripts/pipeline/" 2>/dev/null
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
# --archive=tgz: upload unico; por arquivo estoura o limite de 40 mil uploads/dia do Vercel (28/10/2026)
cd "$R/site"
if ! vercel deploy --prod --yes --archive=tgz > "$PL/deploy.log" 2>&1; then
  echo "$(date '+%F %T') deploy falhou; 2a tentativa em 60 s" >> "$PL/deploy.log"; sleep 60
  vercel deploy --prod --yes --archive=tgz >> "$PL/deploy.log" 2>&1
fi
cd "$R" && git add -A && \
  git -c user.name="Maneco Gomes" -c user.email="manecogomes@gmail.com" \
      commit -q -m "Publicação incremental: dados, código e manifesto carimbado" 2>/dev/null && \
  git push -q origin main 2>/dev/null

echo "$EST" > "$MARCA"
echo "$(date '+%F %T') publicado incremento (manifesto v$VER-$TS)" >> "$PL/parcial.log"
