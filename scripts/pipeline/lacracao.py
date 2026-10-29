#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste L12 — o que cada urna verificou ao carregar × o que foi lacrado no TSE.

uso: lacracao.py <turno 1|2> [UF ...]      WORKERS=3

Emenda de 28/10/2026 (posterior ao plano). O log de cada urna registra, a cada inicialização,
«Verificação de assinatura de aplicação por etapa [n] - [Pacote: /caminho/x.vst] - [RESULTADO]»,
«Versão da aplicação: ...» e «Identificação do Modelo de Urna: UEyyyy». O TSE publica, para cada
modelo de urna, a lista de arquivos lacrados com SHA-512 (Cerimônia de Assinatura Digital e
Lacração, 04/09/2026). A urna não grava o hash no log — grava o resultado da verificação da
assinatura. Logo o cotejo possível é: (a) o conjunto de pacotes que cada urna verificou é o
conjunto lacrado para o seu modelo; (b) todas as verificações deram SUCESSO; (c) a versão
declarada é uma só. O que NÃO se verifica aqui: que o binário instalado é o lacrado (isso é o
Teste de Autenticidade, feito pelo TSE/TREs em urnas sorteadas no dia da eleição).

Saída: /Volumes/SSD1TB/acervo-tse/auditoria/lacracao/{t}t/{UF}.json
"""
import collections, datetime, io, json, multiprocessing as mp, os, re, signal, sys, time, zipfile

VERSAO = 2   # 2: resultado = último colchete da linha (pacotes com "[Arquivo: x]" no meio)
T = sys.argv[1]
UFS_ARG = [u.upper() for u in sys.argv[2:]]
WORKERS = int(os.environ.get("WORKERS", "2"))   # 2: CPU a 100 °C com 3+3 em 28/10; a ponte USB é o gargalo
AC = f"/Volumes/SSD1TB/acervo-tse/2026-{T}t"
OUTD = f"/Volumes/SSD1TB/acervo-tse/auditoria/lacracao/{T}t"
os.makedirs(OUTD, exist_ok=True)
PLEITO = {"1": b"04/10/2026", "2": b"25/10/2026"}[T]
TODAS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()
R_ASS = re.compile(rb"^(\d\d/\d\d/\d{4}) [^\n]*?Verifica\xe7\xe3o de assinatura de aplica\xe7\xe3o por etapa \[(\d+)\] - \[Pacote: ([^\]]+)\](?: - \[Arquivo: [^\]]*\])? - \[([^\]]+)\]\t", re.M)
R_VER = re.compile(rb"Vers\xe3o da aplica\xe7\xe3o: ([^\t\n]+)")
R_MOD = re.compile(rb"Identifica\xe7\xe3o do Modelo de Urna: ([^\t\n]+)")


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
    pacotes = collections.Counter()          # (modelo, pacote, resultado) -> verificações (log inteiro, cumulativo)
    pacotes_dia = collections.Counter()      # idem, só no dia do pleito
    conjuntos = collections.Counter()        # (modelo, conjunto de pacotes verificados) -> seções
    versoes = collections.Counter(); modelos = collections.Counter()
    nao_sucesso = []; n_sec = 0; sem_modelo = 0; multi_versao = 0
    for nome, b in membros(uf):
        try:
            with zipfile.ZipFile(io.BytesIO(b)) as inn: d = inn.read("logd.dat")
        except Exception:
            continue
        n_sec += 1
        try: mun, zona, sec = chave(nome)
        except Exception: mun = zona = sec = None
        mods = collections.Counter(m.decode("latin-1") for m in R_MOD.findall(d))
        modelo = mods.most_common(1)[0][0] if mods else "?"
        if not mods: sem_modelo += 1
        modelos[modelo] += 1
        vs = set(v.decode("latin-1") for v in R_VER.findall(d))
        for v in vs: versoes[v] += 1
        if len(vs) > 1: multi_versao += 1
        pset = set()
        for data, etapa, pac, res in R_ASS.findall(d):
            pac = pac.decode("latin-1"); res = res.decode("latin-1")
            pacotes[(modelo, pac, res)] += 1
            if data == PLEITO: pacotes_dia[(modelo, pac, res)] += 1
            pset.add(pac)
            if res != "SUCESSO" and len(nao_sucesso) < 300:
                nao_sucesso.append({"secao": f"{mun}-{zona}-{sec}", "modelo": modelo, "data": data.decode(), "pacote": pac, "resultado": res})
        conjuntos[(modelo, "|".join(sorted(pset)))] += 1
    res = {"uf": uf, "turno": T, "versao": VERSAO, "gerado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "secoes": n_sec, "sem_modelo": sem_modelo, "secoes_com_mais_de_uma_versao": multi_versao, "fonte": membros.fonte, "membros_falhos": membros.falhas,
           "versoes": dict(versoes), "modelos": dict(modelos),
           "pacotes": [[m, p, r, n] for (m, p, r), n in sorted(pacotes.items())],
           "pacotes_dia": [[m, p, r, n] for (m, p, r), n in sorted(pacotes_dia.items())],
           "conjuntos": [[m, c, n] for (m, c), n in sorted(conjuntos.items(), key=lambda kv: -kv[1])],
           "nao_sucesso": nao_sucesso, "segundos": round(time.time() - t0)}
    tmp = out + ".tmp"; json.dump(res, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, out)
    return uf, f"ok {n_sec} secoes {round(time.time() - t0)}s"


if __name__ == "__main__":
    ufs = UFS_ARG or TODAS
    print(f"lacracao {T}T: {len(ufs)} UFs, {WORKERS} workers", flush=True)
    if WORKERS <= 1:
        for u in ufs: print(*processa(u), flush=True)
    else:
        with mp.Pool(WORKERS) as pool:
            for u, r in pool.imap_unordered(processa, ufs): print(u, r, flush=True)
    print("LACRACAO_CONCLUIDO", flush=True)
