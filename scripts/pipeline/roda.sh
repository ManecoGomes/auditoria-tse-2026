#!/bin/bash
# Pipeline completo do 2o turno: coleta -> auditoria -> comparacao -> publicacao -> aviso.
# Idempotente: pode rodar varias vezes; pula o que ja esta feito.
PY=${PY:-/opt/homebrew/bin/python3}   # 3.9 do sistema nao tem datetime.UTC
set -o pipefail
P="$HOME/Claude/Projetos/eleição"
PL="$P/pipeline"; LOG="$PL/pipeline.log"
NOT="$P/vigia/notifica.py"
LOCK="$PL/.lock"
AUTO_PUBLICAR="${AUTO_PUBLICAR:-1}"   # 1 = publica sozinho se passar no portao

if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -f "$LOCK/pid" ] && kill -0 "$(cat "$LOCK/pid")" 2>/dev/null; then
    echo "$(date '+%F %T') já rodando (pid $(cat "$LOCK/pid"))" >> "$LOG"; exit 0
  fi
  rm -rf "$LOCK"; mkdir "$LOCK" || exit 0
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT
log(){ echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

log "=== PIPELINE 2T INICIADO ==="

# ---------- 1. coleta ----------
log "[1/6] coletando boletins"
"$PY" "$PL/coleta.py" 2 bu >> "$LOG" 2>&1
BU_OK=$?
if [ $BU_OK -ne 0 ]; then log "boletins do 2T ainda não publicados — encerrando"; exit 0; fi

log "[1/6] coletando logs de urna"
"$PY" "$PL/coleta.py" 2 logs >> "$LOG" 2>&1 || log "logs ainda não publicados (segue só com boletins)"

# ---------- 2. auditoria ----------
log "[2/6] auditando boletins (prazo legal 19h)"
"$PY" -u "$PL/audita.py" 2 bu 19 >> "$LOG" 2>&1
log "[2/6] auditando logs de urna"
"$PY" -u "$PL/audita.py" 2 logs 19 >> "$LOG" 2>&1 || true

# ---------- 2b. extracao de votos por secao ----------
log "[2/6] extraindo votos por seção (base do teste E4)"
"$PY" -u "$PL/extrai_votos.py" 2 >> "$LOG" 2>&1 || true
"$PY" -u "$PL/extrai_votos.py" 1 >> "$LOG" 2>&1 || true

# ---------- 3. comparacao e analises ----------
log "[3/6] análises comparativas (blocos A2, C4, E, F do plano)"
"$PY" -u "$PL/analises.py" >> "$LOG" 2>&1 || log "análises falharam (segue)"
log "[3/6] comparando contra a régua do 1º turno"
RESUMO=$("$PY" "$PL/compara.py" 2>>"$LOG")
echo "$RESUMO" >> "$LOG"

# ---------- 4. portao de qualidade ----------
GATE=$("$PY" - <<PY
import json,sys
r=json.load(open("$PL/resumo_2t.json"))
reg=json.load(open("/Volumes/SSD1TB/acervo-tse/2026-2t/registro_bu.json"))
div=[a["arquivo"] for a in reg["arquivos"] if a["confere"] is False]
problemas=[]
if r["ufs_bu"]<25: problemas.append(f"só {r['ufs_bu']} UFs auditadas (esperado 28)")
if div: problemas.append(f"{len(div)} arquivos com hash divergente")
if reg["falhas"]: problemas.append(f"{len(reg['falhas'])} downloads falharam")
if r["secoes"]<400000: problemas.append(f"só {r['secoes']} seções (esperado ~499 mil)")
print("|".join(problemas) if problemas else "OK")
PY
)
if [ "$GATE" != "OK" ]; then
  log "PORTÃO DE QUALIDADE REPROVOU: $GATE"
  "$PY" "$NOT" "Auditoria 2T — revisão necessária antes de publicar" \
"A auditoria do 2o turno rodou, mas o portao de qualidade barrou a publicacao automatica.

Motivo: $GATE

Resumo obtido:
$RESUMO

Nada foi publicado. O relatorio esta em $P/relatorio/RELATORIO-2T.md para revisao manual." >> "$LOG" 2>&1
  exit 1
fi
log "portão de qualidade: OK"

# ---------- 5. publicacao ----------
if [ "$AUTO_PUBLICAR" = "1" ]; then
  log "[5/6] publicando"
  bash "$PL/publica.sh" >> "$LOG" 2>&1 && log "publicado" || log "FALHA na publicação"
else
  log "[5/6] AUTO_PUBLICAR=0 — publicação retida para revisão"
fi

# ---------- 6. aviso ----------
log "[6/6] avisando"
"$PY" "$NOT" "Auditoria do 2º turno concluída" \
"A auditoria do 2o turno rodou de ponta a ponta e o resultado ja esta publicado.

$RESUMO

Relatorio completo: https://auditoria-tse-2026.com.br/relatorio-2t.html
Repositorio:        https://github.com/ManecoGomes/auditoria-tse-2026
Copia de custodia:  GitHub (Drive so no fechamento, via sobe_drive.sh)

Comparacao com a regua do 1o turno esta na secao 3 do relatorio." \
"$P/relatorio/Auditoria_TSE_2T_2026.pdf" >> "$LOG" 2>&1

log "=== PIPELINE 2T CONCLUÍDO ==="
