#!/bin/bash
# Sonda unica de estado do projeto auditoria-tse-2026. Sem efeito colateral:
# so le. Saida pensada para ser lida por humano e por agente.
P="$HOME/Claude/Projetos/eleição"; PL="$P/pipeline"
AC1=/Volumes/SSD1TB/acervo-tse/2026-1t/originais
AC2=/Volumes/SSD1TB/acervo-tse/2026-2t/originais
DEMO=/Volumes/SSD1TB/acervo-tse/auditoria/demo
TODAS="AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ"
echo "=== DIAGNOSTICO auditoria-tse-2026 — $(date '+%F %T') ==="

echo; echo "-- 1. dados do 2o turno no TSE --"
tail -1 "$P/vigia/vigia.log" 2>/dev/null || echo "sem vigia.log"
[ -f "$P/vigia/DISPONIVEL_2T.txt" ] && echo "FLAG DISPONIVEL_2T PRESENTE — o 2o turno saiu" || echo "flag 2T ausente: TSE ainda nao publicou"

echo; echo "-- 2. tarefas agendadas --"
for j in com.maneco.vigia-tse-2t com.maneco.pipeline-tse-2t com.maneco.destrava-tse; do
  st=$(launchctl print "gui/$(id -u)/$j" 2>/dev/null | sed -n 's/.*last exit code = //p' | tr -d '()')
  carregado=$(launchctl list 2>/dev/null | grep -c "$j")
  echo "$j: carregado=$carregado ultimo_exit=${st:-?}"
done

echo; echo "-- 3. processos vivos do projeto --"
ps -eo pid,etime,%cpu,command | grep -E 'baixa_resiliente|demonstra\.py|analises\.py|roda\.sh|publica|marca_integros|arqurnatot' | grep -v grep \
  | sed 's/\(.\{110\}\).*/\1…/' || echo "nenhum"

echo; echo "-- 4. acervo 1o turno (28 UFs) --"
ok=0; falta=""; semok=""
for uf in $TODAS; do
  z="$AC1/bu_imgbu_logjez_rdv_vscmr_2026_1t_$uf.zip"
  if [ -f "$z.ok" ] && [ "$(cat "$z.ok" 2>/dev/null)" = "$(stat -f %z "$z" 2>/dev/null)" ]; then
    ok=$((ok+1))
  elif [ -f "$z" ]; then semok="$semok $uf"
  else falta="$falta $uf"; fi
done
echo "integras (sidecar .ok valido): $ok de 28"
[ -n "$semok" ] && echo "baixadas SEM integridade provada:$semok"
[ -n "$falta" ] && echo "ainda nao baixadas:$falta"
tail -2 "$PL/baixa_resiliente.log" 2>/dev/null
df -h /Volumes/SSD1TB 2>/dev/null | tail -1 | awk '{print "disco SSD1TB: "$4" livres de "$2}'

echo; echo "-- 5. auditoria processada --"
echo "UFs com bloco pronto: $(ls "$DEMO"/*.json 2>/dev/null | grep -v _municipios | wc -l | tr -d ' ')"
echo "UFs com municipios:   $(ls "$DEMO"/*_municipios.json 2>/dev/null | wc -l | tr -d ' ')"
if [ -f "$PL/demonstracao_1t.json" ]; then
  /opt/homebrew/bin/python3 - <<'PY' 2>/dev/null
import json,os
d=json.load(open(os.path.expanduser("~/Claude/Projetos/eleição/pipeline/demonstracao_1t.json")))
print(f"  publicado: {len(d.get('ufs',[]))} UFs | {d.get('municipios','?')} municipios | "
      f"{d.get('secoes',0):,} secoes | {d.get('votos_presidente',0):,} votos".replace(",","."))
print(f"  C1 voto apos lacre: {d.get('C1_secoes_com_voto_apos_lacre')} | "
      f"C4 abaixo de 20s: {d.get('C4_intervalos',{}).get('abaixo_de_20s')} | "
      f"A2 divergentes: {d.get('A2_triangulacao',{}).get('divergentes')} | "
      f"A4 sem explicacao: {d.get('A4_identidade_da_urna',{}).get('sem_explicacao')}")
PY
fi
echo "analises.json: $(/opt/homebrew/bin/python3 -c "import json;d=json.load(open('$PL/analises.json'));print(', '.join(d.get('blocos',{}).keys()) or 'VAZIO')" 2>/dev/null || echo ilegivel)"

echo; echo "-- 6. erros recentes nos logs --"
grep -h -iE 'traceback|error|falhou|corrompido|DESISTI|sem explicacao' \
  "$PL"/*.log "$P/vigia/vigia.log" 2>/dev/null | tail -8 || echo "nenhum"

echo; echo "-- 7. publicacao --"
echo "site local: $(ls "$P/repo/site"/*.html 2>/dev/null | wc -l | tr -d ' ') paginas raiz, $(ls "$P/repo/site/estados"/*.html 2>/dev/null | wc -l | tr -d ' ') de estado, $(ls "$P/repo/site/estados"/*/*.html 2>/dev/null | wc -l | tr -d ' ') de municipio"
echo "git: $(git -C "$P/repo" status --short 2>/dev/null | wc -l | tr -d ' ') arquivos nao commitados | ultimo: $(git -C "$P/repo" log -1 --format='%h %s · %cr' 2>/dev/null)"
echo "no ar: $(curl -s -o /dev/null -w '%{http_code}' -m 15 https://auditoria-tse-2026.com.br 2>/dev/null)"
echo; echo "=== fim ==="
