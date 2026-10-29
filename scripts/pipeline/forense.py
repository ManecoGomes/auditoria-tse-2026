#!/usr/bin/env python3
"""Forense do log de urna + integridade assinada + testes de boletim.
EMENDA DATADA de 2026-10-28 ao plano pre-registrado (posterior aos dados; menor forca probatoria).

uso: forense.py <turno 1|2> [UF ...]      (sem UF: todas)   WORKERS=4

O que mede, por secao, e agrega por UF (cache em FORENSE/{t}t/{UF}.json):

Bloco L — o log e consistente com ter sido gerado pela urna? (rastro de edicao, humana ou por IA)
  L1 gramatica: toda linha = "dd/mm/aaaa HH:MM:SS<TAB>NIVEL<TAB>serial8<TAB>COMPONENTE<TAB>mensagem<TAB>codigo16hex"
  L2 codificacao: latin-1 puro; bytes de controle, sequencias UTF-8 (acentos "duplos", aspas tipograficas,
     travessao, espaco de largura zero, NBSP) e CRLF sao rastro de editor/reescrita
  L3 codigo de linha: 16 hex, unico dentro do arquivo
  L4 relogio: carimbo nunca retrocede
  L5 vocabulario fechado: toda mensagem (digitos -> #) pertence ao repertorio do software; molde raro e listado
  L6 serial da urna constante no arquivo e igual ao NR_URNA_EFETIVADA do boletim; municipio/zona/secao
     declarados pela urna no dia iguais aos do nome do arquivo
  L7 selo final: ultima linha = "Gerando arquivo de resultado [log.jez] + [Inicio]"; nada depois
  L8 software: versao da aplicacao, modelo de urna, fase, turno declarado, verificacoes de assinatura != SUCESSO
  L9 ciclo do dia do pleito: zeresima antes do 1o voto; habilitados = computados = votos p/ Presidente = comparecimento do BU
  L10 energia/reinicios no dia: ligadas, desligamentos, bateria
  L11 arquivos de log identicos (sha256) entre secoes distintas

Bloco A5 — integridade assinada pela urna: o conteiner de assinatura vota.vsc traz o SHA-512 de bu.dat, log.jez e
  rdv.dat; conferimos cada arquivo que temos contra o hash que a propria urna gravou ao encerrar.

Bloco V — boletim (bweb), por secao: 100% para um candidato, zero para 13 ou 22 com 100+ validos,
  comparecimento == aptos, vetores de votos identicos, ultimo digito (uniformidade), tipo de urna.
"""
import os, sys, re, io, json, csv, zipfile, hashlib, collections, time, signal, datetime, glob
VERSAO = 4
T = sys.argv[1]
UFS_ARG = [u.upper() for u in sys.argv[2:]]
WORKERS = int(os.environ.get("WORKERS", "2"))   # 2: CPU a 100 °C com passagens paralelas em 28/10; a ponte USB é o gargalo
AC = f"/Volumes/SSD1TB/acervo-tse/2026-{T}t"
OUTD = f"/Volumes/SSD1TB/acervo-tse/auditoria/forense/{T}t"
os.makedirs(OUTD, exist_ok=True)
PLEITO = {"1": b"04/10/2026", "2": b"25/10/2026"}[T]
PLEITO_ISO = {"1": "2026-10-04", "2": "2026-10-25"}[T]
TODAS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()

