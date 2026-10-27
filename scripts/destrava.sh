#!/bin/bash
# Remediacao deterministica das falhas conhecidas do projeto (§5 do agente auditoria-tse).
# Roda de hora em hora pelo launchd. Sem LLM no caminho comum, idempotente.
# As permissoes da escalada vem de .claude/settings.json, revisado pelo Maneco —
# este script nao pede nem concede permissao nenhuma por conta propria.
P="$HOME/Claude/Projetos/eleição"; PL="$P/pipeline"
AC1=/Volumes/SSD1TB/acervo-tse/2026-1t/originais
DEMO=/Volumes/SSD1TB/acervo-tse/auditoria/demo
PY=/opt/homebrew/bin/python3
LOG="$P/destrava.log"
TODAS="AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ"
AGIU=0; ESCALA=""
log(){ echo "$(date '+%F %T') $*" >>"$LOG"; }
agiu(){ AGIU=1; log "AÇÃO: $*"; }
cd "$P" || exit 1
log "--- destrava iniciado ---"

# 1. script de analise pendurado: vivo > 45 min com CPU acumulada irrisoria.
#    Alcanca SO os tres scripts de analise do projeto — nunca download, nunca terceiros.
for pid in $(pgrep -f "$PL/demonstra.py|$PL/analises.py|$PL/gera_demo_html.py" 2>/dev/null); do
  et=$(ps -p "$pid" -o etime= 2>/dev/null | tr -d ' ')
  cp=$(ps -p "$pid" -o time=   2>/dev/null | tr -d ' ')
  [ -z "$et" ] && continue
  mins=$(echo "$et" | awk -F: '{if(NF==3)print $1*60+$2; else if(NF==2)print $1+0; else print 0}')
  segs=$(echo "$cp" | awk -F: '{if(NF==3)print $1*3600+$2*60+$3; else print $1*60+$2}')
  if [ "${mins:-0}" -gt 45 ] && [ "${segs:-0}" -lt 60 ]; then
    cmd=$(ps -p "$pid" -o command= 2>/dev/null | cut -c1-70)
    kill "$pid" 2>/dev/null
    agiu "encerrei analise pendurada pid=$pid ($et vivo, ${segs}s de CPU): $cmd"
  fi
done

# 2. ZIP baixado sem integridade provada -> prova agora (pula o que ainda cresce)
SEMOK=""
for uf in $TODAS; do
  z="$AC1/bu_imgbu_logjez_rdv_vscmr_2026_1t_$uf.zip"
  [ -f "$z" ] || continue
  [ -f "$z.ok" ] && [ "$(cat "$z.ok" 2>/dev/null)" = "$(stat -f %z "$z" 2>/dev/null)" ] && continue
  pgrep -qf "arqurnatot/bu_imgbu_logjez_rdv_vscmr_2026_1t_$uf.zip" && continue
  # ja reprovado neste exato tamanho: nao gastar CPU refazendo o CRC a cada hora.
  # O marcador cai sozinho quando o arquivo muda de tamanho (download novo).
  [ -f "$z.bad" ] && [ "$(cat "$z.bad" 2>/dev/null)" = "$(stat -f %z "$z" 2>/dev/null)" ] && continue
  SEMOK="$SEMOK $uf"
done
if [ -n "$SEMOK" ]; then
  "$PL/marca_integros.sh" $SEMOK >/dev/null 2>&1
  agiu "testzip rodado em:$SEMOK"
  for uf in $SEMOK; do
    z="$AC1/bu_imgbu_logjez_rdv_vscmr_2026_1t_$uf.zip"
    if [ ! -f "$z.ok" ]; then
      rm -f "$DEMO/$uf.json" "$DEMO/${uf}_municipios.json"
      agiu "$uf falhou no CRC: cache derivado invalidado, precisa rebaixar"
    fi
  done
fi

# 3. nenhum download em curso e UF faltando -> enfileira o resto
if ! pgrep -qf 'baixa_resiliente.sh'; then
  FALTA=""
  for uf in $TODAS; do
    [ -f "$AC1/bu_imgbu_logjez_rdv_vscmr_2026_1t_$uf.zip.ok" ] || FALTA="$FALTA $uf"
  done
  if [ -n "$FALTA" ]; then
    nohup "$PL/baixa_resiliente.sh" $FALTA >/dev/null 2>&1 &
    agiu "acervo incompleto e nenhum download ativo — enfileirei:$FALTA"
  fi
fi

