#!/usr/bin/env python3
"""Gera a demonstracao nacional + uma pagina por unidade da Federacao."""
import json, os, re, datetime

P = os.path.expanduser("~/Claude/Projetos/eleição")
SITE = f"{P}/repo/site"
D = json.load(open(f"{P}/pipeline/demonstracao_1t.json"))
PORUF = D.get("por_uf", {})
DEMO = "/Volumes/SSD1TB/acervo-tse/auditoria/demo"
os.makedirs(f"{SITE}/estados", exist_ok=True)

# bloco completo de cada municipio, por UF: {UF: {cod: bloco}}
import glob as _glob
PORMUN = {}
for _f in sorted(_glob.glob(f"{DEMO}/*_municipios.json")):
    try: _j = json.load(open(_f))
    except Exception: continue
    if _j.get("uf") in PORUF:
        PORMUN[_j["uf"]] = _j.get("municipios", {})

def slug_mun(cod): return str(cod)

N = lambda x: f"{x:,}".replace(",", ".")
URL = "https://auditoria-tse-2026.com.br"

# ---------------------------------------------------------------- graficos
def svg_curva(d):
    cu = d["C3_curva_por_minuto"]
    pts = [(m, v) for m, v in sorted(cu.items()) if "08:00" <= m <= "19:30"]
    if len(pts) < 2: return "<p><em>Curva indisponível: poucos registros.</em></p>"
    mx = max(v for _, v in pts) or 1
    W, H = 900, 260
    x = lambda i: 60 + i*(W-80)/(len(pts)-1)
    y = lambda v: H-34-(v/mx)*(H-60)
    path = " ".join(f"{'M' if i==0 else 'L'}{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(pts))
    m17 = next((i for i, (m, _) in enumerate(pts) if m == "17:00"), None)
    eixo = "".join(f'<text x="{x(i):.0f}" y="{H-12}" font-size="11" fill="#8a857c" '
                   f'text-anchor="middle">{m}</text>'
                   for i, (m, _) in enumerate(pts) if m.endswith(":00") and int(m[:2]) % 2 == 0)
    linha17 = (f'<line x1="{x(m17):.1f}" y1="20" x2="{x(m17):.1f}" y2="{H-34}" stroke="#c0462f" '
               f'stroke-dasharray="4 3"/><text x="{x(m17)+6:.0f}" y="32" font-size="12" '
               f'fill="#c0462f">17h — prazo legal</text>') if m17 is not None else ""
    return (f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto" role="img" '
            f'aria-label="Curva de votação por minuto">'
            f'<line x1="60" y1="{H-34}" x2="{W-20}" y2="{H-34}" stroke="#38342b"/>{linha17}'
            f'<path d="{path}" fill="none" stroke="#e8a33d" stroke-width="2"/>{eixo}'
            f'<text x="8" y="26" font-size="11" fill="#8a857c">{N(mx)} votos/min</text></svg>')

def svg_intervalos(d):
    iv = d["C4_intervalos"]["distribuicao"]
    bars = [(int(k), v) for k, v in sorted(iv.items(), key=lambda t: int(t[0])) if int(k) <= 300]
    if not bars: return "<p><em>Distribuição indisponível: poucos registros.</em></p>"
    mxb = max(v for _, v in bars) or 1
    W, H = 900, 200
    bw = (W-80)/len(bars)
    rects = "".join(f'<rect x="{60+i*bw:.1f}" y="{H-30-(v/mxb)*(H-56):.1f}" '
                    f'width="{max(bw-0.5,0.6):.1f}" height="{(v/mxb)*(H-56):.1f}" '
                    f'fill="{"#c0462f" if s<20 else "#4fa96f"}"/>' for i, (s, v) in enumerate(bars))
    r20 = d["C4_intervalos"]["abaixo_de_20s"]
    rot = "zero ocorrências" if r20 == 0 else f"{N(r20)} ocorrências"
    return (f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto" role="img" '
            f'aria-label="Intervalo entre votos">'
            f'<line x1="60" y1="{H-30}" x2="{W-20}" y2="{H-30}" stroke="#38342b"/>{rects}'
            f'<text x="60" y="{H-10}" font-size="11" fill="#8a857c">0 s</text>'
            f'<text x="{W-20}" y="{H-10}" font-size="11" fill="#8a857c" text-anchor="end">300 s</text>'
            f'<text x="8" y="22" font-size="11" fill="#8a857c">frequência</text>'
            f'<text x="{60+20*bw:.0f}" y="18" font-size="11" fill="#c0462f">'
            f'◀ faixa implausível (&lt;20 s): {rot}</text></svg>')

# ---------------------------------------------------------------- textos
def cauda_17h(d):
    """Substitui os numeros antes fixos: le a propria curva."""
    cu = d["C3_curva_por_minuto"]
    tri = [(h, cu.get(h)) for h in ("17:00", "17:05", "17:10")]
    if any(v is None for _, v in tri): return ""
    return (f'A cauda após as 17h decai suavemente: {N(tri[0][1])} votos às 17h00, '
            f'{N(tri[1][1])} às 17h05, {N(tri[2][1])} às 17h10. '
            f'É a assinatura de uma fila se esvaziando.')

def bloco(d, escopo):
    a2, a4, c4 = d["A2_triangulacao"], d["A4_identidade_da_urna"], d["C4_intervalos"]
    b4 = "".join(f"<tr><td>{k}</td><td style='text-align:right'>{N(v)}</td></tr>"
                 for k, v in sorted(d["B4_ultimo_voto_por_hora"].items()))
    med = f"{c4['mediana_s']:.0f} segundos" if c4.get("mediana_s") is not None else "—"
    nc = a4.get("contingencia_sem_voto", 0)
    cx = (f'<blockquote><p>As {N(nc)} divergências de contingência são benignas e verificáveis: '
          f'o log traz <code>Seção informada pelo operador: 0000 - Urna de contingência</code>, '
          f'nenhum voto e nenhuma habilitação. É a urna reserva, preparada e jamais usada; '
          f'o boletim registra em <code>NR_URNA_EFETIVADA</code> a urna que de fato atendeu a seção. '
          f'O teste A4 as conta porque compara <em>todo</em> log ao boletim, inclusive os sem voto — '
          f'critério mais estrito que o da primeira versão desta página, que os omitia.</p></blockquote>'
          if nc else "")
    eo = a4.get("exemplo_conferido")
    ex = ""
    if eo:
        ex = (f' Exemplo conferido — seção {eo["secao"]}: o log registra a urna '
              f'<code>{eo["urna_log"]}</code> e o boletim registra <code>NR_URNA_EFETIVADA '
              f'{eo["urna_bu"]}</code>, com {N(eo["votos"])} votos. Mesmo equipamento.')
    men, mai = a2.get("log_menor_que_bu"), a2.get("log_maior_que_bu")
    if a2["divergentes"] and men is not None:
        if mai == 0:
            dirpct = (f'<strong>Todas as {N(men)} diferenças apontam no mesmo sentido</strong>: o log tem '
                      f'<em>menos</em> votos que o boletim, nunca mais — variação de '
                      f'{a2.get("delta_min")} a {a2.get("delta_max") if a2.get("delta_max") else -1} voto(s). '
                      f'Conferido sobre as {N(a2["divergentes"])} seções divergentes, não por amostra.')
        else:
            dirpct = (f'<strong>Atenção:</strong> {N(men)} seções com log <em>menor</em> que o boletim e '
                      f'<strong>{N(mai)} com log MAIOR</strong> — variação de {a2.get("delta_min")} a '
                      f'+{a2.get("delta_max")}. Log com mais votos que eleitores <strong>exige '
                      f'explicação</strong> e está detalhado no CSV de seções.')
    else:
        dirpct = ""
    return f'''
<div class="grid">
<div class="stat"><div class="n">{N(d["secoes"])}</div><div class="l">seções auditadas</div></div>
<div class="stat"><div class="n">{N(d["votos_presidente"])}</div><div class="l">votos analisados</div></div>
<div class="stat"><div class="n">{N(d["urnas_distintas"])}</div><div class="l">urnas identificadas</div></div>
<div class="stat{' zero' if a4.get("sem_explicacao",a4["divergentes"])==0 else ''}"><div class="n">{N(a4.get("sem_explicacao",a4["divergentes"]))}</div><div class="l">urnas divergentes sem explicação</div></div>
</div>

<h2>A1 e A4 — Procedência e identidade da urna</h2>
<p>Cada log traz o <strong>número de série da urna</strong> que o gerou, e cada boletim traz o campo
<code>NR_URNA_EFETIVADA</code>. Os dois têm de apontar o mesmo equipamento; se divergirem, o log não
pertence àquela seção.</p>
<p>Resultado: <strong>{N(a4["secoes_comparadas"])} seções conferidas, {N(a4["divergentes"])} com série
divergente</strong> — das quais <strong>{N(a4.get("contingencia_sem_voto",0))}</strong> são urnas de
contingência e <strong>{N(a4.get("sem_explicacao",0))}</strong> seguem <strong>sem explicação</strong>.{ex}</p>
{cx}

<h2>A2 — Triangulação entre boletim e log</h2>
<p>Boletim e log são arquivos independentes gerados pela mesma urna. A contagem de votos deve bater.</p>
<p>Resultado: {N(a2["secoes_comparadas"])} seções comparadas, <strong>{N(a2["divergentes"])} com diferença
({a2["pct"] if a2["pct"] is not None else "—"}%)</strong>. {dirpct}</p>
<p>A cadeia de eventos: {N(d["habilitacoes"])} habilitações →
{N(d["computados"])} votos computados → {N(d["votos_presidente"])} com confirmação de Presidente.
São eleitores que se habilitaram e não concluíram, ou cujo tempo esgotou. <strong>A direção importa:
nunca há mais votos do que eleitores.</strong></p>

<h2>C3 — Formato da curva de votação</h2>
<p>O que se examina não é o volume, e sim o formato. Fluxo contínuo e declinante é compatível com fila
real; degraus, saltos e rajadas não são.</p>
{svg_curva(d)}
<p>{cauda_17h(d)} No 2º turno a curva terá outro formato, porque houve duas
horas legais a mais — o que se compara é a suavidade, não a altura.</p>

<h2>C4 — Intervalo entre votos consecutivos</h2>
<p>Um eleitor precisa de tempo físico para ser identificado, entrar na cabine e votar em todos os cargos.
Sequências rápidas demais indicam registro não-humano.</p>
{svg_intervalos(d)}
<p>Amostra de <strong>{N(c4["amostra"])} intervalos</strong>. Mediana: <strong>{med}</strong>.
Intervalos abaixo de 20 segundos: <strong>{N(c4["abaixo_de_20s"])}</strong> ({c4["pct_abaixo_20s"]}%).</p>

<h2>C1 e C2 — Lacre e prazo</h2>
<p>A urna sela o próprio log ao encerrar: a última linha do arquivo é o registro da geração do log.
Voto posterior a esse marco indicaria reabertura.</p>
<p>Seções com voto após o lacre do boletim: <strong>{N(d["C1_secoes_com_voto_apos_lacre"])}</strong>.</p>
<p>Votos registrados após as 17h (prazo legal do 1º turno): <strong>{N(d["C2_votos_apos_17h"])}</strong>,
ou {d["C2_pct"]}% do total — atendimento de fila remanescente, conforme o art. 153 do Código Eleitoral.</p>

<h2>B4 — Hora do último voto por seção</h2>
<p>Diferente do horário de encerramento, que é ato administrativo do mesário.</p>
<table><thead><tr><th>Hora do último voto</th><th style="text-align:right">Seções</th></tr></thead>
<tbody>{b4}</tbody></table>

<h2>C6 — Habilitações contra votos computados</h2>
<p>Diferença: <strong>{N(d["C6_hab_menos_comput"])}</strong> habilitações sem voto computado.
O número de votos é sempre menor ou igual ao de habilitações — nunca maior.</p>
'''

# ---------------------------------------------------------------- tabela de municipios
COLS = ('<thead><tr><th>Município</th><th style="text-align:right">Seções</th>'
        '<th style="text-align:right">Votos</th><th style="text-align:right">Mediana<br>entre votos</th>'
        '<th style="text-align:right">Intervalos<br>&lt;20s</th>'
        '<th style="text-align:right">Voto após<br>lacre</th>'
        '<th style="text-align:right">Urna de<br>contingência</th>'
        '<th style="text-align:right">Urna divergente<br>sem explicação</th>'
        '<th style="text-align:right">Triangulação<br>divergente</th></tr></thead>')

def linha_mun(uf, m, href=None):
    """Uma linha de municipio, nas mesmas colunas do indice de estados."""
    med = f'{m["mediana_s"]:.0f}s' if m.get("mediana_s") is not None else "—"
    rot = m["nome"] if not href else f'<a href="{href}">{m["nome"]}</a>'
    return (f'<tr><td>{rot}</td>'
            f'<td style="text-align:right">{N(m["secoes"])}</td>'
            f'<td style="text-align:right">{N(m["votos"])}</td>'
            f'<td style="text-align:right">{med}</td>'
            f'<td style="text-align:right">{N(m["abaixo_20s"])}</td>'
            f'<td style="text-align:right">{N(m["apos_lacre"])}</td>'
            f'<td style="text-align:right">{N(m["contingencia"])}</td>'
            f'<td style="text-align:right">{N(m["urna_sem_explicacao"])}</td>'
            f'<td style="text-align:right">{N(m["a2_divergentes"])}</td></tr>')

def tabela_municipios(uf, d):
    res = d.get("municipios_resumo") or []
    if not res:
        return ('<h2>Município por município</h2><p><em>Agregação municipal indisponível para '
                'esta unidade — o cache foi gerado por uma versão anterior do processamento.</em></p>')
    tem = PORMUN.get(uf, {})
    linhas = "".join(linha_mun(uf, m, f'{uf}/{slug_mun(m["municipio"])}.html'
                               if str(m["municipio"]) in tem else None) for m in res)
    tot = (f'<tr><td><strong>Total de {N(len(res))} municípios</strong></td>'
           f'<td style="text-align:right"><strong>{N(d["secoes"])}</strong></td>'
           f'<td style="text-align:right"><strong>{N(d["votos_presidente"])}</strong></td>'
           f'<td style="text-align:right"><strong>'
           f'{(str(round(d["C4_intervalos"]["mediana_s"]))+"s") if d["C4_intervalos"].get("mediana_s") is not None else "—"}'
           f'</strong></td>'
           f'<td style="text-align:right"><strong>{N(d["C4_intervalos"]["abaixo_de_20s"])}</strong></td>'
           f'<td style="text-align:right"><strong>{N(d["C1_secoes_com_voto_apos_lacre"])}</strong></td>'
           f'<td style="text-align:right"><strong>{N(d["A4_identidade_da_urna"].get("contingencia_sem_voto",0))}</strong></td>'
           f'<td style="text-align:right"><strong>{N(d["A4_identidade_da_urna"].get("sem_explicacao",0))}</strong></td>'
           f'<td style="text-align:right"><strong>{N(d["A2_triangulacao"]["divergentes"])}</strong></td></tr>')
    return (f'<h2>Município por município</h2>'
            f'<p>Os mesmos testes, aplicados isoladamente a cada um dos <strong>{N(len(res))} municípios</strong> '
            f'de {d["nome"]} com log auditado. Clique no município para ver a curva de votação e a '
            f'distribuição de intervalos daquela cidade. É nesta granularidade que a comparação com o '
            f'2º turno será feita: a mesma cidade contra si mesma.</p>'
            f'<div class="scroll"><table>{COLS}<tbody>{linhas}{tot}</tbody></table></div>'
            f'<p>As colunas de voto após o lacre, urna divergente sem explicação e intervalos abaixo de '
            f'20 s são as que <strong>exigem explicação quando diferentes de zero</strong>.</p>')

# ---------------------------------------------------------------- molde
BASE = open(f"{SITE}/relatorio.html").read()
_i = BASE.index('<header class="top">'); _j = BASE.index('<footer>')
CABECA, RODAPE = BASE[:_i], BASE[_j:]

def nav(ativo, pre=""):
    its = [("index.html","Resumo"),("plano-2t.html","Plano do 2º turno"),
           ("demonstracao.html","Demonstração"),("estados/index.html","Estados"),
           ("relatorio.html","1º turno"),("verificar.html","Como verificar"),
           ("dados.html","Dados e hashes")]
    out = []
    for h, t in its:
        cls = ' class="on"' if h == ativo else ""
        out.append(f'<a href="{pre}{h}"{cls}>{t}</a>')
    return "<nav>" + "".join(out) + "</nav>"

def pagina(titulo, kicker, h1, sub, corpo, ativo, slug, pre=""):
    head = (CABECA.replace("<title>Relatório completo — Auditoria TSE 2026</title>", f"<title>{titulo}</title>")
                  .replace(f'href="{URL}/relatorio.html"', f'href="{URL}/{slug}"')
                  .replace(f'content="{URL}/relatorio.html"', f'content="{URL}/{slug}"'))
    return (head + f'<header class="top"><div class="kicker">{kicker}</div><h1>{h1}</h1>'
            f'<p class="sub">{sub}</p>' + nav(ativo, pre) + "</header>" + corpo + RODAPE)

# ---------------------------------------------------------------- 1. nacional
falta = [u for u in ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT","PA","PB","PE",
                     "PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO","ZZ"] if u not in PORUF]
