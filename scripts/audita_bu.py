# Auditoria de horarios - Boletins de Urna, 1o turno 2026 (baseline)
import csv, io, json, os, subprocess, sys, zipfile, hashlib, collections, datetime
csv.field_size_limit(10**9)
BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)

# Offset a somar no relogio da urna p/ chegar em Brasilia (UTC-3). Sem horario de verao desde 2019.
OFF={**{u:0 for u in "AL AP BA CE DF ES GO MA MG PA PB PE PI PR RJ RN RS SC SE SP TO".split()},
     **{u:1 for u in "AM MT MS RO RR".split()}, "AC":2}   # ZZ (exterior) = fusos variados -> fora da conversao

MAN=json.load(open("bweb_1t.json"))
ABERTURA_OFICIAL=datetime.time(8,0); ENCERRA_OFICIAL=datetime.time(17,0)

def dt(s):
    s=(s or "").strip()
    if not s: return None
    try: return datetime.datetime.strptime(s,"%Y-%m-%d %H:%M:%S")
    except: return None

def baixa(uf):
    z=f"bw_{uf}.zip"
    if not os.path.exists(z):
        subprocess.run(["curl","-sL","--retry","3","-m","5400","-o",z,MAN[uf]["zip"]],check=True)
    # verificacao de integridade (cadeia de custodia)
    esperado=subprocess.run(["curl","-sL","-m","120",MAN[uf]["sha"]],capture_output=True,text=True).stdout.split()
    esperado=esperado[0].lower() if esperado else None
    h=hashlib.sha512()
    with open(z,"rb") as f:
        for b in iter(lambda:f.read(1<<22),b""): h.update(b)
    calc=h.hexdigest()
    return z,(calc==esperado), (esperado or "")[:16], calc[:16]

for uf in sorted(MAN):
    saida=f"uf/{uf}.json"
    if os.path.exists(saida): print(f"{uf}: já feito",flush=True); continue
    z,ok,esp,cal=baixa(uf)
    sec=collections.defaultdict(list)
    with zipfile.ZipFile(z) as zf:
        nm=[n for n in zf.namelist() if n.lower().endswith(".csv")][0]
        with zf.open(nm) as raw:
            for row in csv.DictReader(io.TextIOWrapper(raw,encoding="latin-1",newline=""),delimiter=";"):
                if row.get("CD_CARGO_PERGUNTA")!="1": continue
                k=(row["CD_MUNICIPIO"],row["NR_ZONA"],row["NR_SECAO"])
                r=(row["DT_ABERTURA"],row["DT_ENCERRAMENTO"],row["DT_BU_RECEBIDO"],row["DT_EMISSAO_BU"],
                   int(row["QT_COMPARECIMENTO"] or 0),int(row["QT_APTOS"] or 0),
                   row["NM_MUNICIPIO"],row["NR_URNA_EFETIVADA"],row["DS_TIPO_URNA"])
                if r not in sec[k]: sec[k].append(r)

    off=OFF.get(uf)
    hist_enc=collections.Counter(); hist_enc_v=collections.Counter()
    hist_bu=collections.Counter();  hist_bu_v=collections.Counter()
    faixas={"ate_17h00":[0,0],"17h00_17h05":[0,0],"17h05_17h30":[0,0],
            "17h30_18h00":[0,0],"18h00_19h00":[0,0],"apos_19h00":[0,0]}
    A={"comp_maior_aptos":[],"encerra_antes_abre":[],"bu_antes_encerra":[],
       "abertura_tardia":[],"multi_registro":[],"encerra_apos_19h":[]}
    comp=aptos=0; n=0
    for k,regs in sec.items():
        n+=1
        if len(regs)>1: A["multi_registro"].append({"sec":k,"n":len(regs),"mun":regs[0][6]})
        a,e,b,em,c,ap,mun,urna,tipo = regs[0]
        comp+=c; aptos+=ap
        da,de,db,dem = dt(a),dt(e),dt(b),dt(em)
        if c>ap: A["comp_maior_aptos"].append({"sec":k,"mun":mun,"comp":c,"aptos":ap})
        if da and de and de<da: A["encerra_antes_abre"].append({"sec":k,"mun":mun,"abre":a,"encerra":e})
        if dem and de and dem<de: A["bu_antes_encerra"].append({"sec":k,"mun":mun,"encerra":e,"emissao":em})
        if db:
            hist_bu[db.replace(minute=0,second=0).isoformat()]+=1
            hist_bu_v[db.replace(minute=0,second=0).isoformat()]+=c
        if de is not None and off is not None:
            eb=de+datetime.timedelta(hours=off)          # encerramento em horario de Brasilia
            hist_enc[eb.replace(minute=0,second=0).isoformat()]+=1
            hist_enc_v[eb.replace(minute=0,second=0).isoformat()]+=c
            mi=eb.hour*60+eb.minute
            f=("ate_17h00" if mi<1020 else "17h00_17h05" if mi<1025 else "17h05_17h30" if mi<1050
               else "17h30_18h00" if mi<1080 else "18h00_19h00" if mi<1140 else "apos_19h00")
            faixas[f][0]+=1; faixas[f][1]+=c
            if mi>=1140: A["encerra_apos_19h"].append({"sec":k,"mun":mun,"encerra_br":eb.isoformat(),"comp":c})
        if da is not None and off is not None:
            ab=da+datetime.timedelta(hours=off)
            if ab.hour*60+ab.minute>8*60+30:
                A["abertura_tardia"].append({"sec":k,"mun":mun,"abre_br":ab.isoformat()})
    json.dump({"uf":uf,"hash_ok":ok,"hash_esperado":esp,"hash_calculado":cal,"offset":off,
               "secoes":n,"comparecimento":comp,"aptos":aptos,"faixas_encerramento":faixas,
               "hist_enc":dict(hist_enc),"hist_enc_v":dict(hist_enc_v),
               "hist_bu":dict(hist_bu),"hist_bu_v":dict(hist_bu_v),
               "anomalias":{k:v[:400] for k,v in A.items()},
               "anomalias_contagem":{k:len(v) for k,v in A.items()}},
              open(saida,"w"))
    flag="HASH OK " if ok else "HASH DIVERGE!"
    print(f"{uf}: {flag} {n:>6} seções {comp:>11,} votantes | "
          f"tardias>17h05: {faixas['17h05_17h30'][0]+faixas['17h30_18h00'][0]+faixas['18h00_19h00'][0]+faixas['apos_19h00'][0]:>5} | "
          f"comp>aptos: {len(A['comp_maior_aptos'])}".replace(",","."),flush=True)
    os.remove(z)
print("CONCLUIDO")