LINE = re.compile(rb"^(\d\d/\d\d/\d{4} \d\d:\d\d:\d\d)\t([A-Z]+)\t(\d{8})\t([A-Z0-9]+)\t([^\t\n]*)\t([0-9A-F]{16})$", re.M)
CTRL = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
C1 = re.compile(rb"[\x80-\x9f]")
UTF8 = re.compile(rb"[\xc2\xc3][\x80-\xbf]|\xe2\x80[\x80-\xbf]|\xef\xbb\xbf")
NBSP = re.compile(rb"\xa0")
HEXRUN = re.compile(rb"\b[0-9A-F]{6,}\b")
DIG = re.compile(rb"\d+")
VOTO_DIA = re.compile(rb"^\d\d/\d\d/\d{4} (\d\d:\d\d:\d\d)\t[A-Z]+\t\d{8}\t[A-Z0-9]+\tVoto confirmado para \[Presidente\]", re.M)
TS_DIA = lambda msg: re.compile(rb"^\d\d/\d\d/\d{4} (\d\d:\d\d:\d\d)\t[A-Z]+\t\d{8}\t[A-Z0-9]+\t" + re.escape(msg), re.M)
R_ZER = TS_DIA(b"Gerando relat\xf3rio [ZER\xc9SIMA] [IN\xcdCIO]")
R_PRONTA = TS_DIA(b"Urna pronta para receber votos")
R_BU = TS_DIA(b"Gerando arquivo de resultado [bu.dat] + [In\xedcio]")
R_LOGJEZ = TS_DIA(b"Gerando arquivo de resultado [log.jez] + [In\xedcio]")
R_LIGADA = re.compile(rb"\tUrna ligada em ", re.M)
R_DESL = re.compile(rb"\tDesligando a urna|\tUrna desligada pela chave", re.M)
R_BAT = re.compile(rb"operando (?:na|com) bateria|sem energia|Falta de energia|rede el\xe9trica ausente|Urna operando na bateria", re.I)
R_HAB = re.compile(rb"Tipo de habilita\xe7\xe3o do eleitor \[([^\]]+)\]")
R_MUN = re.compile(rb"\tMunic\xedpio: (\d+)\t"); R_ZON = re.compile(rb"\tZona Eleitoral: (\d+)\t"); R_SEC = re.compile(rb"\tSe\xe7\xe3o Eleitoral: (\d+)\t")
R_VER = re.compile(rb"Vers\xe3o da aplica\xe7\xe3o: ([^\t\n]+)"); R_MOD = re.compile(rb"Identifica\xe7\xe3o do Modelo de Urna: ([^\t\n]+)")
R_FASE = re.compile(rb"Fase da UE: ([^\t\n]+)"); R_TURNO = re.compile(rb"Turno da UE: ([^\t\n]+)")
R_ASSIN = re.compile(rb"Verifica\xe7\xe3o de assinatura[^\n]*"); R_ASSIN_OK = re.compile(rb"Verifica\xe7\xe3o de assinatura[^\n]*\[SUCESSO\]")
R_VSC_TS = re.compile(rb"20\d{6}T\d{6}")
SELO = b"Gerando arquivo de resultado [log.jez] + [In\xedcio]"

def ler_bweb(uf):
    """por secao: aptos, comparecimento, serial, tipo, votos{votavel: n}, horarios"""
    zs = glob.glob(f"{AC}/boletins/bweb_{T}t_{uf}_*.zip")
    if not zs: return {}
    S = {}
    zf = zipfile.ZipFile(zs[0]); nm = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
    with zf.open(nm) as raw:
        for r in csv.DictReader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";"):
            if r.get("CD_CARGO_PERGUNTA") != "1": continue
            k = (int(r["CD_MUNICIPIO"]), int(r["NR_ZONA"]), int(r["NR_SECAO"]))
            s = S.get(k)
            if s is None:
                s = S[k] = {"aptos": int(r["QT_APTOS"] or 0), "comp": int(r["QT_COMPARECIMENTO"] or 0),
                            "serial": (r.get("NR_URNA_EFETIVADA") or "").strip(), "tipo": r.get("DS_TIPO_URNA"),
                            "abertura": r.get("DT_ABERTURA"), "encerr": r.get("DT_ENCERRAMENTO"), "emissao": r.get("DT_EMISSAO_BU"),
                            "votos": collections.Counter(), "nome_mun": r.get("NM_MUNICIPIO")}
            s["votos"][r["NR_VOTAVEL"]] += int(r["QT_VOTOS"] or 0)
    return S