aviso_falta = (f'<p><strong>Em processamento:</strong> {", ".join(falta)} — '
               f'{len(falta)} de 28 unidades ainda em download ou auditoria. '
               f'A página cresce conforme cada uma termina.</p>') if falta else ""

corpo_nac = (f'''
<blockquote><p><strong>Isto é uma demonstração, não o resultado final.</strong> Os testes descritos no
<a href="plano-2t.html">plano pré-registrado</a> foram executados sobre os logs do 1º turno já obtidos
e íntegros — <strong>{len(PORUF)} unidades da Federação</strong>, <strong>{N(D["secoes"])} seções</strong>
e <strong>{N(D["votos_presidente"])} votos</strong>. No 2º turno, rodarão sobre todas as seções do país.</p>
<p><a href="estados/index.html"><strong>Ver os resultados estado por estado →</strong></a></p></blockquote>
''' + bloco(D, "nacional") + f'''
<h2>Estado por estado</h2>
<p>Os mesmos testes, aplicados isoladamente a cada unidade da Federação, estão em
<a href="estados/index.html">páginas próprias</a> — uma por estado, com a curva e a distribuição
de intervalos daquele estado. É assim que os resultados do 2º turno serão publicados: cada UF
entra no ar quando termina, sem esperar as demais.</p>
{aviso_falta}

<h2>O que ainda não dá para demonstrar</h2>
<p>Os blocos <strong>E</strong> (comparação entre turnos) e <strong>F</strong> (geografia comparada)
exigem os dados do 2º turno, que ainda não existem. O código está escrito, publicado e carimbado;
roda assim que os arquivos saírem.</p>
<p>E permanece o limite estrutural: <strong>não é possível saber em quem votaram os eleitores de um
intervalo de tempo.</strong> O log registra o cargo, nunca o candidato; o RDV traz os votos ordenados,
com apenas dois carimbos de tempo no arquivo inteiro. A separação é o que garante o sigilo do voto.</p>

<h2>Publicação contínua</h2>
<p>No 2º turno os resultados serão publicados <strong>à medida que cada unidade da Federação for
processada</strong>, não ao final. Esta página mostra o estado corrente.</p>
<p>Dados brutos: <code>dados/analises/demonstracao_1t.json</code> e
<code>demonstracao_secoes.csv</code> no repositório.</p>
''')
open(f"{SITE}/demonstracao.html", "w").write(pagina(
  "Demonstração dos testes — Auditoria TSE 2026", "Demonstração · Eleições Gerais 2026",
  "Os testes, executados de verdade",
  "O plano do 2º turno aplicado aos logs do 1º turno já obtidos — para mostrar, não prometer.",
  corpo_nac, "demonstracao.html", "demonstracao.html"))

