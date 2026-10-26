#!/usr/bin/env python3
"""Auditoria de horarios de um turno. uso: audita.py <turno> <bu|logs> [prazo_legal_hora]"""
import csv, io, json, os, sys, zipfile, collections, datetime, re, hashlib
csv.field_size_limit(10**9)
TURNO=sys.argv[1]; TIPO=sys.argv[2]
PRAZO=int(sys.argv[3]) if len(sys.argv)>3 else (17 if TURNO=="1" else 19)
AC=f"/Volumes/SSD1TB/acervo-tse/2026-{TURNO}t"
OUT=f"{os.path.expanduser('~')}/Claude/Projetos/eleição/pipeline/resultados/{TURNO}t/{TIPO}"
os.makedirs(OUT,exist_ok=True)
OFF={**{u:0 for u in "AL AP BA CE DF ES GO MA MG PA PB PE PI PR RJ RN RS SC SE SP TO".split()},
     **{u:1 for u in "AM MT MS RO RR".split()},"AC":2}
def dt(s):
    s=(s or "").strip()
    try: return datetime.datetime.strptime(s,"%Y-%m-%d %H:%M:%S")
    except: return None
def uf_de(n):
    m=re.search(r"_(?:1t|2t)_([A-Z]{2})_",n) or re.search(r"_(?:1t|2t)_([A-Z]{2})\.zip",n)
    return m.group(1) if m else None

if TIPO=="bu":
    for z in sorted(os.listdir(f"{AC}/boletins")):
        if not z.endswith(".zip"): continue
        uf=uf_de(z)
        if not uf or os.path.exists(f"{OUT}/{uf}.json"): continue
        # portao de integridade: nao audita arquivo que nao confere com o hash do TSE
        tse=f"{AC}/boletins/{z}.sha512.tse"
        if os.path.exists(tse):
            esp=open(tse).read().split()[0].lower()
            hh=hashlib.sha512()
            with open(f"{AC}/boletins/{z}","rb") as fh:
                for b in iter(lambda:fh.read(1<<22),b""): hh.update(b)
            if hh.hexdigest()!=esp:
                print(f"{uf}: HASH DIVERGE — NAO AUDITADO (arquivo corrompido ou alterado)",flush=True)
                json.dump({"uf":uf,"turno":TURNO,"erro":"hash_diverge",
                           "sha512_local":hh.hexdigest(),"sha512_tse":esp},
                          open(f"{OUT}/{uf}.ERRO.json","w"))
                continue
        sec={}
        with zipfile.ZipFile(f"{AC}/boletins/{z}") as zf:
            nm=[n for n in zf.namelist() if n.lower().endswith(".csv")][0]
            with zf.open(nm) as raw:
                malformadas=0
                for row in csv.DictReader(io.TextIOWrapper(raw,encoding="latin-1",newline=""),delimiter=";"):
                    try:
                        if row.get("CD_CARGO_PERGUNTA")!="1": continue
                        k=(row["CD_MUNICIPIO"],row["NR_ZONA"],row["NR_SECAO"])
                        if k in sec: continue
                        sec[k]=(row["DT_ABERTURA"],row["DT_ENCERRAMENTO"],row["DT_BU_RECEBIDO"],
                                row["DT_EMISSAO_BU"],int(row["QT_COMPARECIMENTO"] or 0),
                                int(row["QT_APTOS"] or 0),row["NM_MUNICIPIO"])
                    except (ValueError,KeyError,TypeError):
                        malformadas+=1
        off=OFF.get(uf); lim=PRAZO*60
        faixas=collections.Counter(); faixas_v=collections.Counter()
        A=collections.defaultdict(list); comp=aptos=0
        hist=collections.Counter(); histv=collections.Counter(); bu=collections.Counter(); buv=collections.Counter()
        for k,(a,e,b,em,c,ap,mun) in sec.items():
            comp+=c; aptos+=ap
            da,de,db,dem=dt(a),dt(e),dt(b),dt(em)
            if c>ap: A["comp_maior_aptos"].append({"sec":k,"mun":mun,"comp":c,"aptos":ap})
            if da and de and de<da: A["encerra_antes_abre"].append({"sec":k,"mun":mun})
            if dem and de and dem<de: A["bu_antes_encerra"].append({"sec":k,"mun":mun})
            if db:
                bu[db.replace(minute=0,second=0).isoformat()]+=1
                buv[db.replace(minute=0,second=0).isoformat()]+=c
            if de and off is not None:
                eb=de+datetime.timedelta(hours=off); mi=eb.hour*60+eb.minute
                hist[eb.replace(minute=0,second=0).isoformat()]+=1
                histv[eb.replace(minute=0,second=0).isoformat()]+=c
                f=("ate_prazo" if mi<lim else "prazo_mais5" if mi<lim+5 else
                   "prazo_mais30" if mi<lim+30 else "prazo_mais60" if mi<lim+60 else
                   "prazo_mais120" if mi<lim+120 else "acima_120")
                faixas[f]+=1; faixas_v[f]+=c
                if mi>=lim+120: A["encerra_muito_tarde"].append({"sec":k,"mun":mun,"encerra_br":eb.isoformat(),"comp":c})
            if da and off is not None:
                ab=da+datetime.timedelta(hours=off)
                if ab.hour*60+ab.minute>8*60+30: A["abertura_tardia"].append({"sec":k,"mun":mun})
        json.dump({"uf":uf,"turno":TURNO,"prazo_legal":PRAZO,"secoes":len(sec),
                   "linhas_malformadas":malformadas,
                   "comparecimento":comp,"aptos":aptos,"offset":off,
                   "faixas":dict(faixas),"faixas_votantes":dict(faixas_v),
                   "hist_encerramento":dict(hist),"hist_encerramento_v":dict(histv),
                   "hist_bu":dict(bu),"hist_bu_v":dict(buv),
                   "anomalias":{k:v[:400] for k,v in A.items()},
                   "contagem":{k:len(v) for k,v in A.items()}},open(f"{OUT}/{uf}.json","w"))
        if malformadas: print(f"{uf}: ATENCAO — {malformadas} linhas malformadas ignoradas",flush=True)
        print(f"{uf}: {len(sec)} seções, {comp} votantes, tardias>+2h: {len(A['encerra_muito_tarde'])}, comp>aptos: {len(A['comp_maior_aptos'])}",flush=True)

