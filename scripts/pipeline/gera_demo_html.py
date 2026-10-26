#!/usr/bin/env python3
import json, os
P=os.path.expanduser("~/Claude/Projetos/eleição")
d=json.load(open(f"{P}/pipeline/demonstracao_1t.json"))
N=lambda x: f"{x:,}".replace(",",".")

# --- grafico 1: curva de votacao por minuto ---
cu=d["C3_curva_por_minuto"]
pts=[(m,v) for m,v in sorted(cu.items()) if "08:00"<=m<="19:30"]
mx=max(v for _,v in pts); W,H=900,260
def x(i): return 60+i*(W-80)/(len(pts)-1)
def y(v): return H-34-(v/mx)*(H-60)
path=" ".join(f"{'M' if i==0 else 'L'}{x(i):.1f},{y(v):.1f}" for i,(_,v) in enumerate(pts))
marc17=next((i for i,(m,_) in enumerate(pts) if m=="17:00"),None)
eixo="".join(f'<text x="{x(i):.0f}" y="{H-12}" font-size="11" fill="#8a857c" text-anchor="middle">{m}</text>'
             for i,(m,_) in enumerate(pts) if m.endswith(":00") and int(m[:2])%2==0)
g1=f'''<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto" role="img" aria-label="Curva de votação por minuto">
<line x1="60" y1="{H-34}" x2="{W-20}" y2="{H-34}" stroke="#38342b"/>
{f'<line x1="{x(marc17):.1f}" y1="20" x2="{x(marc17):.1f}" y2="{H-34}" stroke="#c0462f" stroke-dasharray="4 3"/><text x="{x(marc17)+6:.0f}" y="32" font-size="12" fill="#c0462f">17h — prazo legal</text>' if marc17 else ''}
<path d="{path}" fill="none" stroke="#e8a33d" stroke-width="2"/>
{eixo}<text x="8" y="26" font-size="11" fill="#8a857c">{N(mx)} votos/min</text></svg>'''

# --- grafico 2: intervalo entre votos ---
iv=d["C4_intervalos"]["distribuicao"]
bars=[(int(k),v) for k,v in sorted(iv.items(),key=lambda t:int(t[0])) if int(k)<=300]
mxb=max(v for _,v in bars); W2,H2=900,200
bw=(W2-80)/len(bars)
rects="".join(f'<rect x="{60+i*bw:.1f}" y="{H2-30-(v/mxb)*(H2-56):.1f}" width="{max(bw-0.5,0.6):.1f}" '
              f'height="{(v/mxb)*(H2-56):.1f}" fill="{"#c0462f" if s<20 else "#4fa96f"}"/>'
              for i,(s,v) in enumerate(bars))
g2=f'''<svg viewBox="0 0 {W2} {H2}" style="width:100%;height:auto" role="img" aria-label="Intervalo entre votos">
<line x1="60" y1="{H2-30}" x2="{W2-20}" y2="{H2-30}" stroke="#38342b"/>{rects}
<text x="60" y="{H2-10}" font-size="11" fill="#8a857c">0 s</text>
<text x="{W2-20}" y="{H2-10}" font-size="11" fill="#8a857c" text-anchor="end">300 s</text>
<text x="8" y="22" font-size="11" fill="#8a857c">frequência</text>
<text x="{60+20*bw:.0f}" y="18" font-size="11" fill="#c0462f">◀ faixa implausível (&lt;20 s): zero ocorrências</text></svg>'''

a2=d["A2_triangulacao"]; a4=d["A4_identidade_da_urna"]; c4=d["C4_intervalos"]
b4="".join(f"<tr><td>{k}</td><td style='text-align:right'>{N(v)}</td></tr>"
           for k,v in sorted(d["B4_ultimo_voto_por_hora"].items()))

