#!/bin/bash
# Baixa ZIPs de log de urna com retomada ilimitada e verificacao de integridade.
# O TSE nao publica hash desses arquivos (404), entao a prova e o proprio ZIP abrir inteiro.
# Sequencial de proposito: nao competir por banda com outro download.
ACERVO=/Volumes/SSD1TB/acervo-tse/2026-1t/originais
URL=https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/bu_imgbu_logjez_rdv_vscmr_2026_1t_%s.zip
LOG=/Users/maneco/Claude/Projetos/eleição/pipeline/baixa_resiliente.log
PY=/opt/homebrew/bin/python3
PASSES=${PASSES:-4}
mkdir -p "$ACERVO"
log(){ echo "$(date '+%F %T') $*" >>"$LOG"; }

for uf in "$@"; do
  u=$(printf "$URL" "$uf"); z="$ACERVO/bu_imgbu_logjez_rdv_vscmr_2026_1t_$uf.zip"
  esperado=$(curl -sI -m 60 "$u" | awk 'BEGIN{IGNORECASE=1}/^content-length:/{gsub(/\r/,"");print $2}' | tail -1)
  [ -z "$esperado" ] && { log "$uf: sem Content-Length, pulando"; continue; }
  log "$uf: alvo $esperado bytes"
  echo "$esperado" > "$z.esperado"   # permite distinguir TRUNCADO de CORROMPIDO
  ok=0
  for passe in $(seq 1 "$PASSES"); do
    # 1. completa o arquivo, retomando quantas vezes precisar
    t=0
    while :; do
      atual=$(stat -f %z "$z" 2>/dev/null || echo 0)
      [ "$atual" -ge "$esperado" ] && break
      t=$((t+1))
      # --limit-rate: o SSD externo e USB; a 25 MB/s de escrita as leituras de diretorio
      # param (demonstra.py ficou 7 min preso em opendir em 2026-10-27 12:25). 15 MB/s
      # deixa folga para o publicador ler o acervo enquanto o download corre.
      # Sem --retry interno: ao "retry", o curl TRUNCA o arquivo ao tamanho de quando a
      # chamada comecou e perde o que baixou (observado 2026-10-27: tamanho caindo entre
      # tentativas, 1,7 GB/h efetivos com teto de 15 MB/s). O while acima ja repete, e cada
      # chamada nova retoma do tamanho real do arquivo (-C -).
      curl -sL -C - --speed-time 120 --speed-limit 10240 --limit-rate "${LIMITE:-20M}" -o "$z" "$u"
      novo=$(stat -f %z "$z" 2>/dev/null || echo 0)
      log "$uf: passe $passe tentativa $t -> $novo/$esperado ($((novo*100/esperado))%)"
      [ "$novo" -ge "$esperado" ] && break
      [ "$novo" -le "$atual" ] && sleep 20   # sem avanco: respira antes de insistir
    done
    # 2. prova de integridade
    if "$PY" -c "import zipfile,sys; sys.exit(0 if zipfile.ZipFile('$z').testzip() is None else 1)" 2>/dev/null; then
      stat -f %z "$z" > "$z.ok"; rm -f "$z.bad"
      nice -n 10 shasum -a 512 "$z" | awk '{print $1}' > "$z.sha512.local"
      log "$uf: COMPLETO e ZIP integro ($(stat -f %z "$z") bytes, passe $passe) — sidecar .ok gravado"; ok=1; break
    fi
    # ZIP completo mas com CRC errado: o CDN e consistente (ETag estavel, Range 206),
    # entao rebaixa SO os membros ruins em vez de jogar GBs fora (repara_zip.py).
    log "$uf: passe $passe baixou 100% mas o ZIP nao abre inteiro — tentando reparo por Range"
    if "$PY" -u "$(dirname "$0")/repara_zip.py" "$z" 40 >> "$LOG" 2>&1; then
      stat -f %z "$z" > "$z.ok"; rm -f "$z.bad" "$z.truncado"
      nice -n 10 shasum -a 512 "$z" | awk '{print $1}' > "$z.sha512.local"
      log "$uf: REPARADO em lugar e integro ($(stat -f %z "$z") bytes) — sidecar .ok gravado"; ok=1; break
    fi
    log "$uf: reparo nao bastou — descartando e refazendo do zero"
    rm -f "$z" "$z.ok" "$z.bad" "$z.truncado"
    sleep 30
  done
  [ "$ok" = 1 ] || log "$uf: DESISTI apos $PASSES passes — CDN entregando dados corrompidos"
done
log "=== fim: $* ==="
