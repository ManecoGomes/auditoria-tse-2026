#!/bin/bash
# Criterio UNICO de integridade do acervo: sidecar <zip>.ok contendo o tamanho
# em bytes no momento em que zipfile.testzip() passou. Quem consome o acervo
# (demonstra.py) exige o sidecar, e assim nunca le um ZIP ainda em download.
ACERVO=/Volumes/SSD1TB/acervo-tse/2026-1t/originais
LOG=/Users/maneco/Claude/Projetos/eleição/pipeline/integridade.log
PY=/opt/homebrew/bin/python3
log(){ echo "$(date '+%F %T') $*" >>"$LOG"; }
for z in "$ACERVO"/bu_imgbu_logjez_rdv_vscmr_2026_1t_*.zip; do
  [ -f "$z" ] || continue
  uf=$(echo "$z" | sed -E 's/.*_1t_([A-Z]{2})\.zip/\1/')
  [ -n "$1" ] && ! echo " $* " | grep -q " $uf " && continue
  tam=$(stat -f %z "$z")
  if [ -f "$z.ok" ] && [ "$(cat "$z.ok")" = "$tam" ]; then log "$uf: ja marcado ($tam bytes)"; continue; fi
  sleep 5; tam2=$(stat -f %z "$z")
  if [ "$tam" != "$tam2" ]; then log "$uf: ainda crescendo ($tam -> $tam2) — nao marcado"; continue; fi
  if nice -n 10 "$PY" -c "import zipfile,sys; sys.exit(0 if zipfile.ZipFile('$z').testzip() is None else 1)" 2>/dev/null; then
    echo "$tam" > "$z.ok"; log "$uf: testzip OK — sidecar gravado ($tam bytes)"
  else
    rm -f "$z.ok"; log "$uf: testzip FALHOU — segue sem sidecar, sera rebaixado"
  fi
done
log "=== fim marca_integros ${*:-todos} ==="
