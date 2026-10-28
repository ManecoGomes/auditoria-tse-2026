#!/usr/bin/env python3
"""Remonta o ZIP do 2T de uma UF a partir dos arquivos soltos em secoes/{UF} (coletados do Portal
Resultados), com .ok SOMENTE se zipfile.testzip() passar. uso: remonta_2t.py UF [UF ...]
Motivo: em 27/10 cinco ZIPs remontados (AM BA ES MG SE) sairam com diretorio central ou CRC ruins
e receberam .ok mesmo assim (coleta_secoes.py nao testava). Escrita grande no volume externo."""
import sys, os, json, zipfile, hashlib, datetime, time
AC = "/Volumes/SSD1TB/acervo-tse/2026-2t"; ORIG = f"{AC}/originais"; SEC = f"{AC}/secoes"
def log(*a):
    print(datetime.datetime.now().strftime("%F %T"), *a, flush=True)
for uf in [u.upper() for u in sys.argv[1:]]:
    t0 = time.time()
    reg = json.load(open(f"{AC}/registro_secoes_{uf}.json"))["secoes"]
    nomes = sorted(n for r in reg if "arquivos" in r for n in r["arquivos"] if n not in r.get("faltam", []))
    z = f"{ORIG}/bu_imgbu_logjez_rdv_vscmr_2026_2t_{uf}.zip"; tmp = z + ".parte"
    log(f"{uf}: {len(nomes)} membros — escrevendo {os.path.basename(z)}")
    for s in (".ok", ".bad"):
        try: os.remove(z + s)
        except FileNotFoundError: pass
    falt = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
        for n in nomes:
            p = f"{SEC}/{uf}/{n}"
            if not os.path.exists(p): falt += 1; continue
            zf.write(p, n)
    os.replace(tmp, z); tam = os.path.getsize(z)
    open(z + ".esperado", "w").write(str(tam))
    log(f"{uf}: {tam:,} bytes, {falt} soltos faltantes; testzip…")
    try: ruim = zipfile.ZipFile(z).testzip()
    except Exception as e: ruim = str(e)
    if ruim is None:
        h = hashlib.sha512()
        with open(z, "rb") as f:
            for b in iter(lambda: f.read(1 << 22), b""): h.update(b)
        open(z + ".sha512.local", "w").write(h.hexdigest() + "  " + os.path.basename(z) + "\n")
        open(z + ".ok", "w").write(str(tam))
        open(z + ".fonte", "a").write(f"remontado de novo em {datetime.datetime.now(datetime.timezone.utc).isoformat()} (testzip OK, {len(nomes)-falt} membros)\n")
        log(f"{uf}: OK em {time.time()-t0:.0f}s — sidecar .ok gravado")
    else:
        open(z + ".bad", "w").write(str(tam)); log(f"{uf}: FALHOU no testzip ({ruim}) — .bad")
