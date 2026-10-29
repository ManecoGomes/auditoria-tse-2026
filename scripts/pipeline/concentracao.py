#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Perfil horário de cada seção (base do teste K — concentração por horário × resultado).

uso: concentracao.py <turno 1|2> [UF ...]      WORKERS=3

Emenda de 28/10/2026 (posterior ao plano). Para cada seção, a partir dos registros
«Voto confirmado para [Presidente]» do dia do pleito (hora de Brasília):
  votos por hora (07h..19h, 13 faixas), votos de 17h em diante, maior contagem num bloco
  de 10 min e o rótulo desse bloco, número de blocos de 10 min com voto, e o índice de
  rajada = maior bloco de 10 min / média dos blocos com voto.
Saída: /Volumes/SSD1TB/acervo-tse/auditoria/concentracao/{t}t/{UF}.json
"""
import collections, datetime, io, json, multiprocessing as mp, os, re, signal, sys, time, zipfile

VERSAO = 1
T = sys.argv[1]
UFS_ARG = [u.upper() for u in sys.argv[2:]]
WORKERS = int(os.environ.get("WORKERS", "2"))   # 2: CPU a 100 °C com 3+3 em 28/10; a ponte USB é o gargalo
AC = f"/Volumes/SSD1TB/acervo-tse/2026-{T}t"
OUTD = f"/Volumes/SSD1TB/acervo-tse/auditoria/concentracao/{T}t"
os.makedirs(OUTD, exist_ok=True)
PLEITO = {"1": b"04/10/2026", "2": b"25/10/2026"}[T]
TODAS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()
OFF = {"AC": 2, "AM": 1, "MT": 1, "MS": 1, "RO": 1, "RR": 1}
VOTO = re.compile(rb"^" + PLEITO + rb" (\d\d):(\d\d):\d\d\t[^\n]*Voto confirmado para \[Presidente\]", re.M)
HORAS = list(range(7, 20))   # 07h..19h; antes de 7h e depois de 19h caem nas pontas


def membros(uf):
    z = f"{AC}/originais/bu_imgbu_logjez_rdv_vscmr_2026_{T}t_{uf}.zip"
    solto = f"{AC}/secoes/{uf}"
    try:
        zf = zipfile.ZipFile(z); nomes = sorted(zf.namelist()); fonte = "zip"
    except Exception as e:
        zf = None; fonte = f"zip_invalido:{e}"
        reg = f"{AC}/registro_secoes_{uf}.json"
        if not os.path.exists(reg): raise
        nomes = sorted(n for r in json.load(open(reg))["secoes"] if "arquivos" in r
                       for n in r["arquivos"] if n not in r.get("faltam", []))
    falhas = 0
    for n in nomes:
        if not (n.startswith("o") and n.endswith("-log.jez")): continue
        b = None
        if zf is not None:
            try: b = zf.read(n)
            except Exception: b = None; falhas += 1
        if b is None and os.path.exists(f"{solto}/{n}"):
            try: b = open(f"{solto}/{n}", "rb").read()
            except Exception: b = None
        if b is None: continue
        yield n, b
    if zf: zf.close()
    membros.fonte = fonte; membros.falhas = falhas


def chave(nome):
    r = nome.split("-")[0][8:]
    return (int(r[0:5]), int(r[5:9]), int(r[9:]))


def processa(uf):
    t0 = time.time()
    out = f"{OUTD}/{uf}.json"
    if os.path.exists(out):
        try:
            if json.load(open(out)).get("versao") == VERSAO: return uf, "cache"
        except Exception: pass
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("watchdog 4h")))
    signal.alarm(4 * 3600)
    off = OFF.get(uf, 0)
    linhas = []; n_sec = 0; hora_uf = collections.Counter(); bins_uf = collections.Counter()
    for nome, b in membros(uf):
        try:
            with zipfile.ZipFile(io.BytesIO(b)) as inn: d = inn.read("logd.dat")
        except Exception:
            continue
        n_sec += 1
        try: mun, zona, sec = chave(nome)
        except Exception: mun = zona = sec = None
        hm = [((int(h) + off) % 24, int(m)) for h, m in VOTO.findall(d)]
        n = len(hm)
        horas = [0] * len(HORAS)
        b10 = collections.Counter()
        for h, m in hm:
            idx = min(max(h, HORAS[0]), HORAS[-1]) - HORAS[0]
            horas[idx] += 1
            b10[h * 6 + m // 10] += 1
        for h, v in zip(HORAS, horas): hora_uf[h] += v
        for k, v in b10.items(): bins_uf[k] += v
        apos17 = sum(1 for h, m in hm if h >= 17)
        if b10:
            kmax, vmax = max(b10.items(), key=lambda kv: kv[1])
            ativos = len(b10); rajada = round(vmax / (n / ativos), 3)
            rot = f"{kmax // 6:02d}:{(kmax % 6) * 10:02d}"
        else:
            vmax = 0; ativos = 0; rajada = None; rot = None
        linhas.append([mun, zona, sec, n, apos17, vmax, rot, ativos, rajada] + horas)
    res = {"uf": uf, "turno": T, "versao": VERSAO, "gerado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "secoes": n_sec, "fonte": membros.fonte, "membros_falhos": membros.falhas,
           "colunas": ["municipio", "zona", "secao", "votos", "apos17h", "max_bloco10min", "bloco_max", "blocos_ativos", "rajada"] + [f"h{h:02d}" for h in HORAS],
           "votos_por_hora": {str(h): hora_uf[h] for h in HORAS}, "votos_por_bloco10": {f"{k // 6:02d}:{(k % 6) * 10:02d}": v for k, v in sorted(bins_uf.items())},
           "linhas": linhas, "segundos": round(time.time() - t0)}
    tmp = out + ".tmp"
    json.dump(res, open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, out)
    return uf, f"ok {n_sec} secoes {round(time.time() - t0)}s"


if __name__ == "__main__":
    ufs = UFS_ARG or TODAS
    print(f"concentracao {T}T: {len(ufs)} UFs, {WORKERS} workers", flush=True)
    if WORKERS <= 1:
        for u in ufs: print(*processa(u), flush=True)
    else:
        with mp.Pool(WORKERS) as pool:
            for u, r in pool.imap_unordered(processa, ufs): print(u, r, flush=True)
    print("CONCENTRACAO_CONCLUIDO", flush=True)