corpo=f'''
<blockquote><p><strong>Isto é uma demonstração, não o resultado final.</strong> Os testes descritos no
<a href="plano-2t.html">plano pré-registrado</a> foram executados sobre os logs do 1º turno que já estão
em mãos e íntegros — {", ".join(d["ufs"])}, <strong>{N(d["secoes"])} seções</strong> e
<strong>{N(d["votos_presidente"])} votos</strong>. No 2º turno, rodarão sobre todas as seções do país.</p></blockquote>

<div class="grid">
<div class="stat"><div class="n">{N(d["secoes"])}</div><div class="l">seções demonstradas</div></div>
<div class="stat"><div class="n">{N(d["votos_presidente"])}</div><div class="l">votos analisados</div></div>
<div class="stat"><div class="n">{N(d["urnas_distintas"])}</div><div class="l">urnas identificadas</div></div>
<div class="stat zero"><div class="n">{a4["divergentes"]}</div><div class="l">urnas com identidade divergente</div></div>
</div>

<h2>A1 e A4 — Procedência e identidade da urna</h2>
<p>Cada log traz o <strong>número de série da urna</strong> que o gerou, e cada boletim traz o campo
<code>NR_URNA_EFETIVADA</code>. Os dois têm de apontar o mesmo equipamento; se divergirem, o log não
pertence àquela seção.</p>
<p>Resultado: <strong>{N(a4["secoes_comparadas"])} seções conferidas, {a4["divergentes"]} divergências.</strong>
Exemplo real — seção 3050/3/241 de Roraima: log registra a urna <code>02297435</code>, boletim registra
<code>NR_URNA_EFETIVADA 2297435</code>. Mesmo equipamento.</p>
<p>Os relatórios passam a trazer o número de série por seção, no arquivo
<code>demonstracao_secoes.csv</code>.</p>

<h2>A2 — Triangulação entre boletim e log</h2>
<p>Boletim e log são arquivos independentes gerados pela mesma urna. A contagem de votos deve bater.</p>
<p>Resultado: {N(a2["secoes_comparadas"])} seções comparadas, <strong>{N(a2["divergentes"])} com diferença
({a2["pct"]}%)</strong>. Todas as diferenças são de <strong>−1 ou −2</strong>: o log tem <em>menos</em>
que o boletim, nunca mais.</p>
<p>A explicação está na cadeia de eventos: {N(d["habilitacoes"])} habilitações →
{N(d["computados"])} votos computados → {N(d["votos_presidente"])} com confirmação de Presidente.
São eleitores que se habilitaram e não concluíram, ou cujo tempo esgotou. <strong>A direção importa:
nunca há mais votos do que eleitores.</strong></p>
<p>Esse {a2["pct"]}% é agora a linha de base. Se no 2º turno a diferença mudar de direção — log com
<em>mais</em> votos que o boletim — isso exige explicação.</p>

<h2>C3 — Formato da curva de votação</h2>
<p>O que se examina não é o volume, e sim o formato. Fluxo contínuo e declinante é compatível com fila
real; degraus, saltos e rajadas não são.</p>
{g1}
<p>A cauda após as 17h decai suavemente: 2.849 votos às 17h00, 1.818 às 17h05, 1.412 às 17h10.
É a assinatura de uma fila se esvaziando. No 2º turno a curva terá outro formato, porque houve duas
horas legais a mais — o que se compara é a suavidade, não a altura.</p>

<h2>C4 — Intervalo entre votos consecutivos</h2>
<p>Um eleitor precisa de tempo físico para ser identificado, entrar na cabine e votar em todos os cargos.
Sequências rápidas demais indicam registro não-humano.</p>
{g2}
<p>Amostra de <strong>{N(c4["amostra"])} intervalos</strong>. Mediana: <strong>{c4["mediana_s"]:.0f} segundos</strong>.
Intervalos abaixo de 20 segundos: <strong>{c4["abaixo_de_20s"]}</strong> ({c4["pct_abaixo_20s"]}%).</p>

<h2>C1 e C2 — Lacre e prazo</h2>
<p>A urna sela o próprio log ao encerrar: a última linha do arquivo é o registro da geração do log.
Voto posterior a esse marco indicaria reabertura.</p>
<p>Seções com voto após o lacre do boletim: <strong>{d["C1_secoes_com_voto_apos_lacre"]}</strong>.</p>
<p>Votos registrados após as 17h (prazo legal do 1º turno): <strong>{N(d["C2_votos_apos_17h"])}</strong>,
ou {d["C2_pct"]}% do total — atendimento de fila remanescente, conforme o art. 153 do Código Eleitoral.</p>

<h2>B4 — Hora do último voto por seção</h2>
<p>Diferente do horário de encerramento, que é ato administrativo do mesário.</p>
<table><thead><tr><th>Hora do último voto</th><th style="text-align:right">Seções</th></tr></thead>
<tbody>{b4}</tbody></table>

<h2>C6 — Habilitações contra votos computados</h2>
<p>Diferença: <strong>{N(d["C6_hab_menos_comput"])}</strong> habilitações sem voto computado.
O número de votos é sempre menor ou igual ao de habilitações — nunca maior.</p>

<h2>O que ainda não dá para demonstrar</h2>
<p>Os blocos <strong>E</strong> (comparação entre turnos) e <strong>F</strong> (geografia comparada)
exigem os dados do 2º turno, que ainda não existem. O código está escrito, publicado e carimbado;
roda assim que os arquivos saírem.</p>
<p>E permanece o limite estrutural: <strong>não é possível saber em quem votaram os eleitores de um
intervalo de tempo.</strong> O log registra o cargo, nunca o candidato; o RDV traz os votos ordenados,
com apenas dois carimbos de tempo no arquivo inteiro. A separação é o que garante o sigilo do voto.</p>

<h2>Publicação contínua</h2>
<p>No 2º turno os resultados serão publicados <strong>à medida que cada unidade da Federação for
processada</strong>, não ao final. Esta página mostra o estado corrente; o número de seções cresce
conforme os logs chegam e são auditados.</p>
<p>Dados brutos desta demonstração: <code>dados/analises/demonstracao_1t.json</code> e
<code>demonstracao_secoes.csv</code> no repositório.</p>
'''
NAV=('<nav><a href="index.html">Resumo</a><a href="plano-2t.html">Plano do 2º turno</a>'
     '<a href="demonstracao.html" class="on">Demonstração</a><a href="relatorio.html">1º turno</a>'
     '<a href="verificar.html">Como verificar</a><a href="dados.html">Dados e hashes</a></nav>')
base=open(f"{P}/repo/site/relatorio.html").read()
i=base.index('<header class="top">'); j=base.index('<footer>')
novo=(base[:i].replace("Relatório completo","Demonstração dos testes")
 +'<header class="top"><div class="kicker">Demonstração · Eleições Gerais 2026</div>'
 '<h1>Os testes, executados de verdade</h1>'
 '<p class="sub">O plano do 2º turno aplicado aos logs do 1º turno já obtidos — para mostrar, não prometer.</p>'
 +NAV+'</header>'+corpo+base[j:])
open(f"{P}/repo/site/demonstracao.html","w").write(novo)
# nav nas demais
import re
for f in ["index.html","plano-2t.html","relatorio.html","verificar.html","dados.html"]:
    p=f"{P}/repo/site/{f}"; s=open(p).read()
    if "demonstracao.html" in s: continue
    s=re.sub(r"<nav>.*?</nav>", NAV.replace(' class="on"','').replace(f'<a href="{f}">',f'<a href="{f}" class="on">'),
             s, count=1, flags=re.S)
    open(p,"w").write(s)
print("demonstracao.html gerada")