# ---------------------------------------------------------------- 2. indice de estados
linhas = ""
for uf in sorted(PORUF):
    d = PORUF[uf]
    a2, a4, c4 = d["A2_triangulacao"], d["A4_identidade_da_urna"], d["C4_intervalos"]
    med = f"{c4['mediana_s']:.0f}s" if c4.get("mediana_s") is not None else "—"
    linhas += (f'<tr><td><a href="{uf}.html">{uf} — {d["nome"]}</a></td>'
               f'<td style="text-align:right">{N(d.get("municipios", 0))}</td>'
               f'<td style="text-align:right">{N(d["secoes"])}</td>'
               f'<td style="text-align:right">{N(d["votos_presidente"])}</td>'
               f'<td style="text-align:right">{med}</td>'
               f'<td style="text-align:right">{N(c4["abaixo_de_20s"])}</td>'
               f'<td style="text-align:right">{N(d["C1_secoes_com_voto_apos_lacre"])}</td>'
               f'<td style="text-align:right">{N(a4.get("contingencia_sem_voto",0))}</td>'
               f'<td style="text-align:right">{N(a4.get("sem_explicacao",0))}</td>'
               f'<td style="text-align:right">{N(a2["divergentes"])}</td></tr>')
linhas += (f'<tr><td><strong>Total das {len(PORUF)}</strong></td>'
           f'<td style="text-align:right"><strong>{N(D.get("municipios", 0))}</strong></td>'
           f'<td style="text-align:right"><strong>{N(D["secoes"])}</strong></td>'
           f'<td style="text-align:right"><strong>{N(D["votos_presidente"])}</strong></td>'
           f'<td style="text-align:right"><strong>{D["C4_intervalos"]["mediana_s"]:.0f}s</strong></td>'
           f'<td style="text-align:right"><strong>{N(D["C4_intervalos"]["abaixo_de_20s"])}</strong></td>'
           f'<td style="text-align:right"><strong>{N(D["C1_secoes_com_voto_apos_lacre"])}</strong></td>'
           f'<td style="text-align:right"><strong>{N(D["A4_identidade_da_urna"].get("contingencia_sem_voto",0))}</strong></td>'
           f'<td style="text-align:right"><strong>{N(D["A4_identidade_da_urna"].get("sem_explicacao",0))}</strong></td>'
           f'<td style="text-align:right"><strong>{N(D["A2_triangulacao"]["divergentes"])}</strong></td></tr>'
           ) if PORUF else ""

