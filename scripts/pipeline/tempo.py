#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estrutura temporal dos votos no log (base dos testes K6/K7 — "eventos com tempo determinado,
repetições, periodicidade"). Emenda de 28/10/2026, posterior ao plano.

uso: tempo.py <turno 1|2> [UF ...]      WORKERS=2

Para cada UF, a partir de «Voto confirmado para [Presidente]» do dia do pleito (hora local da urna):
  - contagem nacional de votos por SEGUNDO do dia (86.400 posições) — espectro/periodicidade;
  - histograma do segundo dentro do minuto (0–59) e do minuto dentro da hora (0–59) — uniformidade;
  - por seção: assinatura dos primeiros 40 intervalos (hash) e dos últimos 40 — repetição entre urnas;
  - por seção: maior pausa (s) entre votos consecutivos dentro do dia e a hora em que ocorreu;
  - por seção: número de intervalos exatamente iguais ao anterior em sequência (corrida de intervalos
    idênticos, o que um gerador programado produz e um eleitor não).
Saída: /Volumes/SSD1TB/acervo-tse/auditoria/tempo/{t}t/{UF}.json
"""
import collections, datetime, hashlib, io, json, multiprocessing as mp, os, re, signal, sys, time, zipfile

VERSAO = 1
T = sys.argv[1]
UFS_ARG = [u.upper() for u in sys.argv[2:]]
WORKERS = int(os.environ.get("WORKERS", "2"))
AC = f"/Volumes/SSD1TB/acervo-tse/2026-{T}t"
OUTD = f"/Volumes/SSD1TB/acervo-tse/auditoria/tempo/{T}t"
os.makedirs(OUTD, exist_ok=True)
PLEITO = {"1": b"04/10/2026", "2": b"25/10/2026"}[T]
TODAS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()
OFF = {"AC": 2, "AM": 1, "MT": 1, "MS": 1, "RO": 1, "RR": 1}
VOTO = re.compile(rb"^" + PLEITO + rb" (\d\d):(\d\d):(\d\d)\t[^\n]*Voto confirmado para \[Presidente\]", re.M)


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
    por_seg = [0] * 86400; seg_min = [0] * 60; min_hora = [0] * 60
    ass_ini = collections.Counter(); ass_fim = collections.Counter(); linhas = []; n_sec = 0
    for nome, b in membros(uf):
        try:
            with zipfile.ZipFile(io.BytesIO(b)) as inn: d = inn.read("logd.dat")
        except Exception:
            continue
        n_sec += 1
        try: mun, zona, sec = chave(nome)
        except Exception: mun = zona = sec = None
        ts = sorted(((int(h) + off) % 24) * 3600 + int(m) * 60 + int(s) for h, m, s in VOTO.findall(d))
        for t in ts:
            por_seg[t] += 1; seg_min[t % 60] += 1; min_hora[(t // 60) % 60] += 1
        inter = [y - x for x, y in zip(ts, ts[1:])]
        if len(inter) >= 40:
            hi = hashlib.sha1(",".join(map(str, inter[:40])).encode()).hexdigest()[:16]
            hf = hashlib.sha1(",".join(map(str, inter[-40:])).encode()).hexdigest()[:16]
            ass_ini[hi] += 1; ass_fim[hf] += 1
        else:
            hi = hf = None
        if inter:
            k = max(range(len(inter)), key=lambda i: inter[i]); pausa = inter[k]; hora_pausa = ts[k]
            iguais = 0; run = 1; maxrun = 1
            for a, c in zip(inter, inter[1:]):
                if a == c: run += 1; maxrun = max(maxrun, run)
                else: run = 1
            maxrun = maxrun if len(inter) > 1 else 0
        else:
            pausa = None; hora_pausa = None; maxrun = 0
        linhas.append([mun, zona, sec, len(ts), pausa, (f"{hora_pausa // 3600:02d}:{(hora_pausa % 3600) // 60:02d}" if hora_pausa is not None else None), maxrun, hi, hf])
    res = {"uf": uf, "turno": T, "versao": VERSAO, "gerado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "secoes": n_sec, "fonte": membros.fonte, "membros_falhos": membros.falhas,
           "por_segundo": por_seg, "segundo_no_minuto": seg_min, "minuto_na_hora": min_hora,
           "assinaturas_iniciais_repetidas": {k: v for k, v in ass_ini.items() if v > 1},
           "assinaturas_finais_repetidas": {k: v for k, v in ass_fim.items() if v > 1},
           "colunas": ["municipio", "zona", "secao", "votos", "maior_pausa_s", "hora_da_pausa", "maior_corrida_intervalos_identicos", "ass_ini", "ass_fim"],
           "linhas": linhas, "segundos": round(time.time() - t0)}
    tmp = out + ".tmp"; json.dump(res, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, out)
    return uf, f"ok {n_sec} secoes {round(time.time() - t0)}s"


if __name__ == "__main__":
    ufs = UFS_ARG or TODAS
    print(f"tempo {T}T: {len(ufs)} UFs, {WORKERS} workers", flush=True)
    if WORKERS <= 1:
        for u in ufs: print(*processa(u), flush=True)
    else:
        with mp.Pool(WORKERS) as pool:
            for u, r in pool.imap_unordered(processa, ufs): print(u, r, flush=True)
    print("TEMPO_CONCLUIDO", flush=True)
