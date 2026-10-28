#!/usr/bin/env python3
"""Coleta os arquivos de urna POR SECAO no Portal Resultados do TSE e remonta, por UF,
o mesmo ZIP que o portal de dados abertos publica dias depois
(bu_imgbu_logjez_rdv_vscmr_2026_{t}t_{UF}.zip, membros o0{pleito}{uf}{mun}{zona}{secao}-*.{bu.dat,log.jez,rdv.dat,vota.vsc}).

Por que: o ZIP consolidado nao tem prazo normativo (2022/2024: 2-3 dias); os arquivos por secao
ficam publicos no Portal Resultados assim que a secao e totalizada (comprovado 2026-10-27, 2T).

uso: coleta_secoes.py <turno 1|2> [UF ...]        (sem UF: todas, da menor para a maior)
     THREADS=64 (paralelismo), SO_LOG=0/1 (1 = so log+bu, deixa rdv/vota para depois)

Saida: {ACERVO}/secoes/{uf}/{arquivos}, {ACERVO}/secoes/{uf}/aux/*.json,
       {ACERVO}/originais/bu_imgbu_logjez_rdv_vscmr_2026_{t}t_{UF}.zip (+ .ok, .esperado, .sha512.local)
       {ACERVO}/registro_secoes_{UF}.json (hash/dr/hr/st de cada secao, faltantes)
Idempotente: pula arquivo que ja existe e abre; refaz ZIP se a lista de secoes mudou.
"""
import concurrent.futures as cf, hashlib, io, json, os, subprocess, sys, time, zipfile, datetime, collections

T = sys.argv[1] if len(sys.argv) > 1 else "2"
PLEITO = {"1": "3220", "2": "3221"}[T]
UFS_ARG = [u.upper() for u in sys.argv[2:]]
ACERVO = f"/Volumes/SSD1TB/acervo-tse/2026-{T}t"
ORIG = f"{ACERVO}/originais"; SEC = f"{ACERVO}/secoes"
BASE = f"https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/{PLEITO}"
UA = "Mozilla/5.0 auditoria-tse-2026 (manecogomes@gmail.com)"
THREADS = int(os.environ.get("THREADS", "64"))
SO_LOG = os.environ.get("SO_LOG", "0") == "1"
LOG = os.path.expanduser(f"~/Claude/Projetos/eleição/pipeline/coleta_secoes_{T}t.log")
ORDEM = ["RR","AP","AC","TO","RO","SE","MS","DF","AM","AL","ES","PI","RN","MT","PB","CE","MA",
         "PA","GO","PE","SC","PR","RS","RJ","BA","MG","SP","ZZ"]
os.makedirs(ORIG, exist_ok=True); os.makedirs(SEC, exist_ok=True)

def log(*a):
    s = f"{datetime.datetime.now():%F %T} " + " ".join(str(x) for x in a)
    print(s, flush=True); open(LOG, "a").write(s + "\n")

def curl(url, dest=None, tent=4):
    """GET com retries; devolve bytes (ou True se gravou em dest). None se falhou."""
    for i in range(tent):
        args = ["curl", "-s", "-m", "90", "-A", UA, "-w", "%{http_code}", url]
        args += ["-o", dest] if dest else ["-o", "-"]
        r = subprocess.run(args, capture_output=True)
        code = r.stdout[-3:].decode(errors="ignore") if dest else r.stdout[-3:].decode(errors="ignore")
        if code == "200":
            return True if dest else r.stdout[:-3]
        if code == "404":
            return None          # nao insistir: 404 em serie bloqueia o IP
        time.sleep(2 * (i + 1))
    return None

def secoes_da_uf(uf):
    j = curl(f"{BASE}/config/{uf.lower()}/{uf.lower()}-p00{PLEITO}-cs.json")
    if not j: return None
    d = json.loads(j); out = []
    for a in d["abr"]:
        for m in a["mu"]:
            for z in m["zon"]:
                for s in z["sec"]:
                    out.append((str(m["cd"]).zfill(5), str(z["cd"]).zfill(4), str(s["ns"]).zfill(4), s.get("da"), s.get("ha")))
    return out

def abre_ok(p):
    """Arquivo existe e e utilizavel (jez/zip abre; demais: tamanho > 0)."""
    if not os.path.exists(p) or os.path.getsize(p) == 0: return False
    if p.endswith(".jez"):
        try: return zipfile.ZipFile(p).testzip() is None
        except Exception: return False
    return True