else:  # logs
    VOTO=re.compile(rb"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\t.*Voto confirmado para \[Presidente\]",re.M)
    BUG =re.compile(rb"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\t.*Gerando arquivo de resultado \[bu\.dat\] \+ \[In",re.M)
    HAB=re.compile(rb"Eleitor foi habilitado"); COMP=re.compile(rb"O voto do eleitor foi computado")
    def P(b): return datetime.datetime.strptime(b.decode(),"%d/%m/%Y %H:%M:%S")
    for z in sorted(os.listdir(f"{AC}/originais")):
        if not z.endswith(".zip"): continue
        uf=uf_de(z)
        if not uf or os.path.exists(f"{OUT}/{uf}.json"): continue
        off=datetime.timedelta(hours=OFF.get(uf,0))
        permin=collections.Counter(); ult=collections.Counter()
        n=tv=th=tc=0; A=collections.defaultdict(list); PORSEC=[]
        try:
            OZ=zipfile.ZipFile(f"{AC}/originais/{z}")
            if OZ.testzip() is not None: raise zipfile.BadZipFile("conteudo corrompido")
        except Exception as e:
            print(f"{uf}: ARQUIVO INCOMPLETO OU CORROMPIDO ({e}) — não auditado",flush=True)
            json.dump({"uf":uf,"turno":TURNO,"erro":"zip_invalido","detalhe":str(e)},
                      open(f"{OUT}/{uf}.ERRO.json","w"))
            continue
        for nome in [x for x in OZ.namelist() if x.endswith("-log.jez")]:
            try:
                with zipfile.ZipFile(io.BytesIO(OZ.read(nome))) as inn: d=inn.read("logd.dat")
            except Exception: continue
            n+=1
            _r=nome.split("-")[0][8:]
            mun,zon,sec=int(_r[0:5]),int(_r[5:9]),int(_r[9:]); sid=f"{mun}-{zon}-{sec}"
            votos=[P(m.group(1))+off for m in VOTO.finditer(d)]
            h=len(HAB.findall(d)); c=len(COMP.findall(d)); th+=h; tc+=c; tv+=len(votos)
            if not votos: continue
            for t in votos: permin[t.replace(second=0).isoformat()]+=1
            mx=max(votos); ult[mx.replace(minute=0,second=0).isoformat()]+=1
            g=BUG.search(d)
            if g:
                tbu=P(g.group(1))+off
                dep=[t for t in votos if t>tbu]
                if dep: A["voto_apos_lacre_do_bu"].append({"sec":sid,"bu":tbu.isoformat(),"n":len(dep),"ultimo":max(dep).isoformat()})
            fora=[t for t in votos if t.hour>=PRAZO]
            if fora: A["voto_apos_prazo_legal"].append({"sec":sid,"n":len(fora),"ultimo":max(fora).isoformat()})
            if h!=c: A["habilitacao_difere_voto"].append({"sec":sid,"hab":h,"comput":c})
            a17=sum(1 for t in votos if t.hour<17)
            a19=sum(1 for t in votos if 17<=t.hour<19)
            ap19=sum(1 for t in votos if t.hour>=19)
            PORSEC.append([mun,zon,sec,len(votos),a17,a19,ap19,
                           min(votos).isoformat(),max(votos).isoformat(),
                           1 if (g and [t for t in votos if t>tbu]) else 0])
        OZ.close()
        import csv as _csv
        with open(f"{OUT}/{uf}_secoes.csv","w",newline="") as _f:
            _w=_csv.writer(_f)
            _w.writerow(["municipio","zona","secao","votos","ate_17h","de17_a_19h","apos_19h",
                         "primeiro_voto","ultimo_voto","voto_apos_lacre"])
            _w.writerows(PORSEC)
        json.dump({"uf":uf,"turno":TURNO,"prazo_legal":PRAZO,"secoes":n,"votos":tv,
                   "habilitacoes":th,"computados":tc,"votos_por_minuto":dict(permin),
                   "ultimo_voto_por_hora":dict(ult),
                   "anomalias":{k:v[:500] for k,v in A.items()},
                   "contagem":{k:len(v) for k,v in A.items()}},open(f"{OUT}/{uf}.json","w"))
        print(f"{uf}: {n} seções, {tv} votos, apósLacre: {len(A['voto_apos_lacre_do_bu'])}, após{PRAZO}h: {len(A['voto_apos_prazo_legal'])}",flush=True)
print("AUDITA_CONCLUIDO")