def membros(uf):
    """(nome, bytes) em ordem, agrupaveis por secao. ZIP; se o ZIP estiver ruim, arquivos soltos do registro."""
    z = f"{AC}/originais/bu_imgbu_logjez_rdv_vscmr_2026_{T}t_{uf}.zip"
    solto = f"{AC}/secoes/{uf}"
    try:
        zf = zipfile.ZipFile(z); nomes = sorted(zf.namelist()); fonte = "zip"
    except Exception as e:
        zf = None; fonte = f"zip_invalido:{e}"
        reg = f"{AC}/registro_secoes_{uf}.json"
        if not os.path.exists(reg): raise
        nomes = sorted(n for r in json.load(open(reg))["secoes"] if "arquivos" in r for n in r["arquivos"] if n not in r.get("faltam", []))
    falhas = 0
    for n in nomes:
        if not n.startswith("o"): continue
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
            j = json.load(open(out))
            if j.get("versao") == VERSAO: return uf, "cache"
        except Exception: pass
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("watchdog 4h")))
    signal.alarm(4 * 3600)
    BU = ler_bweb(uf)
    C = collections.Counter(); A = collections.defaultdict(list)
    moldes = collections.Counter(); moldes_arq = collections.Counter(); exemplo = {}
    versoes = collections.Counter(); modelos = collections.Counter(); fases = collections.Counter(); turnos_dia = collections.Counter()
    hab = collections.Counter(); niveis = collections.Counter(); comps = collections.Counter(); erros_dia = collections.Counter()
    digitos = {"13": collections.Counter(), "22": collections.Counter()}
    hashes_log = collections.Counter(); vetores = collections.Counter()
    def an(k, sec, **kw):
        C[k] += 1
        if len(A[k]) < 300: A[k].append({"sec": sec, **kw})
    grupo = {}; gk = None
    def fecha(gk, g):
        sec = "%d-%d-%d" % gk
        C["secoes"] += 1
        bu = BU.get(gk)
        if bu is None: an("sem_boletim", sec)
        # ---------- A5: hashes no conteiner de assinatura ----------
        vsc = g.get("vota.vsc")
        if vsc is None: an("A5_sem_vsc", sec)
        else:
            C["A5_vsc"] += 1
            for tipo in ("bu.dat", "log.jez", "rdv.dat"):
                b = g.get(tipo)
                if b is None: an(f"A5_sem_{tipo}", sec); continue
                h = hashlib.sha512(b).digest()
                if h in vsc: C[f"A5_{tipo}_confere"] += 1
                else: an(f"A5_{tipo}_DIVERGE", sec, bytes=len(b))
            m = R_VSC_TS.search(vsc)
            if m: g["vsc_ts"] = m.group(0).decode()
        # ---------- log ----------
        jez = g.get("log.jez")
        if jez is None: an("sem_log", sec); return
        try:
            with zipfile.ZipFile(io.BytesIO(jez)) as inn: d = inn.read("logd.dat")
        except Exception as e:
            an("log_jez_ilegivel", sec, erro=str(e)[:80]); return
        C["logs"] += 1; C["bytes_log"] += len(d)
        hashes_log[hashlib.sha256(d).hexdigest()] += 1
        nl = d.count(b"\n") + (0 if d.endswith(b"\n") else 1)
        ok = LINE.findall(d); C["linhas"] += nl; C["linhas_ok"] += len(ok)
        if len(ok) != nl:
            ruins = [l for l in d.split(b"\n") if l and not LINE.match(l)]
            an("L1_linha_fora_da_gramatica", sec, n=nl - len(ok), exemplos=[x[:160].decode("latin-1", "replace") for x in ruins[:3]])
        # L2 codificacao
        for nome, rx in (("L2_bytes_controle", CTRL), ("L2_bytes_C1", C1), ("L2_sequencia_utf8", UTF8), ("L2_nbsp", NBSP)):
            k = len(rx.findall(d))
            if k: an(nome, sec, n=k)
        if b"\r" in d: an("L2_crlf", sec, n=d.count(b"\r"))
        # L3 codigos
        codes = [t[5] for t in ok]
        dup = len(codes) - len(set(codes))
        if dup: an("L3_codigo_repetido", sec, n=dup)
        # L4 relogio
        back = 0; maxback = ""; prev = b""
        for t in ok:
            ts = t[0]; k = ts[6:10] + ts[3:5] + ts[0:2] + ts[11:]
            if k < prev:
                back += 1
                if not maxback: maxback = (prev.decode(), k.decode())
            prev = k if k > prev else prev
        if back: an("L4_relogio_retrocede", sec, n=back, exemplo=maxback)
        # no dia do pleito, separado: antes do dia ha carga/preparacao/ajuste de data e hora (legitimo)
        pd = PLEITO[6:10] + PLEITO[3:5] + PLEITO[0:2]
        bd = 0; prev = b""; ex = ""
        for t in ok:
            ts = t[0]
            if not ts.startswith(PLEITO): continue
            k = ts[11:]
            if k < prev:
                bd += 1
                if not ex: ex = (prev.decode(), k.decode())
            else: prev = k
        if bd: an("L4_relogio_retrocede_no_dia", sec, n=bd, exemplo=ex)
        # L5 vocabulario
        msgs = b"\n".join(t[4] for t in ok)
        msgs = DIG.sub(b"#", HEXRUN.sub(b"#", msgs)).split(b"\n")
        moldes.update(msgs); st = set(msgs); moldes_arq.update(st)
        for m in st:
            if m not in exemplo: exemplo[m] = sec
        # niveis/componentes/serial
        niveis.update(t[1] for t in ok); comps.update(t[3] for t in ok)
        seriais = set(t[2] for t in ok)
        if len(seriais) > 1: an("L6_serial_varia_no_arquivo", sec, seriais=[s.decode() for s in sorted(seriais)][:5])
        serial_log = next(iter(seriais)).decode() if seriais else None
        # L8 software (arquivo inteiro)
        versoes.update(x.decode("latin-1") for x in set(R_VER.findall(d)))
        modelos.update(x.decode("latin-1") for x in set(R_MOD.findall(d)))
        fases.update(x.decode("latin-1") for x in set(R_FASE.findall(d)))
        na = len(R_ASSIN.findall(d)); nok = len(R_ASSIN_OK.findall(d))
        C["L8_verificacoes_assinatura"] += na; C["L8_verificacoes_assinatura_ok"] += nok
        if na != nok: an("L8_assinatura_nao_sucesso", sec, n=na - nok)
        # L7 selo final
        fim = d.rstrip(b"\n").rsplit(b"\n", 1)[-1]
        if SELO not in fim: an("L7_sem_selo_final", sec, ultima=fim[:120].decode("latin-1", "replace"))
        # ---------- dia do pleito ----------
        i = d.find(b"\n" + PLEITO + b" ")
        if i < 0 and d.startswith(PLEITO): i = -1
        if i < 0: an("L9_sem_linhas_no_dia_do_pleito", sec); return
        dia = d[i + 1:]
        C["linhas_dia"] += dia.count(b"\n")
        turnos_dia.update(x.decode("latin-1") for x in set(R_TURNO.findall(dia)))
        tdec = set(R_TURNO.findall(dia))
        if tdec and any(not x.startswith(T.encode()) for x in tdec):
            an("L8_turno_declarado_diferente", sec, declarado=[x.decode("latin-1") for x in tdec])
        for e in re.findall(rb"\tERRO\t\d{8}\t[A-Z0-9]+\t([^\t\n]*)\t", dia):
            erros_dia[DIG.sub(b"#", e).decode("latin-1")] += 1
        votos = VOTO_DIA.findall(dia); nv = len(votos)
        nhab = dia.count(b"Eleitor foi habilitado"); ncomp = dia.count(b"O voto do eleitor foi computado")
        C["votos_presidente_dia"] += nv; C["habilitados_dia"] += nhab; C["computados_dia"] += ncomp
        if nhab != ncomp: an("L9_habilitados_ne_computados", sec, hab=nhab, comp=ncomp)
        if nv != ncomp: an("L9_votos_presidente_ne_computados", sec, votos=nv, comp=ncomp)
        z = R_ZER.search(dia); p = R_PRONTA.search(dia); b = R_BU.search(dia); lj = R_LOGJEZ.search(dia)
        if not z: an("L9_sem_zeresima_no_dia", sec)
        elif votos:
            antes = sum(1 for v in votos if v < z.group(1))
            if antes: an("L9_voto_antes_da_zeresima", sec, n=antes, zeresima=z.group(1).decode())
        if not p and votos: an("L9_sem_urna_pronta", sec)
        if votos and p and min(votos) < p.group(1): an("L9_voto_antes_de_urna_pronta", sec, primeiro=min(votos).decode(), pronta=p.group(1).decode())
        if not b: an("L9_sem_geracao_de_bu_no_dia", sec)
        if not lj: an("L7_sem_geracao_de_logjez_no_dia", sec)
        if b and votos and max(votos) > b.group(1): an("C1_voto_apos_lacre", sec, n=sum(1 for v in votos if v > b.group(1)))
        if lj and g.get("vsc_ts"):
            vt = g["vsc_ts"]; lt = lj.group(1).decode().replace(":", "")
            C["A5_vsc_com_carimbo"] += 1
            if vt[9:] < lt: an("A5_vsc_anterior_ao_log", sec, vsc=vt, log=lj.group(1).decode())
        # L10 energia
        C["L10_ligadas_dia"] += len(R_LIGADA.findall(dia)); C["L10_desligamentos_dia"] += len(R_DESL.findall(dia))
        nb = len(R_BAT.findall(dia))
        if nb: C["L10_secoes_com_evento_bateria"] += 1; C["L10_eventos_bateria"] += nb
        lig = len(R_LIGADA.findall(dia))
        if lig >= 3: an("L10_tres_ou_mais_ligadas_no_dia", sec, n=lig)
        hab.update(x.decode("latin-1") for x in R_HAB.findall(dia))
        C["L9_habilitacao_manual_mesario"] += dia.count(b"habilitou o eleitor")
        # L6 identidade
        mm = R_MUN.findall(dia); zz = R_ZON.findall(dia); ss = R_SEC.findall(dia)
        if mm and zz and ss:
            dec = (int(mm[-1]), int(zz[-1]), int(ss[-1]))
            if dec != gk: an("L6_secao_declarada_difere_do_arquivo", sec, declarada="%d-%d-%d" % dec)
        else: an("L6_sem_identificacao_no_dia", sec)
        if bu is not None:
            if bu["serial"] and serial_log and int(bu["serial"]) != int(serial_log):
                an("L6_serial_log_ne_boletim", sec, log=serial_log, bu=bu["serial"], tipo=bu["tipo"])
            if bu["comp"] != ncomp:
                an("A2_comparecimento_bu_ne_computados_log", sec, bu=bu["comp"], log=ncomp, dif=bu["comp"] - ncomp)
                C["A2_bu_maior"] += bu["comp"] > ncomp; C["A2_log_maior"] += ncomp > bu["comp"]
            tv = sum(bu["votos"].values())
            if tv != bu["comp"]: an("V_soma_votos_ne_comparecimento", sec, soma=tv, comp=bu["comp"])
    def fecha_bu(gk, bu):
        sec = "%d-%d-%d" % gk
        v = bu["votos"]; val = sum(n for k, n in v.items() if k not in ("95", "96"))
        if bu["aptos"] and bu["comp"] == bu["aptos"] and bu["aptos"] >= 50: an("V_comparecimento_igual_aptos", sec, aptos=bu["aptos"])
        if bu["comp"] > bu["aptos"]: an("D1_comparecimento_maior_que_aptos", sec, comp=bu["comp"], aptos=bu["aptos"])
        if val >= 50:
            for c in ("13", "22"):
                if v.get(c, 0) == val: an("V_100pct_um_candidato", sec, cand=c, validos=val)
        if val >= 100:
            for c in ("13", "22"):
                if v.get(c, 0) == 0: an("V_zero_para_candidato_com_100_validos", sec, cand=c, validos=val)
                if v.get(c, 0) >= 100: digitos[c][v[c] % 10] += 1
        if bu["comp"] >= 100:
            vetores[(bu["aptos"], bu["comp"], v.get("13", 0), v.get("22", 0), v.get("95", 0), v.get("96", 0))] += 1
        C["tipo_urna:" + str(bu["tipo"])] += 1
    for nome, b in membros(uf):
        k = chave(nome)
        if gk is not None and k != gk:
            fecha(gk, grupo); grupo = {}
        gk = k; grupo[nome.rsplit("-", 1)[-1]] = b
    if gk is not None: fecha(gk, grupo)
    for k, bu in BU.items(): fecha_bu(k, bu)
    C["boletins"] = len(BU)
    dups = {h: n for h, n in hashes_log.items() if n > 1}
    if dups: C["L11_logs_identicos_grupos"] = len(dups); C["L11_logs_identicos_arquivos"] = sum(dups.values())
    vdup = {k: n for k, n in vetores.items() if n > 1}
    C["V_vetores_identicos_grupos"] = len(vdup); C["V_vetores_identicos_secoes"] = sum(vdup.values())
    raros = [{"molde": m.decode("latin-1"), "arquivos": moldes_arq[m], "ocorrencias": moldes[m], "exemplo_secao": exemplo[m]}
             for m in moldes if moldes_arq[m] <= 2]
    raros.sort(key=lambda x: (x["arquivos"], x["ocorrencias"]))
    res = {"versao": VERSAO, "uf": uf, "turno": T, "pleito": PLEITO_ISO, "fonte": getattr(membros, "fonte", "?"),
           "membros_com_falha_no_zip": getattr(membros, "falhas", 0),
           "gerado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "segundos": round(time.time() - t0),
           "contagem": dict(C), "anomalias": {k: v for k, v in A.items()},
           "moldes_total": len(moldes), "moldes_raros": raros[:400],
           "moldes_top": [[m.decode("latin-1"), n, moldes_arq[m]] for m, n in moldes.most_common(60)],
           "versoes": dict(versoes), "modelos": dict(modelos), "fases": dict(fases), "turno_declarado_dia": dict(turnos_dia),
           "niveis": {k.decode(): v for k, v in niveis.items()}, "componentes": {k.decode(): v for k, v in comps.items()},
           "habilitacao_tipos": dict(hab), "erros_dia": dict(erros_dia.most_common(40)),
           "ultimo_digito": {c: {str(d): n for d, n in sorted(cnt.items())} for c, cnt in digitos.items()},
           "vetores_identicos_exemplos": [list(k) + [n] for k, n in sorted(vdup.items(), key=lambda x: -x[1])[:20]]}
    tmp = out + ".tmp"; json.dump(res, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, out)
    signal.alarm(0)
    return uf, f"ok {C['logs']} logs {res['segundos']}s"

if __name__ == "__main__":
    ufs = UFS_ARG or TODAS
    print(f"forense {T}T: {len(ufs)} UFs, {WORKERS} workers", flush=True)
    if WORKERS <= 1:
        for u in ufs: print(*processa(u), flush=True)
    else:
        import multiprocessing as mp
        with mp.Pool(WORKERS) as pool:
            for uf, st in pool.imap_unordered(processa, ufs):
                print(uf, st, flush=True)
    print("FORENSE_CONCLUIDO", flush=True)
