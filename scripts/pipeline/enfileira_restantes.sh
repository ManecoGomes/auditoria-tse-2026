#!/bin/bash
# Espera o lote em curso terminar e baixa o resto do acervo, sequencialmente.
# MA e GO entram de novo porque falharam no testzip (sidecar .ok ausente).
cd "$(dirname "$0")"
while pgrep -f "baixa_resiliente.sh AC AL AM CE BA MG GO" >/dev/null; do sleep 60; done
echo "$(date '+%F %T') lote 1 terminou — iniciando lote 2" >> baixa_resiliente.log
./baixa_resiliente.sh MA MS MT PA PB PE PI PR RN RO RR SE TO RJ SC RS PR SP ZZ
echo "$(date '+%F %T') lote 2 terminou" >> baixa_resiliente.log