# 4. download empacado: acervo no mesmo tamanho por 3 ciclos seguidos.
#    Encerra so o curl daquele download; o while do baixa_resiliente.sh retoma.
ULT="$P/.destrava_bytes"
TAM=$(ls -l "$AC1"/*.zip 2>/dev/null | awk '{s+=$5} END{print s+0}')
if [ -f "$ULT" ] && [ "$(cat "$ULT")" = "$TAM" ] && pgrep -qf 'baixa_resiliente.sh'; then
  C=$(cat "$P/.destrava_empaca" 2>/dev/null || echo 0); C=$((C+1))
  echo "$C" > "$P/.destrava_empaca"
  if [ "$C" -ge 3 ]; then
    for pid in $(pgrep -f 'curl.*arqurnatot' 2>/dev/null); do kill "$pid" 2>/dev/null; done
    agiu "download sem avanço em $C ciclos — encerrei o curl para o script retomar"
    echo 0 > "$P/.destrava_empaca"
  fi
else
  echo 0 > "$P/.destrava_empaca"
fi
echo "$TAM" > "$ULT"

# 5. UF integra sem bloco processado -> processa
PEND=""
for uf in $TODAS; do
  [ -f "$AC1/bu_imgbu_logjez_rdv_vscmr_2026_1t_$uf.zip.ok" ] || continue
  { [ -f "$DEMO/$uf.json" ] && [ -f "$DEMO/${uf}_municipios.json" ]; } || PEND="$PEND $uf"
done
if [ -n "$PEND" ] && ! pgrep -qf "$PL/demonstra.py"; then
  nohup "$PY" -u "$PL/demonstra.py" >> "$PL/demonstra_v4.log" 2>&1 &
  agiu "UF íntegra sem bloco ($PEND) — demonstra.py relançado"
fi

# 6. analises.json vazio com dados disponiveis -> roda
if [ -f "$PL/analises.json" ] && ! pgrep -qf "$PL/analises.py"; then
  VAZIO=$("$PY" -c "import json;print(1 if not json.load(open('$PL/analises.json')).get('blocos') else 0)" 2>/dev/null || echo 0)
  if [ "$VAZIO" = "1" ] && [ -n "$(ls "$DEMO"/*_municipios.json 2>/dev/null)" ]; then
    "$PY" -u "$PL/analises.py" >> "$PL/analises.log" 2>&1 && agiu "analises.py rodado (analises.json estava vazio)"
  fi
fi

# 7. bloco novo que o site ainda nao reflete -> publica
if ! pgrep -qf "publica_parcial.sh|$PL/demonstra.py"; then
  if [ ! -f "$P/repo/site/estados/index.html" ]; then
    "$PL/publica_parcial.sh" >> "$PL/parcial.log" 2>&1 && agiu "site publicado pela primeira vez"
  elif [ -n "$(find "$DEMO" -name '*_municipios.json' -newer "$P/repo/site/estados/index.html" 2>/dev/null | head -1)" ]; then
    "$PL/publica_parcial.sh" >> "$PL/parcial.log" 2>&1 && agiu "site republicado (bloco novo disponível)"
  fi
fi

# 8. vigia/pipeline caiu do launchd -> recarrega
for j in com.maneco.vigia-tse-2t com.maneco.pipeline-tse-2t com.maneco.destrava-tse; do
  if ! launchctl list 2>/dev/null | grep -q "$j"; then
    launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/$j.plist" 2>/dev/null \
      && agiu "$j recarregado no launchd"
  fi
done

# 9. vigia mudo por mais de 2h -> algo o travou, escala
if [ -f "$P/vigia/vigia.log" ]; then
  IDADE=$(( ( $(date +%s) - $(stat -f %m "$P/vigia/vigia.log") ) / 60 ))
  [ "$IDADE" -gt 120 ] && ESCALA="$ESCALA vigia sem escrever há ${IDADE}min;"
fi

# 10. erro fora do catalogo conhecido -> escala
NOVOS=$(grep -h -iE 'traceback|AttributeError|KeyError|ValueError|DESISTI' \
        "$PL"/*.log 2>/dev/null | grep -v 'datetime.UTC' | tail -3)
[ -n "$NOVOS" ] && ESCALA="$ESCALA erro não catalogado: $(echo "$NOVOS" | head -1);"

log "resultado: agiu=$AGIU escala=${ESCALA:-nada}"

# ---- escalada: so quando o deterministico nao bastou ----
# Sem --permission-mode: as permissoes vem de .claude/settings.json, que o Maneco
# revisou. O deny de lá impede o agente de tocar no plano pre-registrado, no
# manifesto carimbado e em qualquer reescrita de historia publicada.
if [ -n "$ESCALA" ]; then
  log "ESCALANDO para o agente auditoria-tse"
  if command -v claude >/dev/null 2>&1; then
    claude -p "Use o agente auditoria-tse. O destrava.sh automático não resolveu: $ESCALA
Rode ./diagnostico.sh, ache a causa raiz, conserte, e publique se houver bloco novo. O diretório .claude/ é só leitura para você: NÃO tente editar o arquivo do agente nem o settings.json — em vez disso, termine o relato com a linha pronta para a tabela do §5 (sintoma | causa | conserto), que o Maneco aplica. Relate em no máximo 12 linhas." \
      >> "$P/destrava-agente.log" 2>&1 \
      && log "agente concluiu (ver destrava-agente.log)" || log "agente retornou erro"
  else
    log "claude CLI indisponível — escalada só por notificação"
  fi
  [ -f "$P/vigia/notifica.py" ] && "$PY" "$P/vigia/notifica.py" \
     "Auditoria TSE — intervenção necessária" "$ESCALA" >/dev/null 2>&1
fi
log "--- destrava fim ---"
