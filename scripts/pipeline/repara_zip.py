#!/usr/bin/env python3
"""Repara um ZIP do acervo do TSE SEM rebaixar o arquivo inteiro.

Por que existe: o TSE nao publica hash, mas cada membro do ZIP tem CRC proprio,
e o CDN e consistente (ETag estavel, Range honrado — verificado em 2026-10-27).
Entao, quando testzip() falha, o certo nao e apagar 9,6 GB e recomecar — e:
  1. completar o arquivo se estiver TRUNCADO (Range a partir do tamanho atual);
  2. localizar os membros com CRC errado;
  3. rebaixar via Range exatamente os bytes desses membros e sobrescrever no lugar;
  4. reverificar. Repete ate limpar ou esgotar tentativas.
Se o diretorio central (fim do arquivo) estiver ilegivel, rebaixa o ultimo 1 MB
(onde ficam EOCD e ZIP64) antes de qualquer coisa.

uso: repara_zip.py <caminho.zip> [max_rodadas=4]
sai 0 = integro ao final; 1 = ainda corrompido; 2 = erro de rede/CDN.
"""
import os, sys, struct, zipfile, urllib.request, time

URL = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/{}"
LOG = os.path.expanduser("~/Claude/Projetos/eleição/pipeline/repara_zip.log")

def log(*a):
    s = time.strftime("%F %T ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(LOG, "a") as f: f.write(s + "\n")

def head(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=120) as r:
        return int(r.headers["Content-Length"]), r.headers.get("ETag")

def fetch_range(url, start, end, tentativas=5):
    """Bytes [start, end] inclusive, exigindo 206 e tamanho exato."""
    want = end - start + 1
    for t in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(req, timeout=300) as r:
                if r.status != 206:
                    raise IOError(f"esperava 206, veio {r.status}")
                data = r.read()
            if len(data) != want:
                raise IOError(f"range devolveu {len(data)} bytes, esperava {want}")
            return data
        except Exception as e:
            log(f"  range {start}-{end} tentativa {t+1}: {e}"); time.sleep(5 * (t + 1))
    return None

def membros_ruins(path):
    """Lista (offset_inicio, tamanho_total_no_arquivo, nome) dos membros com CRC errado."""
    ruins = []
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        for i in infos:
            try:
                with z.open(i) as f:
                    while f.read(1 << 20): pass
            except Exception as e:
                # local header = 30 bytes fixos + nome + extra; le o header real para medir
                with open(path, "rb") as fh:
                    fh.seek(i.header_offset); h = fh.read(30)
                    n, x = struct.unpack("<HH", h[26:30]) if len(h) == 30 else (0, 0)
                total = 30 + n + x + i.compress_size
                ruins.append((i.header_offset, total, i.filename, type(e).__name__))
    return ruins

def main():
    path = sys.argv[1]; rodadas = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    nome = os.path.basename(path); url = URL.format(nome)
    log(f"=== repara {nome} ===")
    try: esperado, etag = head(url)
    except Exception as e:
        log(f"HEAD falhou: {e}"); return 2
    log(f"CDN: {esperado:,} bytes, ETag {etag}")

    for rodada in range(1, rodadas + 1):
        tam = os.path.getsize(path) if os.path.exists(path) else 0
        # 1. truncado -> completar com Range a partir do que existe
        if tam < esperado:
            log(f"rodada {rodada}: TRUNCADO ({tam:,}/{esperado:,}, faltam {esperado-tam:,}) — completando")
            with open(path, "ab") as f:
                pos = tam
                while pos < esperado:
                    fim = min(pos + (64 << 20) - 1, esperado - 1)
                    data = fetch_range(url, pos, fim)
                    if data is None: log("falha de rede ao completar"); return 2
                    f.write(data); pos += len(data)
            tam = os.path.getsize(path)
        elif tam > esperado:
            log(f"rodada {rodada}: arquivo MAIOR que o CDN ({tam:,} > {esperado:,}) — truncando ao tamanho certo")
            with open(path, "r+b") as f: f.truncate(esperado)
            tam = esperado

        # 2. diretorio central legivel? se nao, rebaixa o ultimo 1 MB
        try:
            zipfile.ZipFile(path).close()
        except zipfile.BadZipFile:
            ini = max(0, tam - (1 << 20))
            log(f"rodada {rodada}: diretorio central ilegivel — rebaixando bytes {ini:,}-{tam-1:,}")
            data = fetch_range(url, ini, tam - 1)
            if data is None: return 2
            with open(path, "r+b") as f: f.seek(ini); f.write(data)
            try: zipfile.ZipFile(path).close()
            except zipfile.BadZipFile:
                log("diretorio central segue ilegivel apos rebaixar o fim — corrupcao mais ampla");
                # cai para a verificacao de membros na proxima rodada nao faz sentido; desiste desta rodada
                continue

        # 3. membros com CRC errado
        ruins = membros_ruins(path)
        if not ruins:
            log(f"rodada {rodada}: INTEGRO — testzip limpo"); return 0
        log(f"rodada {rodada}: {len(ruins)} membro(s) corrompido(s); rebaixando so esses bytes")
        for off, total, nm, err in ruins[:200]:
            data = fetch_range(url, off, off + total - 1)
            if data is None: log(f"  falha ao rebaixar {nm}"); return 2
            with open(path, "r+b") as f: f.seek(off); f.write(data)
            log(f"  reparado {nm} @ {off:,} ({total:,} bytes) [{err}]")
        if len(ruins) > 200:
            log(f"  {len(ruins)} membros ruins — corrupcao extensa; reparados 200, proxima rodada continua")
    log("esgotou rodadas sem limpar")
    return 1

if __name__ == "__main__":
    sys.exit(main())
