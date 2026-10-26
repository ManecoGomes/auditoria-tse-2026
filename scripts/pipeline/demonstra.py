#!/usr/bin/env python3
"""Executa a bateria do plano sobre os logs do 1o turno ja obtidos (demonstracao)."""
import csv, glob, io, json, os, re, zipfile, collections, datetime, statistics
P=os.path.expanduser("~/Claude/Projetos/eleição")
AC="/Volumes/SSD1TB/acervo-tse/2026-1t/originais"
OFF={"DF":0,"ES":0,"AC":2,"AM":1,"MT":1,"MS":1,"RO":1,"RR":1}
URNA=re.compile(rb"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}\t\w+\t(\d+)\t",re.M)
VOTO=re.compile(rb"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\t.*Voto confirmado para \[Presidente\]",re.M)
BUG=re.compile(rb"^(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\t.*Gerando arquivo de resultado \[bu\.dat\] \+ \[In",re.M)
HAB=re.compile(rb"Eleitor foi habilitado"); COMP=re.compile(rb"O voto do eleitor foi computado")
def Pt(b): return datetime.datetime.strptime(b.decode(),"%d/%m/%Y %H:%M:%S")

UFS=[]
for z in sorted(glob.glob(f"{AC}/*.zip")):
    try:
        zz=zipfile.ZipFile(z)
        if zz.testzip() is None: UFS.append((re.search(r"_1t_([A-Z]{2})\.zip",z).group(1),z))
    except Exception: pass
print("UFs íntegras:",[u for u,_ in UFS],flush=True)

permin=collections.Counter(); inter=collections.Counter(); ultimo=collections.Counter()
nsec=0; tv=0; th=0; tc=0; aposlacre=0; apos17=0
porsec={}
for uf,z in UFS:
    off=datetime.timedelta(hours=OFF.get(uf,0)); OZ=zipfile.ZipFile(z)
    for nome in [n for n in OZ.namelist() if n.endswith("-log.jez")]:
        try:
            with zipfile.ZipFile(io.BytesIO(OZ.read(nome))) as inn: d=inn.read("logd.dat")
        except Exception: continue
        nsec+=1
        r=nome.split("-")[0][8:]; key=(uf,int(r[0:5]),int(r[5:9]),int(r[9:]))
        mu=URNA.search(d); serie=mu.group(1).decode().lstrip("0") if mu else ""
        votos=sorted(Pt(m.group(1))+off for m in VOTO.finditer(d))
        th+=len(HAB.findall(d)); tc+=len(COMP.findall(d)); tv+=len(votos)
        if not votos: continue
        for t in votos: permin[t.replace(second=0).strftime("%H:%M")]+=1
        ultimo[max(votos).strftime("%H:%M")[:2]+"h"]+=1
        # C4 intervalo entre votos consecutivos
        for a,b in zip(votos,votos[1:]):
            s=int((b-a).total_seconds())
            if 0<=s<=600: inter[s]+=1
        g=BUG.search(d)
        apl=0
        if g:
            tbu=Pt(g.group(1))+off
            if [t for t in votos if t>tbu]: aposlacre+=1; apl=1
        a17=sum(1 for t in votos if t.hour>=17); apos17+=a17
        porsec[key]={"votos":len(votos),"apos17":a17,"apos_lacre":apl,
                     "ultimo":max(votos).isoformat(),"urna":serie}
    OZ.close()
    print(f"  {uf} processada ({nsec} seções acumuladas)",flush=True)

rap=sum(q for s,q in inter.items() if s<20)
tot_int=sum(inter.values())
D={"gerado_utc":datetime.datetime.now(datetime.UTC).isoformat(),
   "ufs":[u for u,_ in UFS],"secoes":nsec,"votos_presidente":tv,
   "habilitacoes":th,"computados":tc,
   "C1_secoes_com_voto_apos_lacre":aposlacre,
   "C2_votos_apos_17h":apos17,"C2_pct":round(100*apos17/tv,4) if tv else 0,
   "C3_curva_por_minuto":dict(sorted(permin.items())),
   "C4_intervalos":{"amostra":tot_int,"mediana_s":statistics.median(list(inter.elements())) if tot_int else None,
                    "abaixo_de_20s":rap,"pct_abaixo_20s":round(100*rap/tot_int,4) if tot_int else 0,
                    "distribuicao":{str(k):v for k,v in sorted(inter.items())[:300]}},
   "B4_ultimo_voto_por_hora":dict(sorted(ultimo.items())),
   "C6_hab_menos_comput":th-tc}
# A2 + verificacao de identidade da urna, contra o boletim
bu={}
for uf,_ in UFS:
    f=f"{P}/pipeline/resultados/1t/votos/{uf}.csv"
    if not os.path.exists(f): continue
    import csv as _c
    for r in _c.DictReader(open(f)):
        bu[(uf,int(r["municipio"]),int(r["zona"]),int(r["secao"]))]=(
            int(r["comparecimento"] or 0),)
import csv as _c2, zipfile as _z, io as _io
urnabu={}
for uf,_ in UFS:
    zb=glob.glob(f"/Volumes/SSD1TB/acervo-tse/2026-1t/boletins/bweb_1t_{uf}_*.zip")
    if not zb: continue
    with _z.ZipFile(zb[0]) as zf:
        nm=[n for n in zf.namelist() if n.lower().endswith(".csv")][0]
        with zf.open(nm) as raw:
            for r in _c2.DictReader(_io.TextIOWrapper(raw,encoding="latin-1",newline=""),delimiter=";"):
                if r.get("CD_CARGO_PERGUNTA")!="1": continue
                k=(uf,int(r["CD_MUNICIPIO"]),int(r["NR_ZONA"]),int(r["NR_SECAO"]))
                if k not in urnabu: urnabu[k]=(r["NR_URNA_EFETIVADA"].lstrip("0"),r["DS_TIPO_URNA"])
dif_voto=[]; dif_urna=[]; comp=0
for k,v in porsec.items():
    if k in bu:
        comp+=1
        if v["votos"]!=bu[k][0]:
            dif_voto.append({"secao":"-".join(map(str,k)),"log":v["votos"],"bu":bu[k][0]})
    if k in urnabu and v["urna"] and urnabu[k][0] and v["urna"]!=urnabu[k][0]:
        dif_urna.append({"secao":"-".join(map(str,k)),"urna_log":v["urna"],"urna_bu":urnabu[k][0]})
D["A2_triangulacao"]={"secoes_comparadas":comp,"divergentes":len(dif_voto),
                      "pct":round(100*len(dif_voto)/comp,4) if comp else None,"exemplos":dif_voto[:30]}
D["A4_identidade_da_urna"]={"secoes_comparadas":len([k for k in porsec if k in urnabu]),
                            "divergentes":len(dif_urna),"exemplos":dif_urna[:30]}
D["urnas_distintas"]=len({v["urna"] for v in porsec.values() if v["urna"]})
json.dump(D,open(f"{P}/pipeline/demonstracao_1t.json","w"),indent=1,ensure_ascii=False)
with open(f"{P}/pipeline/demonstracao_secoes.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["uf","municipio","zona","secao","urna_serie","votos","apos17h","apos_lacre","ultimo_voto"])
    for (uf,m,zo,se),v in sorted(porsec.items()):
        w.writerow([uf,m,zo,se,v["urna"],v["votos"],v["apos17"],v["apos_lacre"],v["ultimo"]])
print(json.dumps({k:v for k,v in D.items() if not isinstance(v,dict)},ensure_ascii=False,indent=1))
