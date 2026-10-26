#!/usr/bin/env python3
"""Compara o 2o turno contra a regua do 1o e emite o relatorio."""
import json, glob, os, collections, datetime
P=os.path.expanduser("~/Claude/Projetos/eleição")
R=f"{P}/pipeline/resultados"

def carrega(turno,tipo):
    ag={"secoes":0,"comparecimento":0,"aptos":0,"faixas":collections.Counter(),
        "faixas_v":collections.Counter(),"cont":collections.Counter(),
        "votos":0,"hab":0,"comput":0,"ufs":[],"permin":collections.Counter()}
    for f in sorted(glob.glob(f"{R}/{turno}t/{tipo}/*.json")):
        d=json.load(open(f)); ag["ufs"].append(d["uf"])
        ag["secoes"]+=d.get("secoes",0)
        ag["comparecimento"]+=d.get("comparecimento",0); ag["aptos"]+=d.get("aptos",0)
        ag["votos"]+=d.get("votos",0); ag["hab"]+=d.get("habilitacoes",0); ag["comput"]+=d.get("computados",0)
        for k,v in (d.get("faixas") or {}).items(): ag["faixas"][k]+=v
        for k,v in (d.get("faixas_votantes") or {}).items(): ag["faixas_v"][k]+=v
        for k,v in (d.get("contagem") or {}).items(): ag["cont"][k]+=v
        for k,v in (d.get("votos_por_minuto") or {}).items(): ag["permin"][k]+=v
    return ag

# 1o turno: regua ja consolidada (auditoria original)
REGUA={"secoes":499206,"comparecimento":125275835,"aptos":158745007,
       "encerrou_apos_prazo_mais2h":8324,"pct_apos_prazo_mais2h":1.67,
       "abertura_tardia":960,"comp_maior_aptos":0,"encerra_antes_abre":0,
       "bu_antes_encerra":0,"multi_urna":0,"ufs":28}

bu=carrega(2,"bu"); lg=carrega(2,"logs")
N=lambda x: f"{x:,}".replace(",",".")
FX=[("ate_prazo","até o prazo legal"),("prazo_mais5","até +5 min"),("prazo_mais30","até +30 min"),
    ("prazo_mais60","até +1 h"),("prazo_mais120","até +2 h"),("acima_120","mais de +2 h")]

L=[]
L.append("# Auditoria do 2º turno — Eleições Gerais 2026")
L.append("")
L.append(f"*Gerado automaticamente em {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} (America/Sao_Paulo)*")
L.append("*Luis Manuel Jordão Elias Gomes (Maneco Gomes) — OAB/RJ 245.463*")
L.append("")
L.append("Prazo legal de encerramento no 2º turno: **19h** (horário de Brasília), por decisão do")
L.append("Ministro Cristiano Zanin de 25/10/2026, que prorrogou a votação a partir das 17h01.")
L.append("")
L.append("## 1. Universo auditado")
L.append("")
L.append(f"- Unidades da Federação: {len(bu['ufs'])}")
L.append(f"- Seções eleitorais: {N(bu['secoes'])}")
L.append(f"- Comparecimento: {N(bu['comparecimento'])}")
L.append(f"- Eleitores aptos: {N(bu['aptos'])}")
if lg["secoes"]:
    L.append(f"- Seções com log analisado: {N(lg['secoes'])}")
    L.append(f"- Votos para Presidente nos logs: {N(lg['votos'])}")
L.append("")
L.append("## 2. Verificações de impossibilidade lógica")
L.append("")
rot=[("comp_maior_aptos","Comparecimento maior que eleitores aptos","comp_maior_aptos"),
     ("encerra_antes_abre","Encerramento anterior à abertura","encerra_antes_abre"),
     ("bu_antes_encerra","Boletim emitido antes do encerramento","bu_antes_encerra")]
for k,desc,rk in rot:
    L.append(f"- {desc}: **{N(bu['cont'].get(k,0))}**  (1º turno: {REGUA[rk]})")
