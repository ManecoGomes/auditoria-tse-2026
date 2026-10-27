#!/bin/bash
# Calcula sha512 (uma vez) dos ZIPs ja provados integros que ainda nao tem sidecar .sha512.local.
AC=/Volumes/SSD1TB/acervo-tse/2026-1t/originais
LOG=/Users/maneco/Claude/Projetos/eleição/pipeline/integridade.log
for z in "$AC"/bu_imgbu_logjez_rdv_vscmr_2026_1t_*.zip; do
  [ -f "$z.ok" ] || continue
  [ -f "$z.sha512.local" ] && [ -s "$z.sha512.local" ] && continue
  uf=$(echo "$z" | sed -E 's/.*_1t_([A-Z]{2})\.zip/\1/')
  nice -n 10 shasum -a 512 "$z" | awk '{print $1}' > "$z.sha512.local.tmp" && mv "$z.sha512.local.tmp" "$z.sha512.local"
  echo "$(date '+%F %T') $uf: sha512 calculado ($(cut -c1-16 "$z.sha512.local")…)" >> "$LOG"
done
echo "$(date '+%F %T') === fim sha512_backfill ===" >> "$LOG"
