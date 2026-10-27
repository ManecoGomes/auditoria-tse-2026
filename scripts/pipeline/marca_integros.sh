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
  # tamanho esperado: sidecar .esperado (gravado pelo downloader) ou HEAD no CDN
  esp=$(cat "$z.esperado" 2>/dev/null)
  [ -z "$esp" ] && esp=$(curl -sI -m 60 "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/$(basename "$z")" | awk 'BEGIN{IGNORECASE=1}/^content-length:/{gsub(/\r/,"");print $2}' | tail -1) && [ -n "$esp" ] && echo "$esp" > "$z.esperado"
  if [ -n "$esp" ] && [ "$tam" -lt "$esp" ]; then
    rm -f "$z.ok" "$z.bad"; echo "$tam" > "$z.truncado"
    log "$uf: TRUNCADO ($tam de $esp bytes, $((100*tam/esp))%) — nao e corrupcao; o downloader completa"; continue
  fi
  if nice -n 10 "$PY" -c "import zipfile,sys; sys.exit(0 if zipfile.ZipFile('$z').testzip() is None else 1)" 2>/dev/null; then
    echo "$tam" > "$z.ok"; rm -f "$z.bad" "$z.truncado"
    nice -n 10 shasum -a 512 "$z" | awk '{print $1}' > "$z.sha512.local"
    log "$uf: testzip OK — sidecar gravado ($tam bytes), sha512 em $z.sha512.local"
  else
    rm -f "$z.ok"; echo "$tam" > "$z.bad"
    log "$uf: testzip FALHOU — marcado .bad em $tam bytes, sera rebaixado"
  fi
done
log "=== fim marca_integros ${*:-todos} ==="