L.append("")
L.append("## 3. Encerramento das seções, contra a régua do 1º turno")
L.append("")
tot=sum(bu["faixas"].values()) or 1
for k,d in FX:
    s=bu["faixas"].get(k,0); v=bu["faixas_v"].get(k,0)
    L.append(f"- {d}: {N(s)} seções ({100*s/tot:.2f}%), {N(v)} votantes")
L.append("")
alem=bu["faixas"].get("acima_120",0)
L.append(f"No 1º turno, {N(REGUA['encerrou_apos_prazo_mais2h'])} seções "
         f"({REGUA['pct_apos_prazo_mais2h']}%) encerraram mais de 2h após o prazo legal.")
L.append(f"No 2º turno: **{N(alem)} seções ({100*alem/tot:.2f}%)**.")
if tot and REGUA["pct_apos_prazo_mais2h"]:
    razao=(100*alem/tot)/REGUA["pct_apos_prazo_mais2h"]
    L.append(f"Razão entre os turnos: **{razao:.2f}×**.")
    L.append("")
    L.append("Razão próxima de 1 indica comportamento equivalente ao do turno não contestado.")
    L.append("Razão muito acima de 1 indica desvio que exige explicação.")
L.append("")
L.append("## 4. Verificações específicas do 2º turno")
L.append("")
L.append(f"- Seções com voto registrado **após o lacre do boletim** (reabertura de urna): "
         f"**{N(lg['cont'].get('voto_apos_lacre_do_bu',0))}**")
L.append(f"- Seções com voto registrado **após as 19h** (fora do prazo mesmo sob a regra nova): "
         f"**{N(lg['cont'].get('voto_apos_prazo_legal',0))}**")
L.append(f"- Seções com divergência entre habilitações e votos computados: "
         f"**{N(lg['cont'].get('habilitacao_difere_voto',0))}**")
if lg["hab"]:
    L.append(f"- Habilitações: {N(lg['hab'])} · Votos computados: {N(lg['comput'])} "
             f"(diferença {N(lg['hab']-lg['comput'])})")
L.append("")
L.append("Voto registrado entre 17h e 19h no 2º turno é **lícito** — era o prazo vigente por")
L.append("força da decisão judicial. Volume nessa faixa não constitui, por si, irregularidade.")
L.append("")
L.append("## 5. Limitações")
L.append("")
L.append("Os dados do TSE não identificam o eleitor. O log registra a habilitação sem qualquer")
L.append("elemento de identificação — voto e identidade são desacoplados por força do sigilo do")
L.append("voto (art. 14 da Constituição). Não é possível, com esta base, afirmar que determinada")
L.append("pessoa votou, nem que votou mais de uma vez.")
L.append("")
L.append("## 6. Reprodução")
L.append("")
L.append("Programas, dados e manifesto criptográfico em github.com/ManecoGomes/auditoria-tse-2026.")
L.append("O método foi publicado em 26/10/2026, antes da divulgação destes dados, e sua data está")
L.append("ancorada na blockchain do Bitcoin (bloco 973245).")

os.makedirs(f"{P}/relatorio",exist_ok=True)
open(f"{P}/relatorio/RELATORIO-2T.md","w").write("\n".join(L)+"\n")
resumo={"ufs_bu":len(bu["ufs"]),"ufs_logs":len(lg["ufs"]),"secoes":bu["secoes"],
        "comparecimento":bu["comparecimento"],
        "impossibilidades":{k:bu["cont"].get(k,0) for k,_,_ in rot},
        "voto_apos_lacre":lg["cont"].get("voto_apos_lacre_do_bu",0),
        "voto_apos_19h":lg["cont"].get("voto_apos_prazo_legal",0),
        "encerrou_alem_2h":alem,"pct_alem_2h":round(100*alem/tot,3)}
json.dump(resumo,open(f"{P}/pipeline/resumo_2t.json","w"),indent=1)
print(json.dumps(resumo,ensure_ascii=False))
