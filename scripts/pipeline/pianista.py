#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste do "pianista": votos em sequência rápida demais, seção por seção, nos dois turnos.

uso: pianista.py <turno 1|2> [UF ...]      (sem UF: todas)   WORKERS=3

Emenda de 28/10/2026 (posterior ao plano). O plano pré-registrado mede intervalos abaixo
de 20 s (C4). Este script repete a medida com limiares de 30 s e 40 s, e acrescenta o que
um "pianista" (mesário votando em série por eleitores ausentes) deixaria no log e que a
contagem solta de intervalos não capta: a SEQUÊNCIA — quantos votos consecutivos abaixo
do limiar, e qual o menor tempo em que uma urna registrou 10 votos seguidos.

Por seção (só "Voto confirmado para [Presidente]" do dia do pleito, hora local da urna):
  n votos, n intervalos (0..600 s), intervalos < 20 / 30 / 40 s, o mesmo só na janela
  final (voto de 17h em diante, hora de Brasília), maior corrida consecutiva < 20/30/40 s
  (dia inteiro e janela final), menor tempo para 10 votos seguidos, mediana dos intervalos.

Saída: /Volumes/SSD1TB/acervo-tse/auditoria/pianista/{t}t/{UF}.json
       (linhas por seção + distribuição de intervalos da UF, dia inteiro e janela final).
Lê o ZIP oficial da UF; se o ZIP estiver inválido, os arquivos soltos de secoes/{UF}
(mesma regra de forense.py).
"""
import collections, datetime, io, json, multiprocessing as mp, os, re, signal, sys, time, zipfile

VERSAO = 1
T = sys.argv[1]
UFS_ARG = [u.upper() for u in sys.argv[2:]]
WORKERS = int(os.environ.get("WORKERS", "3"))
AC = f"/Volumes/SSD1TB/acervo-tse/2026-{T}t"
OUTD = f"/Volumes/SSD1TB/acervo-tse/auditoria/pianista/{T}t"
os.makedirs(OUTD, exist_ok=True)
PLEITO = {"1": b"04/10/2026", "2": b"25/10/2026"}[T]
TODAS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()
OFF = {"AC": 2, "AM": 1, "MT": 1, "MS": 1, "RO": 1, "RR": 1}   # para hora de Brasília
LIMIARES = (20, 30, 40)
INICIO_FINAL = 17 * 60          # janela final: voto de 17h em diante (hora de Brasília)
VOTO = re.compile(rb"^" + PLEITO + rb" (\d\d):(\d\d):(\d\d)\t[^\n]*Voto confirmado para \[Presidente\]", re.M)


def membros(uf):
    """(nome, bytes) dos -log.jez, em ordem. ZIP; se inválido, arquivos soltos do registro."""
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


def corrida_max(flags):
    """Maior sequência de True consecutivos."""
    m = c = 0
    for f in flags:
        c = c + 1 if f else 0
        if c > m: m = c
    return m


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
    dist = collections.Counter(); dist_final = collections.Counter()
    linhas = []; n_sec = 0; sem_voto = 0
    for nome, b in membros(uf):
        try:
            with zipfile.ZipFile(io.BytesIO(b)) as inn: d = inn.read("logd.dat")
        except Exception:
            continue
        n_sec += 1
        try: mun, zona, sec = chave(nome)
        except Exception: mun = zona = sec = None
        # segundos desde a meia-noite, hora de Brasília
        ts = sorted((int(h) + off) * 3600 + int(m) * 60 + int(s) for h, m, s in VOTO.findall(d))
        if len(ts) < 2:
            if not ts: sem_voto += 1
            linhas.append([mun, zona, sec, len(ts), 0] + [0] * 13 + [None, None])
            continue
        inter = [(y - x, y) for x, y in zip(ts, ts[1:]) if 0 <= y - x <= 600]
        n_int = len(inter)
        sg = [i for i, _ in inter]
        fin = [i for i, y in inter if y >= INICIO_FINAL * 60]
        for i in sg: dist[i] += 1
        for i in fin: dist_final[i] += 1
        c = [sum(1 for i in sg if i < L) for L in LIMIARES]
        cf = [sum(1 for i in fin if i < L) for L in LIMIARES]
        run = [corrida_max([i < L for i in sg]) for L in LIMIARES]
        runf = [corrida_max([i < L for i in fin]) for L in LIMIARES]
        min10 = min((ts[i + 9] - ts[i] for i in range(len(ts) - 9)), default=None)
        srt = sorted(sg); med = (srt[n_int // 2] if n_int % 2 else (srt[n_int // 2 - 1] + srt[n_int // 2]) / 2) if n_int else None
        linhas.append([mun, zona, sec, len(ts), n_int] + c + [len(fin)] + cf + run + runf + [min10, med])
    res = {"uf": uf, "turno": T, "versao": VERSAO, "gerado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "secoes": n_sec, "sem_voto": sem_voto, "fonte": membros.fonte, "membros_falhos": membros.falhas,
           "colunas": ["municipio", "zona", "secao", "votos", "intervalos", "abaixo20", "abaixo30", "abaixo40",
                       "intervalos_final", "final_abaixo20", "final_abaixo30", "final_abaixo40",
                       "corrida20", "corrida30", "corrida40", "corrida_final20", "corrida_final30", "corrida_final40",
                       "menor_tempo_10_votos_s", "mediana_s"],
           "dist": dict(sorted(dist.items())), "dist_final": dict(sorted(dist_final.items())),
           "linhas": linhas, "segundos": round(time.time() - t0)}
    tmp = out + ".tmp"
    json.dump(res, open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, out)
    return uf, f"ok {n_sec} secoes {round(time.time() - t0)}s"


if __name__ == "__main__":
    ufs = UFS_ARG or TODAS
    print(f"pianista {T}T: {len(ufs)} UFs, {WORKERS} workers", flush=True)
    if WORKERS <= 1:
        for u in ufs: print(*processa(u), flush=True)
    else:
        with mp.Pool(WORKERS) as pool:
            for u, r in pool.imap_unordered(processa, ufs): print(u, r, flush=True)
    print("PIANISTA_CONCLUIDO", flush=True)
