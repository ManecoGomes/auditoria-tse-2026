#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste K1 — RDV × boletim, voto a voto, por seção, nos dois turnos.

uso: rdv_bu.py <turno 1|2> [UF ...]      WORKERS=3

Emenda de 28/10/2026 (posterior ao plano). O Registro Digital do Voto (rdv.dat) é um
arquivo DER/ASN.1 gravado pela urna com cada voto digitado (tipo + número), por cargo,
sem hora e sem ordem de digitação. Este script decodifica o DER de forma genérica (sem
depender da especificação ASN.1 do TSE) e conta, para o cargo de Presidente, os votos por
tipo e por número; depois confere, seção a seção, com o boletim de urna (CSV extraído do
bweb do TSE): nominais por candidato, brancos e nulos.

O mapeamento do ENUMERATED tipoVoto é calibrado pelo próprio boletim na primeira UF
(o código que acompanha um número de candidato é o nominal; os demais se identificam
pelas contagens de branco e nulo) e registrado na saída.

Saída: /Volumes/SSD1TB/acervo-tse/auditoria/rdv/{t}t/{UF}.json
"""
import collections, csv, datetime, io, json, multiprocessing as mp, os, signal, sys, time, zipfile

VERSAO = 1
T = sys.argv[1]
UFS_ARG = [u.upper() for u in sys.argv[2:]]
WORKERS = int(os.environ.get("WORKERS", "3"))
P = os.path.expanduser("~/Claude/Projetos/eleição")
AC = f"/Volumes/SSD1TB/acervo-tse/2026-{T}t"
OUTD = f"/Volumes/SSD1TB/acervo-tse/auditoria/rdv/{T}t"
os.makedirs(OUTD, exist_ok=True)
TODAS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()
ELEICAO_PRES = {"1": 6257, "2": 6258}[T]   # id da eleição presidencial no RDV/BU (relatório SISTOT 6257_T1 / 6258_T2)
CARGO_PRES = 1


def tlv(b, i):
    tag = b[i]; i += 1
    if tag & 0x1f == 0x1f:
        while b[i] & 0x80: i += 1
        i += 1
    l = b[i]; i += 1
    if l & 0x80:
        n = l & 0x7f; l = int.from_bytes(b[i:i + n], "big"); i += n
    return tag, l, i


def filhos(b, i, end):
    """Lista de (tag, inicio_valor, fim_valor) dos elementos de um construído."""
    out = []
    while i < end:
        tag, l, j = tlv(b, i)
        out.append((tag, j, j + l)); i = j + l
    return out


def votos_presidente(b):
    """Conta (tipo, numero) dos votos do cargo Presidente na eleição presidencial do RDV.

    Estrutura observada (2026): raiz SEQ { cabecalho, identificacao, rdv SEQ { ..., [A1] SEQ OF
    eleicao SEQ { idEleicao INT, SEQ OF cargo SEQ { [81] tipo, idCargo INT, SEQ OF voto SEQ {
    ENUM tipoVoto, [12/1b] numero? } } } } }. Procura-se a eleição pelo id e o cargo pelo idCargo.
    """
    cont = collections.Counter()
    raiz = filhos(b, 0, len(b))
    if not raiz or raiz[0][0] != 0x30: return cont, "raiz"
    def procura(i, end, depth=0):
        for tag, s, e in filhos(b, i, end):
            # o conjunto de eleicoes vem num CHOICE com tag de contexto: [A1] na maioria das secoes,
            # [A2] em algumas (MG 1T: 41238-39-168 e 50075-47-41) — a eleicao traz campos ENUM extras
            if tag in (0xa1, 0xa2, 0xa3) or tag == 0x30 and depth < 3:
                if tag in (0xa1, 0xa2, 0xa3):
                    # o cabecalho tambem tem um [A1]/[A2] curto (dois ENUM): so e o bloco de eleicoes
                    # se dentro houver SEQ { INT idEleicao, ... }; senao, segue procurando
                    achou = False
                    for etag, es, ee in filhos(b, s, e):          # eleicoes
                        if etag != 0x30: continue
                        el = filhos(b, es, ee)
                        if not el or el[0][0] != 0x02: continue
                        if int.from_bytes(b[el[0][1]:el[0][2]], "big") != ELEICAO_PRES: continue
                        seq_cargos = [x for x in el[1:] if x[0] == 0x30]
                        if not seq_cargos: continue
                        achou = True
                        for ctag, cs, ce in filhos(b, seq_cargos[0][1], seq_cargos[0][2]):   # cargos
                            cg = filhos(b, cs, ce)
                            ints = [x for x in cg if x[0] == 0x02]
                            seqs = [x for x in cg if x[0] == 0x30]
                            if not ints or not seqs: continue
                            if int.from_bytes(b[ints[0][1]:ints[0][2]], "big") != CARGO_PRES: continue
                            for vtag, vs, ve in filhos(b, seqs[-1][1], seqs[-1][2]):   # votos
                                tipo = None; num = None
                                for xt, xs, xe in filhos(b, vs, ve):
                                    if xt == 0x0a: tipo = int.from_bytes(b[xs:xe], "big")
                                    elif xt in (0x12, 0x1b, 0x0c, 0x13): num = b[xs:xe].decode("latin-1")
                                    elif xt == 0x02 and num is None: num = str(int.from_bytes(b[xs:xe], "big"))
                                cont[(tipo, num)] += 1
                    if achou: return True
                elif procura(s, e, depth + 1): return True
        return False
    procura(raiz[0][1], raiz[0][2])
    return cont, "ok"


def boletim(uf):
    """{(mun, zona, sec): {("Nominal", numero): votos, ("Branco", None): n, ("Nulo", None): n}}"""
    f = f"{P}/pipeline/resultados/{T}t/votos/{uf}.csv"
    d = collections.defaultdict(dict)
    if not os.path.exists(f): return d
    for r in csv.DictReader(open(f)):
        k = (int(r["municipio"]), int(r["zona"]), int(r["secao"]))
        tipo = r["tipo"]; num = r["numero"] if tipo == "Nominal" else None
        d[k][(tipo, num)] = d[k].get((tipo, num), 0) + int(r["votos"])
    return d


def membros_rdv(uf):
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
        if not (n.startswith("o") and n.endswith("-rdv.dat")): continue
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
    membros_rdv.fonte = fonte; membros_rdv.falhas = falhas


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
    BU = boletim(uf)
    CANDIDATOS = {num for sec in BU.values() for (tipo, num) in sec if tipo == "Nominal"}   # números válidos do pleito na UF
    tipos = collections.Counter(); n_rdv = 0; n_cmp = 0; iguais = 0; difs = []; sem_bu = 0; ilegiveis = 0
    tot_rdv = collections.Counter(); tot_bu = collections.Counter()
    # calibracao do ENUM: o codigo que vem com numero e o nominal; dos demais, o mais frequente e nulo ou branco
    # (decidido pela comparacao com o boletim, seção a seção, abaixo)
    for nome, b in membros_rdv(uf):
        n_rdv += 1
        try: cont, st = votos_presidente(b)
        except Exception: ilegiveis += 1; continue
        if st != "ok": ilegiveis += 1; continue
        for (tipo, num), v in cont.items(): tipos[tipo] += v
        try: k = chave(nome)
        except Exception: continue
        bu = BU.get(k)
        if not bu: sem_bu += 1; continue
        n_cmp += 1
        # Calibrado em AC 2T (2.270/2.270 seções): tipoVoto 2 = nominal (número digitado), 3 = branco,
        # 4 = nulo com o número digitado, 6 = nulo sem número; número digitado que não é candidato = nulo.
        nominal_bu = {num: v for (tipo, num), v in bu.items() if tipo == "Nominal"}
        branco_bu = bu.get(("Branco", None), 0); nulo_bu = bu.get(("Nulo", None), 0)
        nominal_rdv = collections.Counter(); branco_rdv = 0; nulo_rdv = 0
        for (tipo, num), v in cont.items():
            if tipo == 2 and num in CANDIDATOS: nominal_rdv[num] += v
            elif tipo == 3: branco_rdv += v
            else: nulo_rdv += v
        ok = dict(nominal_rdv) == nominal_bu and branco_rdv == branco_bu and nulo_rdv == nulo_bu
        for num, v in nominal_rdv.items(): tot_rdv[num] += v
        for num, v in nominal_bu.items(): tot_bu[num] += v
        tot_rdv["branco"] += branco_rdv; tot_bu["branco"] += branco_bu; tot_rdv["nulo"] += nulo_rdv; tot_bu["nulo"] += nulo_bu
        if ok: iguais += 1
        elif len(difs) < 200:
            difs.append({"secao": f"{k[0]}-{k[1]}-{k[2]}", "rdv": dict(nominal_rdv) | {"branco": branco_rdv, "nulo": nulo_rdv, "tipos": {f"{t_}:{n_}": v for (t_, n_), v in cont.items() if not (t_ == 2 and n_ in CANDIDATOS)}},
                         "bu": nominal_bu | {"branco": branco_bu, "nulo": nulo_bu}})
    res = {"uf": uf, "turno": T, "versao": VERSAO, "gerado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "rdv_lidos": n_rdv, "ilegiveis": ilegiveis, "sem_boletim": sem_bu, "comparadas": n_cmp, "iguais": iguais, "diferentes": n_cmp - iguais,
           "tipos_enum": {str(k): v for k, v in tipos.items()}, "totais_rdv": dict(tot_rdv), "totais_bu": dict(tot_bu),
           "exemplos_diferentes": difs, "fonte": membros_rdv.fonte, "membros_falhos": membros_rdv.falhas, "segundos": round(time.time() - t0)}
    tmp = out + ".tmp"; json.dump(res, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, out)
    return uf, f"ok {n_cmp} comparadas, {n_cmp - iguais} diferentes, {round(time.time() - t0)}s"


if __name__ == "__main__":
    ufs = UFS_ARG or TODAS
    print(f"rdv_bu {T}T: {len(ufs)} UFs, {WORKERS} workers", flush=True)
    if WORKERS <= 1:
        for u in ufs: print(*processa(u), flush=True)
    else:
        with mp.Pool(WORKERS) as pool:
            for u, r in pool.imap_unordered(processa, ufs): print(u, r, flush=True)
    print("RDV_CONCLUIDO", flush=True)