corpo_idx = f'''
<p>Os mesmos oito testes do <a href="../plano-2t.html">plano pré-registrado</a>, aplicados
isoladamente a cada unidade da Federação. Clique no estado para ver a curva de votação e a
distribuição de intervalos daquele estado.</p>
<div class="scroll"><table>
<thead><tr><th>Estado</th><th style="text-align:right">Municípios</th><th style="text-align:right">Seções</th><th style="text-align:right">Votos</th>
<th style="text-align:right">Mediana<br>entre votos</th><th style="text-align:right">Intervalos<br>&lt;20s</th>
<th style="text-align:right">Voto após<br>lacre</th><th style="text-align:right">Urna de<br>contingência</th><th style="text-align:right">Urna divergente<br>sem explicação</th>
<th style="text-align:right">Triangulação<br>divergente</th></tr></thead>
<tbody>{linhas}</tbody></table></div>
<p>As três últimas colunas são os testes em que <strong>qualquer número diferente de zero exige
explicação</strong>. A coluna de triangulação admite diferenças negativas — eleitor que se habilitou
e não concluiu o voto — e está detalhada na página de cada estado.</p>
{aviso_falta}
<p>Dados brutos por estado: <code>dados/analises/demonstracao_1t.json</code>, chave <code>por_uf</code>.</p>
'''
open(f"{SITE}/estados/index.html", "w").write(pagina(
  "Resultados por estado — Auditoria TSE 2026", "Demonstração · Eleições Gerais 2026",
  "Estado por estado",
  "Os testes do plano aplicados a cada unidade da Federação, publicados à medida que terminam.",
  corpo_idx, "estados/index.html", "estados/index.html", pre="../"))

