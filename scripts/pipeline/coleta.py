#!/usr/bin/env python3
"""Descobre, baixa, confere e preserva os arquivos do TSE de um turno.
uso: coleta.py <turno 1|2> <bu|logs|cesp|ceft|gedai>
  bu    boletins de urna (bweb)            logs  logs de votacao (bu_imgbu_logjez_rdv_vscmr)
  cesp  correspondencia ESPERADA urna x secao (CESP, antes da eleicao)   -> teste A4
  ceft  correspondencia EFETIVADA urna x secao (CEFT, depois da eleicao) -> teste A4
  gedai logs do GEDAI (preparacao/carga das urnas, antes da eleicao)     -> teste C5"""
import hashlib, json, os, subprocess, sys, datetime, zipfile

TURNO=sys.argv[1]; TIPO=sys.argv[2]
AC=f"/Volumes/SSD1TB/acervo-tse/2026-{TURNO}t"
API="https://dadosabertos.tse.jus.br/api/3/action/package_show?id="
DS={"bu":"resultados-2026-boletim-de-urna",
    "logs":"resultados-2026-arquivos-transmitidos-para-totalizacao",
    "cesp":f"resultados-2026-correspondencias-esperadas-e-efetivadas-{TURNO}-turno",
    "ceft":f"resultados-2026-correspondencias-esperadas-e-efetivadas-{TURNO}-turno",
    "gedai":f"resultados-2026-logs-do-sistema-de-preparacao-das-urnas-eletronicas-gedai-{TURNO}-turno"}[TIPO]
SUB={"bu":"boletins","logs":"originais","cesp":"correspesp","ceft":"correspefet","gedai":"logsgedai"}[TIPO]
PREFIXO={"cesp":"CESP_","ceft":"CEFT_","gedai":"log_gedai_"}.get(TIPO,"")   # cesp e ceft dividem o dataset
os.makedirs(f"{AC}/{SUB}",exist_ok=True)

j=json.loads(subprocess.run(["curl","-sL","-m","120",API+DS],capture_output=True,text=True).stdout)
res=j["result"]["resources"]
alvo=[r for r in res if f"_{TURNO}t_" in r["url"].lower() and r["url"].endswith(".zip")
      and os.path.basename(r["url"]).startswith(PREFIXO)]
hashes={}
for r in res:
    if r["url"].endswith(".sha512") and f"_{TURNO}t_" in r["url"].lower() and os.path.basename(r["url"]).startswith(PREFIXO):
        hashes[os.path.basename(r["url"])[:-7]]=r["url"]
if not alvo:
    print(json.dumps({"ok":False,"motivo":"sem arquivos publicados","turno":TURNO,"tipo":TIPO})); sys.exit(2)

reg=[]; falhas=[]
for r in sorted(alvo,key=lambda x:x["url"]):
    url=r["url"]; nome=os.path.basename(url); p=f"{AC}/{SUB}/{nome}"
    if not os.path.exists(p):
        for t in range(8):
            rc=subprocess.run(["curl","-sL","-C","-","--retry","5","--retry-delay","10",
                               "--retry-all-errors","-m","21600","-o",p,url]).returncode
            if rc==0:
                try: zipfile.ZipFile(p).testzip(); break
                except Exception: os.remove(p)
        else:
            falhas.append(nome); print(f"FALHOU {nome}",flush=True); continue
    h=hashlib.sha512()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1<<22),b""): h.update(b)
    local=h.hexdigest()
    pub=""
    if nome in hashes:
        o=subprocess.run(["curl","-sL","-m","120",hashes[nome]],capture_output=True,text=True).stdout.split()
        pub=o[0].lower() if o else ""
        open(p+".sha512.tse","w").write(pub+"  "+nome+"\n")
    open(p+".sha512.local","w").write(local+"  "+nome+"\n")
    confere = (local==pub) if pub else None
    reg.append({"arquivo":nome,"bytes":os.path.getsize(p),"sha512":local,
                "sha512_tse":pub,"confere":confere,"url":url,
                "baixado_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()})
    print(f"{nome}: {'OK' if confere else ('SEM HASH TSE' if confere is None else 'DIVERGE')}",flush=True)

json.dump({"turno":TURNO,"tipo":TIPO,"n":len(reg),"falhas":falhas,"arquivos":reg},
          open(f"{AC}/registro_{TIPO}.json","w"),indent=1)
div=[r["arquivo"] for r in reg if r["confere"] is False]
print(json.dumps({"ok":not div and not falhas,"n":len(reg),"divergentes":div,"falhas":falhas}))
