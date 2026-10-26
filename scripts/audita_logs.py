# Auditoria forense dos LOGS DE URNA - 1o turno 2026 (baseline)
import io, json, os, re, subprocess, sys, zipfile, hashlib, collections, datetime
BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
OFF={**{u:0 for u in "AL AP BA CE DF ES GO MA MG PA PB PE PI PR RJ RN RS SC SE SP TO".split()},
     **{u:1 for u in "AM MT MS RO RR".split()}, "AC":2}
URL="https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/bu_imgbu_logjez_rdv_vscmr_2026_1t_{}.zip"

TS=re.compile(rb"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\t",re.M)
VOTO_PRES=re.compile(rb"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\t.*Voto confirmado para \[Presidente\]",re.M)
BU_GER   =re.compile(rb"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\t.*Gerando arquivo de resultado \[bu\.dat\] \+ \[In",re.M)
HAB      =re.compile(rb"Eleitor foi habilitado")
COMPUT   =re.compile(rb"O voto do eleitor foi computado")
MANUAL   =re.compile(rb"Identificador do eleitor digitado pelo mes")
MESARIO  =re.compile(rb"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\t.*Registrando mes.rios antes da vota",re.M)

def P(b): return datetime.datetime.strptime(b.decode(),"%d/%m/%Y %H:%M:%S")

ufs=sys.argv[1:] or sorted(OFF)
for uf in ufs:
    out=f"uf_log/{uf}.json"
    if os.path.exists(out): print(f"{uf}: já feito",flush=True); continue
    os.makedirs("uf_log",exist_ok=True)
    ACERVO="/Volumes/SSD1TB/acervo-tse/2026-1t/originais"
    z=os.path.join(ACERVO,f"bu_imgbu_logjez_rdv_vscmr_2026_1t_{uf}.zip")
    # baixa com retomada; tolera queda de conexao
    for tent in range(1,9):
        r=subprocess.run(["curl","-sL","-C","-","--retry","5","--retry-delay","10",
                          "--retry-all-errors","-m","21600","-o",z,URL.format(uf)])
        if r.returncode==0:
            try:
                zipfile.ZipFile(z).testzip(); break
            except Exception as e:
                print(f"  {uf}: ZIP corrompido ({e}), rebaixando",flush=True); os.remove(z)
        print(f"  {uf}: tentativa {tent} falhou (curl {r.returncode}), retomando",flush=True)
    else:
        print(f"{uf}: FALHOU apos 8 tentativas — pulando",flush=True); continue
    # registra o hash do original preservado
    import hashlib
    h=hashlib.sha512()
    with open(z,"rb") as f:
        for b in iter(lambda:f.read(1<<22),b""): h.update(b)
    open(os.path.join(ACERVO,f"bu_imgbu_logjez_rdv_vscmr_2026_1t_{uf}.zip.sha512.local"),"w").write(
        f"{h.hexdigest()}  bu_imgbu_logjez_rdv_vscmr_2026_1t_{uf}.zip\n")
    off=datetime.timedelta(hours=OFF[uf])
    permin=collections.Counter(); ultimo=collections.Counter()
    nsec=0; tot_voto=0; tot_hab=0; tot_comp=0; tot_man=0
    A={"voto_apos_bu":[], "voto_apos_19h":[], "hab_dif_comput":[], "sem_votos":[]}
    try:
        OZ=zipfile.ZipFile(z)
    except Exception as e:
        print(f"{uf}: ZIP inválido ({e})",flush=True); continue
    jez=[n for n in OZ.namelist() if n.endswith("-log.jez")]
    for i,nome in enumerate(jez):
        try:
            with zipfile.ZipFile(io.BytesIO(OZ.read(nome))) as inner:
                d=inner.read("logd.dat")
        except Exception: continue
        nsec+=1
        votos=[P(m.group(1))+off for m in VOTO_PRES.finditer(d)]
        hab=len(HAB.findall(d)); comput=len(COMPUT.findall(d)); man=len(MANUAL.findall(d))
        tot_hab+=hab; tot_comp+=comput; tot_man+=man; tot_voto+=len(votos)
        sid=nome.split("-")[0][-10:]
        if not votos: A["sem_votos"].append(sid); continue
        for t in votos: permin[t.replace(second=0).isoformat()]+=1
        ult=max(votos); ultimo[ult.replace(minute=0,second=0).isoformat()]+=1
        bu=BU_GER.search(d)
        if bu:
            tbu=P(bu.group(1))+off
            depois=[t for t in votos if t>tbu]
            if depois: A["voto_apos_bu"].append({"sec":sid,"bu":tbu.isoformat(),"n":len(depois),"ult":max(depois).isoformat()})
        tarde=[t for t in votos if t.hour>=19]
        if tarde: A["voto_apos_19h"].append({"sec":sid,"n":len(tarde),"ult":max(tarde).isoformat()})
        if hab!=comput: A["hab_dif_comput"].append({"sec":sid,"hab":hab,"comput":comput})
        if (i+1)%2000==0: print(f"  {uf} {i+1}/{len(jez)}",flush=True)
    OZ.close()
    json.dump({"uf":uf,"secoes":nsec,"votos_presidente":tot_voto,"habilitacoes":tot_hab,
               "votos_computados":tot_comp,"habilitacao_manual":tot_man,
               "votos_por_minuto":dict(permin),"ultimo_voto_por_hora":dict(ultimo),
               "anomalias":{k:v[:500] for k,v in A.items()},
               "anomalias_contagem":{k:len(v) for k,v in A.items()}}, open(out,"w"))
    print(f"{uf}: {nsec} seções | {tot_voto:,} votos pres | hab {tot_hab:,} vs comput {tot_comp:,} | "
          f"manual {tot_man:,} | apósBU {len(A['voto_apos_bu'])} | após19h {len(A['voto_apos_19h'])}".replace(",","."),flush=True)
    # original preservado em ACERVO — nao remover
print("LOGS CONCLUIDO")