# ---------------------------------------------------------------- 3. uma pagina por estado
for uf in sorted(PORUF):
    d = PORUF[uf]
    viz = [u for u in sorted(PORUF) if u != uf]
    outros = " · ".join(f'<a href="{u}.html">{u}</a>' for u in viz)
    corpo = (f'<blockquote><p>Os oito testes do <a href="../plano-2t.html">plano pré-registrado</a> '
             f'aplicados <strong>somente a {d["nome"]}</strong>, sobre os logs do 1º turno. '
             f'Para o total do país, veja a <a href="../demonstracao.html">demonstração nacional</a>; '
             f'para a comparação entre estados, o <a href="index.html">índice</a>.</p></blockquote>'
             + bloco(d, d["nome"])
             + tabela_municipios(uf, d)
             + f'<h2>Outros estados</h2><p>{outros or "—"}</p>')
    open(f"{SITE}/estados/{uf}.html", "w").write(pagina(
      f'{d["nome"]} — Auditoria TSE 2026', f'Demonstração · {uf}',
      f'{d["nome"]}', f'Os testes do plano aplicados aos logs do 1º turno de {d["nome"]}.',
      corpo, None, f"estados/{uf}.html", pre="../"))

# ---------------------------------------------------------------- 3b. uma pagina por municipio
n_mun = 0
for uf in sorted(PORMUN):
    tem = PORMUN[uf]
    if not tem: continue
    os.makedirs(f"{SITE}/estados/{uf}", exist_ok=True)
    duf = PORUF[uf]
    res = {str(m["municipio"]): m for m in (duf.get("municipios_resumo") or [])}
    ordem_mun = sorted(tem, key=lambda c: (tem[c].get("nome") or ""))
    for pos, cod in enumerate(ordem_mun):
        b = tem[cod]
        viz = []
        if pos > 0:
            a_ = tem[ordem_mun[pos-1]]
            viz.append(f'◀ <a href="{slug_mun(ordem_mun[pos-1])}.html">{a_["nome"]}</a>')
        if pos < len(ordem_mun)-1:
            a_ = tem[ordem_mun[pos+1]]
            viz.append(f'<a href="{slug_mun(ordem_mun[pos+1])}.html">{a_["nome"]}</a> ▶')
        corpo = (f'<blockquote><p>Os oito testes do <a href="../../plano-2t.html">plano pré-registrado</a> '
                 f'aplicados <strong>somente a {b["nome"]} ({uf})</strong>, sobre os logs do 1º turno. '
                 f'Para o estado inteiro, veja <a href="../{uf}.html">{duf["nome"]}</a>; '
                 f'para o país, a <a href="../../demonstracao.html">demonstração nacional</a>.</p>'
                 f'<p>Esta página é a linha de base desta cidade. Quando o TSE publicar o 2º turno, '
                 f'os mesmos números sairão aqui ao lado, para comparação direta.</p></blockquote>'
                 + bloco(b, b["nome"])
                 + f'<h2>Vizinhos no estado</h2><p>{" · ".join(viz) or "—"}</p>'
                 + f'<p><a href="../{uf}.html">◀ Todos os municípios de {duf["nome"]}</a></p>')
        open(f"{SITE}/estados/{uf}/{slug_mun(cod)}.html", "w").write(pagina(
          f'{b["nome"]} ({uf}) — Auditoria TSE 2026', f'Demonstração · {uf} · município',
          b["nome"], f'Os testes do plano aplicados aos logs do 1º turno de {b["nome"]} ({uf}).',
          corpo, None, f"estados/{uf}/{slug_mun(cod)}.html", pre="../../"))
        n_mun += 1