def baixa_secao(uf, mun, zon, ns):
    u = uf.lower(); d = f"{SEC}/{uf}"; da = f"{d}/aux"
    auxp = f"{da}/p00{PLEITO}-{u}-m{mun}-z{zon}-s{ns}-aux.json"
    if not os.path.exists(auxp):
        j = curl(f"{BASE}/dados/{u}/{mun}/{zon}/{ns}/p00{PLEITO}-{u}-m{mun}-z{zon}-s{ns}-aux.json")
        if not j: return {"sec": f"{mun}-{zon}-{ns}", "erro": "aux"}
        open(auxp, "wb").write(j)
    try: aux = json.load(open(auxp))
    except Exception:
        os.remove(auxp); return {"sec": f"{mun}-{zon}-{ns}", "erro": "aux-json"}
    hs = aux.get("hashes") or []
    if not hs: return {"sec": f"{mun}-{zon}-{ns}", "erro": "sem-hash", "st": aux.get("st")}
    h = hs[-1]; arqs = [a["nm"] for a in h.get("arq", [])]
    if SO_LOG: arqs = [a for a in arqs if a.endswith("-log.jez") or a.endswith("-bu.dat")]
    falt = []
    for nm in arqs:
        p = f"{d}/{nm}"
        if abre_ok(p): continue
        ok = curl(f"{BASE}/dados/{u}/{mun}/{zon}/{ns}/{h['hash']}/{nm}", dest=p)
        if not ok or not abre_ok(p):
            if os.path.exists(p): os.remove(p)
            falt.append(nm)
    return {"sec": f"{mun}-{zon}-{ns}", "hash": h["hash"], "dr": h.get("dr"), "hr": h.get("hr"),
            "st": h.get("st"), "st_secao": aux.get("st"), "arquivos": arqs, "faltam": falt}

def monta_zip(uf, reg):
    z = f"{ORIG}/bu_imgbu_logjez_rdv_vscmr_2026_{T}t_{uf}.zip"
    d = f"{SEC}/{uf}"
    nomes = sorted(n for r in reg if "arquivos" in r for n in r["arquivos"] if n not in r["faltam"])
    tmp = z + ".parte"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as zf:
        for n in nomes: zf.write(f"{d}/{n}", n)
    os.replace(tmp, z)
    tam = os.path.getsize(z)
    open(z + ".esperado", "w").write(str(tam))
    # .ok so depois de testzip() passar: em 27/10 cinco ZIPs remontados (AM BA ES MG SE) sairam
    # com diretorio central ou CRC ruins e levaram .ok mesmo assim (regressao vista em 28/10).
    for s in (".ok", ".bad"):
        try: os.remove(z + s)
        except FileNotFoundError: pass
    try: ruim = zipfile.ZipFile(z).testzip()
    except Exception as e: ruim = str(e)
    if ruim is None: open(z + ".ok", "w").write(str(tam))
    else:
        open(z + ".bad", "w").write(str(tam)); log(f"{uf}: ZIP remontado FALHOU no testzip ({ruim}) — sidecar .bad")
    h = hashlib.sha512()
    with open(z, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""): h.update(b)
    open(z + ".sha512.local", "w").write(h.hexdigest() + "  " + os.path.basename(z) + "\n")
    open(f"{ORIG}/{os.path.basename(z)}.fonte", "w").write(
        f"remontado a partir do Portal Resultados ({BASE}) em {datetime.datetime.now(datetime.timezone.utc).isoformat()}; "
        f"{len(nomes)} membros; membro a membro identico ao que o portal de dados abertos publica (conferir quando sair)\n")
    return z, tam, len(nomes)

def processa_uf(uf):
    t0 = time.time()
    secs = secoes_da_uf(uf)
    if secs is None: log(f"{uf}: cs.json indisponivel — pulando"); return
    os.makedirs(f"{SEC}/{uf}/aux", exist_ok=True)
    log(f"{uf}: {len(secs)} secoes no cs.json — baixando com {THREADS} threads")
    reg = []; feitas = 0
    with cf.ThreadPoolExecutor(THREADS) as ex:
        for r in ex.map(lambda s: baixa_secao(uf, s[0], s[1], s[2]), secs):
            reg.append(r); feitas += 1
            if feitas % 2000 == 0: log(f"  {uf} {feitas}/{len(secs)} ({time.time()-t0:.0f}s)")
    erros = [r for r in reg if "erro" in r]; falt = sum(len(r.get("faltam", [])) for r in reg)
    st = collections.Counter(r.get("st") for r in reg)
    log(f"{uf}: {len(reg)} secoes | erros de aux: {len(erros)} | arquivos faltantes: {falt} | status: {dict(st)}")
    json.dump({"uf": uf, "turno": T, "pleito": PLEITO, "fonte": BASE, "n": len(reg),
               "coletado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "erros_aux": erros[:500], "secoes": reg}, open(f"{ACERVO}/registro_secoes_{uf}.json", "w"))
    if erros or falt:
        log(f"{uf}: incompleta ({len(erros)} aux, {falt} arquivos) — ZIP montado mesmo assim; rode de novo para completar")
    z, tam, n = monta_zip(uf, reg)
    log(f"{uf}: ZIP remontado {os.path.basename(z)} ({tam:,} bytes, {n} membros) em {time.time()-t0:.0f}s — sidecar .ok gravado")

ufs = UFS_ARG or ORDEM
log(f"=== coleta por secao: turno {T} (pleito {PLEITO}) UFs: {' '.join(ufs)} ===")
for uf in ufs:
    try: processa_uf(uf)
    except Exception as e: log(f"{uf}: FALHOU ({type(e).__name__}: {e})")
log("=== fim ===")
