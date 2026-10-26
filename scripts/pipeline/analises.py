#!/usr/bin/env python3
"""Analises comparativas entre turnos (blocos A2, C4, E, F do plano pre-registrado)."""
import csv, glob, json, os, statistics, collections, datetime, sys
P=os.path.expanduser("~/Claude/Projetos/eleição"); R=f"{P}/pipeline/resultados"

def votos_secao(t):
    """{(mun,zona,sec): {numero: votos, '_comp': comparecimento}}"""
    d={}
    for f in sorted(glob.glob(f"{R}/{t}t/votos/*.csv")):
        for r in csv.DictReader(open(f)):
            k=(int(r["municipio"]),int(r["zona"]),int(r["secao"]))
            e=d.setdefault(k,{"_comp":int(r["comparecimento"] or 0)})
            if r["tipo"]=="Nominal": e[r["numero"]]=e.get(r["numero"],0)+int(r["votos"] or 0)
    return d

def horas_secao(t):
    """{(mun,zona,sec): dict do CSV de horas}"""
    d={}
    for f in sorted(glob.glob(f"{R}/{t}t/logs/*_secoes.csv")):
        for r in csv.DictReader(open(f)):
            d[(int(r["municipio"]),int(r["zona"]),int(r["secao"]))]={
                k:(int(v) if v.isdigit() else v) for k,v in r.items()}
    return d

OUT={"gerado_utc":datetime.datetime.now(datetime.UTC).isoformat(),"blocos":{}}

v1=votos_secao(1); v2=votos_secao(2)
h1=horas_secao(1); h2=horas_secao(2)
print(f"seções com voto 1T:{len(v1)} 2T:{len(v2)} | com log 1T:{len(h1)} 2T:{len(h2)}",flush=True)

# ---------- A2: triangulacao boletim x log ----------
if v2 and h2:
    dif=[]; n=0
    for k,h in h2.items():
        if k not in v2: continue
        n+=1; d=h["votos"]-v2[k]["_comp"]
        if d: dif.append({"secao":"-".join(map(str,k)),"log":h["votos"],"bu":v2[k]["_comp"],"dif":d})
    OUT["blocos"]["A2_triangulacao"]={"secoes_comparadas":n,"divergentes":len(dif),
        "pct":round(100*len(dif)/n,4) if n else None,"exemplos":dif[:50]}
    print(f"A2: {len(dif)}/{n} seções com divergência log x boletim",flush=True)

# ---------- E1/E2/E3: comparacao entre turnos ----------
if v1 and v2:
    comuns=set(v1)&set(v2)
    comp=[(v2[k]["_comp"],v1[k]["_comp"]) for k in comuns if v1[k]["_comp"]]
    OUT["blocos"]["E1_comparecimento"]={"secoes_comuns":len(comuns),
        "variacao_mediana_pct":round(statistics.median([100*(a-b)/b for a,b in comp]),3) if comp else None}
    print(f"E1: {len(comuns)} seções comuns aos dois turnos",flush=True)

# ---------- E4: inferencia ecologica ----------
if v1 and v2 and h2:
    # finalistas = os 2 mais votados nacionalmente no 2T
    tot=collections.Counter()
    for k,e in v2.items():
        for num,q in e.items():
            if num!="_comp": tot[num]+=q
    fin=[n for n,_ in tot.most_common(2)]
    linhas=[]
    for k in set(v1)&set(v2)&set(h2):
        c1,c2=v1[k]["_comp"],v2[k]["_comp"]
        if not c1 or not c2: continue
        h=h2[k]; tard=h["de17_a_19h"]+h["apos_19h"]
        if not h["votos"]: continue
        reg={"secao":"-".join(map(str,k)),"pct_tardio":100*tard/h["votos"]}
        for f in fin:
            reg[f"desloc_{f}"]=100*v2[k].get(f,0)/c2 - 100*v1[k].get(f,0)/c1
        linhas.append(reg)
    if linhas:
        with open(f"{P}/pipeline/resultados/E4_ecologica.csv","w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(linhas[0])); w.writeheader(); w.writerows(linhas)
        # compara quartil superior de votacao tardia contra o inferior
        linhas.sort(key=lambda r:r["pct_tardio"])
        q=len(linhas)//4
        baixo,alto=linhas[:q],linhas[-q:] if q else ([],[])
        res={"secoes":len(linhas),"finalistas":fin,
             "quartil_inferior_pct_tardio":round(statistics.mean([r["pct_tardio"] for r in baixo]),3) if baixo else None,
             "quartil_superior_pct_tardio":round(statistics.mean([r["pct_tardio"] for r in alto]),3) if alto else None}
        for f in fin:
            mb=statistics.mean([r[f"desloc_{f}"] for r in baixo]) if baixo else 0
            ma=statistics.mean([r[f"desloc_{f}"] for r in alto]) if alto else 0
            res[f"deslocamento_{f}"]={"quartil_sem_votacao_tardia":round(mb,4),
                                      "quartil_com_mais_votacao_tardia":round(ma,4),
                                      "diferenca_pontos":round(ma-mb,4)}
        res["ALERTA_METODOLOGICO"]=("Inferencia ecologica. Correlacao no nivel da secao NAO demonstra "
            "comportamento individual (falacia ecologica). Secoes com fila longa tendem a ser urbanas "
            "e populosas, o que ja se associa a padroes de voto. Usar a secao como controle de si mesma "
            "entre turnos reduz, mas nao elimina, esse vies.")
        OUT["blocos"]["E4_ecologica"]=res
        print(f"E4: {len(linhas)} seções analisadas, finalistas {fin}",flush=True)

# ---------- F: geografia ----------
if h2:
    mun=collections.defaultdict(lambda:[0,0])
    for k,h in h2.items():
        mun[k[0]][0]+=h["de17_a_19h"]+h["apos_19h"]; mun[k[0]][1]+=h["votos"]
    pct=[(m,100*a/b) for m,(a,b) in mun.items() if b>500]
    pct.sort(key=lambda x:-x[1])
    OUT["blocos"]["F1_geografia"]={"municipios":len(pct),
        "mediana_pct_tardio":round(statistics.median([p for _,p in pct]),3) if pct else None,
        "top20_mais_tardio":[{"municipio":m,"pct_tardio":round(p,2)} for m,p in pct[:20]]}
    print(f"F1: {len(pct)} municípios",flush=True)

json.dump(OUT,open(f"{P}/pipeline/analises.json","w"),indent=1,ensure_ascii=False)
print("ANALISES_CONCLUIDAS")