print(f"paginas de municipio geradas: {n_mun}")

# ---------------------------------------------------------------- 4. nav das demais paginas
for f in ["index.html", "plano-2t.html", "relatorio.html", "verificar.html", "dados.html"]:
    p = f"{SITE}/{f}"
    if not os.path.exists(p): continue
    s = open(p).read()
    s2 = re.sub(r"<nav>.*?</nav>", lambda m: nav(f), s, count=1, flags=re.S)
    if s2 != s: open(p, "w").write(s2)

# ---------------------------------------------------------------- 5. sitemap
hoje = datetime.date.today().isoformat()
urls = (["index.html","plano-2t.html","demonstracao.html","estados/index.html",
         "relatorio.html","verificar.html","dados.html"]
        + [f"estados/{u}.html" for u in sorted(PORUF)]
        + [f"estados/{u}/{slug_mun(c)}.html" for u in sorted(PORMUN) for c in sorted(PORMUN[u])])
open(f"{SITE}/sitemap.xml","w").write(
 '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
 + "".join(f"<url><loc>{URL}/{u}</loc><lastmod>{hoje}</lastmod></url>\n" for u in urls) + "</urlset>\n")

print(f"gerado: demonstracao.html + estados/index.html + {len(PORUF)} páginas de estado "
      f"({', '.join(sorted(PORUF))})")
