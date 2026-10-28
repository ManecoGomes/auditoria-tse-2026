# -*- coding: utf-8 -*-
# Paginas de sintese do site, executadas por gera_demo_html.py (exec) com os mesmos globais:
#   D (1T), D2 (2T ou None), PORUF/PORUF2, bloco(), tabela_janelas(), comparacao_turnos(),
#   svg_serie(), svg_reta(), tabela_rapidas(), pagina(), N, _f, P, SITE, URL, aviso_falta.
# Gera: index.html, primeiro-turno.html, segundo-turno.html, comparativo.html (+ demonstracao.html = alias).
import json as _json, glob as _g, os as _os, csv as _csv

# ---------------------------------------------------------------- dados auxiliares
RESULTADO_OFICIAL = {  # balanco do TSE publicado em 26/10/2026 00h18 (atualizado 00h35)
    "lula": 64256232, "flavio": 59826041, "pct_lula": 51.79, "pct_flavio": 48.21,
    "fonte": "https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/presidente-do-tse-anuncia-reeleicao-de-lula-e-faz-balanco-do-2o-turno-das-eleicoes-2026"}
MARGEM = RESULTADO_OFICIAL["lula"] - RESULTADO_OFICIAL["flavio"]
TSE_34K = {"total": 34393, "17_18": 32399, "18_19": 1981, "apos19": 13, "secoes_abertas_1710": 24268,
           "secoes_apos19": 6766, "secoes_universo": 497333,
           "fonte": "https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/eleicoes-2026-mais-de-34-mil-votos-foram-registrados-apos-as-17h-no-2o-turno"}

def _analises():
    try: return _json.load(open(f"{P}/pipeline/analises.json")).get("blocos") or {}
    except Exception: return {}

def _cobertura_2t():
    """Por UF: secoes no cs.json do Portal Resultados, totalizadas, com arquivos, e processadas."""
    out = {}
    for f in sorted(_g.glob("/Volumes/SSD1TB/acervo-tse/2026-2t/registro_secoes_*.json")):
        try: r = _json.load(open(f))
        except Exception: continue
        secs = r.get("secoes", [])
        tot = sum(1 for s in secs if s.get("st") == "Totalizado")
        ok = sum(1 for s in secs if "arquivos" in s and not s.get("faltam"))
        out[r["uf"]] = {"cs": r.get("n", len(secs)), "totalizadas": tot, "coletadas": ok,
                        "quando": (r.get("coletado_utc") or "")[:16].replace("T", " ") + " UTC",
                        "processada": r["uf"] in PORUF2}
    return out

def _c4b(d):
    return (d or {}).get("C4b_reta_final") or {}

def _jan(d, k):
    return (_c4b(d).get("janelas") or {}).get(k) or {}

def _pct(a, b):
    return (f"{100*a/b:.2f}%".replace(".", ",")) if b else "—"

# ---------------------------------------------------------------- blocos reutilizaveis
def cards_status():
    c1 = (f'<div class="stat"><div class="n">{len(PORUF)}/28</div><div class="l">UFs do 1º turno auditadas</div></div>'
          f'<div class="stat"><div class="n">{N(D["secoes"])}</div><div class="l">seções do 1º turno</div></div>'
          f'<div class="stat"><div class="n">{N(_jan(D,"final").get("discrepantes",0))}</div><div class="l">votos discrepantes após 17h (1º turno)</div></div>')
    if D2:
        c2 = (f'<div class="stat"><div class="n">{len(PORUF2)}/28</div><div class="l">UFs do 2º turno auditadas</div></div>'
              f'<div class="stat"><div class="n">{N(D2["secoes"])}</div><div class="l">seções do 2º turno</div></div>'
              f'<div class="stat{" zero" if _jan(D2,"final").get("discrepantes",0)==0 else ""}"><div class="n">{N(_jan(D2,"final").get("discrepantes",0))}</div><div class="l">votos discrepantes após 17h (2º turno)</div></div>')
    else:
        c2 = '<div class="stat"><div class="n">0/28</div><div class="l">UFs do 2º turno (coleta em curso)</div></div>'
    return f'<div class="grid">{c1}{c2}</div>'

def secao_virada(d2):
    """A pergunta decisiva, respondida com aritmetica sobre os dados existentes."""
    b2 = _jan(d2, "final") if d2 else {}
    v2, disc2, r20 = b2.get("votos", 0), b2.get("discrepantes", 0), b2.get("abaixo_de_20s", 0)
    linhas = ""
    def row(rot, val, nota=""):
        return (f'<tr><td>{rot}</td><td style="text-align:right"><strong>{val}</strong></td>'
                f'<td style="text-align:right">{nota}</td></tr>')
    linhas += row("Margem oficial entre os dois candidatos", N(MARGEM), "TSE, balanço de 26/10")
    linhas += row("Votos necessários para inverter o resultado (metade da margem + 1)", N(MARGEM//2 + 1), "um voto trocado conta duas vezes")
    linhas += row("Votos depois das 17h no 2º turno, levantamento do TSE (27/10)", N(TSE_34K["total"]), f'{_pct(TSE_34K["total"], MARGEM//2+1)} do necessário')
    if d2:
        linhas += row(f'Votos depois das 17h nos logs já auditados ({len(PORUF2)} UFs)', N(v2), f'{_pct(v2, MARGEM//2+1)} do necessário')
        linhas += row("Dos quais discrepantes do ritmo da própria seção", N(disc2), f'{_pct(disc2, MARGEM//2+1)} do necessário')
        linhas += row("Dos quais abaixo de 20 segundos", N(r20), f'{_pct(r20, MARGEM//2+1)} do necessário')
    texto_dados = (f'Nos logs já auditados do 2º turno ({len(PORUF2)} UFs, {N(d2["secoes"])} seções), houve '
                   f'<strong>{N(v2)}</strong> votos depois das 17h, dos quais <strong>{N(disc2)}</strong> discrepantes '
                   f'e <strong>{N(r20)}</strong> abaixo de 20 segundos.') if d2 else \
                  'Os logs do 2º turno estão sendo coletados seção a seção; esta tabela ganha as linhas próprias conforme as UFs entram.'
    return f'''
<h2>A pergunta decisiva: isso poderia ter virado o resultado?</h2>
<p>A hipótese em teste é que, nas duas horas a mais do 2º turno, mesários tenham votado por eleitores ausentes.
Antes de qualquer conclusão sobre <em>se</em> aconteceu, a aritmética responde <em>quanto</em> isso poderia valer.
Para inverter um resultado é preciso trocar metade da margem mais um voto, porque cada voto retirado de um
candidato e dado ao outro conta duas vezes.</p>
<div class="scroll"><table><thead><tr><th>Grandeza</th><th style="text-align:right">Votos</th><th style="text-align:right">Observação</th></tr></thead>
<tbody>{linhas}</tbody></table></div>
<p>{texto_dados} <strong>Mesmo no cenário extremo</strong> — todos os votos depois das 17h fraudulentos e todos para
um só candidato — o conjunto ficaria abaixo de {_pct(max(TSE_34K["total"], v2), MARGEM//2+1)} do necessário para
inverter o resultado. Os testes desta auditoria dizem se houve voto em ritmo incompatível com eleitor real e onde;
não dizem em quem foi cada voto, porque o log registra o cargo e nunca o candidato.</p>
<p><strong>E a "virada" durante a apuração?</strong> O placar parcial muda de líder conforme a ordem em que os boletins
chegam à totalização, que segue a geografia do fechamento das seções, não a hora dos votos. No 1º turno,
100% dos votos entram na contagem depois das 17h porque a transmissão só começa com o encerramento. Uma virada no
placar parcial não é, por si, indício de nada; o que se audita é a sequência de votos dentro de cada urna, antes
de qualquer transmissão. O teste B3 do plano (curva de recebimento dos boletins) mede exatamente a ordem de chegada.</p>
'''

def secao_contexto_2t():
    return f'''
<h2>O que aconteceu em 25 de outubro, com fontes</h2>
<div class="scroll"><table><thead><tr><th>Hora (Brasília)</th><th>Fato</th><th>Fonte</th></tr></thead><tbody>
<tr><td>13h22</td><td>Coligação de Lula pede ao TSE prorrogação por problemas de transporte na Bahia.</td><td><a href="https://www.dgabc.com.br/Noticia/4364886" rel="noopener">DGABC</a>, <a href="https://noticias.uol.com.br/ultimas-noticias/agencia-estado/2026/10/25/pt-recorreu-ao-stf-apos-nunes-marques-nao-decidir-pedido-de-prorrogacao.htm" rel="noopener">UOL/Estadão</a></td></tr>
<tr><td>15h27</td><td>Campanha de Flávio Bolsonaro pede prorrogação por chuvas em SP, PR e SC.</td><td><a href="https://www.dgabc.com.br/Noticia/4364886" rel="noopener">DGABC</a> (fonte única)</td></tr>
<tr><td>16h12</td><td>Presidente do TSE pede informações aos TREs em 30 min, sem decidir.</td><td><a href="https://noticias.uol.com.br/ultimas-noticias/agencia-estado/2026/10/25/pt-recorreu-ao-stf-apos-nunes-marques-nao-decidir-pedido-de-prorrogacao.htm" rel="noopener">UOL/Estadão</a></td></tr>
<tr><td>16h29</td><td>Coligação aciona o STF; Zanin é sorteado relator.</td><td><a href="https://exame.com/brasil/apos-prorrogacao-tse-retoma-totalizacao-dos-votos-e-divulgacao-dos-resultados/" rel="noopener">Exame</a></td></tr>
<tr><td>16h57 a 17h03</td><td>Zanin prorroga a votação até 19h. As fontes divergem no minuto: 16h57 (decisão), 17h01, 17h03 (divulgação).</td><td><a href="https://noticias.stf.jus.br/postsnoticias/stf-prorroga-votacao-ate-as-19h-em-locais-onde-urnas-permaneceram-abertas-apos-as-17h/" rel="noopener">STF</a>, <a href="https://www.conjur.com.br/2026-out-26/o-impossivel-pedido-de-anulacao-das-eleicoes/" rel="noopener">Conjur</a></td></tr>
<tr><td>17h49</td><td>Ofício-Circular GAB-PRES 354/2026 do TSE: seções "que ainda estiverem abertas" ficam até 19h; as já encerradas não reabrem.</td><td><a href="https://static.poder360.com.br/uploads/2026/10/TSE-mantem-sessoes-abertas-ate-as-19h-25-out-2026.pdf" rel="noopener">Ofício (PDF)</a></td></tr>
<tr><td>18h44</td><td>Nota oficial do TSE: recebimento de BUs, totalização e divulgação retomados só após as 19h.</td><td><a href="https://www.tse.jus.br/comunicacao/noticias/2026/Outubro/esclarecimento-sobre-prorrogacao-da-votacao" rel="noopener">TSE</a></td></tr>
<tr><td>26/10, 00h18</td><td>Balanço oficial: Lula {N(RESULTADO_OFICIAL["lula"])} ({RESULTADO_OFICIAL["pct_lula"]}%) × Flávio {N(RESULTADO_OFICIAL["flavio"])} ({RESULTADO_OFICIAL["pct_flavio"]}%). O TSE reconhece "acúmulo de arquivos à espera de processamento".</td><td><a href="{RESULTADO_OFICIAL["fonte"]}" rel="noopener">TSE</a></td></tr>
<tr><td>26/10, noite</td><td>PL reconhece o resultado proclamado; campanha de Flávio fala em AIJE por abuso de poder, não em anulação.</td><td><a href="https://g1.globo.com/politica/eleicoes/2026/noticia/2026/10/26/pl-reconhece-resultado-das-eleicoes.ghtml" rel="noopener">g1</a>, <a href="https://valor.globo.com/politica/eleicoes-2026/noticia/2026/10/26/flavio-bolsonaro-afirma-que-pedira-cassacao-da-chapa-de-lula.ghtml" rel="noopener">Valor</a></td></tr>
<tr><td>27/10, 15h21</td><td>TSE divulga levantamento: {N(TSE_34K["total"])} votos depois das 17h ({N(TSE_34K["17_18"])} entre 17h e 18h, {N(TSE_34K["18_19"])} entre 18h e 19h, {TSE_34K["apos19"]} após 19h); {N(TSE_34K["secoes_abertas_1710"])} seções abertas depois das 17h10; {N(TSE_34K["secoes_apos19"])} encerradas após 19h.</td><td><a href="{TSE_34K["fonte"]}" rel="noopener">TSE</a></td></tr>
</tbody></table></div>
<p>O dado "totalização interrompida às 17h06 com 0,25% apurado" circula na imprensa (Valor, O Globo) mas não consta
de documento oficial; fica registrado como relato de imprensa. O levantamento do TSE de 34.393 votos não traz base
por seção nem metodologia reproduzível; o g1 chegou a 35.521 numa primeira versão e corrigiu para 34.330, e a
diferença de 63 votos para o número do TSE não tem explicação publicada. Esta auditoria produz o mesmo número a
partir dos logs, seção a seção, e o publica ao lado — por UF, na tabela de estados, e no total nacional.</p>

<h2>Por que o pacote oficial do 2º turno ainda não saiu, e por que isso não nos impede</h2>
<p>O calendário eleitoral (Res. TSE 23.760/2026) obriga a divulgar os boletins "à medida que forem recebidos" no dia
da eleição e abre, no dia seguinte, o pedido de logs e RDV pelas entidades fiscalizadoras, com cinco dias úteis para
atendimento (Res. 23.673/2021, art. 49). <strong>Não há prazo normativo</strong> para o pacote consolidado por UF no
portal de dados abertos; em 2022 ele saiu dois a três dias depois do turno, em 2024 também.</p>
<p>A pesquisa completa que sustenta esta seção — cronologia com horários, números do TSE e da imprensa, normas,
contradições entre fontes e avaliação de confiabilidade de cada fonte — está publicada no repositório:
<a href="https://github.com/ManecoGomes/auditoria-tse-2026/blob/main/relatorio/PESQUISA-PUBLICACAO-2T.md" rel="noopener">relatorio/PESQUISA-PUBLICACAO-2T.md</a>.</p>
<p>Os mesmos arquivos, porém, ficam públicos <strong>seção por seção</strong> no Portal Resultados assim que a seção é
totalizada — boletim, log, RDV e arquivo de votação, identificados por hash. Esta auditoria coleta por esse caminho e
remonta, por UF, um ZIP com os mesmos membros e os mesmos nomes do pacote oficial. Quando o pacote sair, os dois são
conferidos membro a membro, e a conferência é publicada.</p>
'''

def tabela_cobertura_2t(cob):
    if not cob: return "<p><em>Coleta do 2º turno ainda não iniciada.</em></p>"
    rows = ""
    tcs = ttot = tcol = 0
    for uf in sorted(cob):
        c = cob[uf]; tcs += c["cs"]; ttot += c["totalizadas"]; tcol += c["coletadas"]
        rows += (f'<tr><td>{uf}</td><td style="text-align:right">{N(c["cs"])}</td><td style="text-align:right">{N(c["totalizadas"])}</td>'
                 f'<td style="text-align:right">{N(c["coletadas"])}</td><td>{"sim" if c["processada"] else "em fila"}</td><td>{c["quando"]}</td></tr>')
    rows += (f'<tr><td><strong>{len(cob)} UFs</strong></td><td style="text-align:right"><strong>{N(tcs)}</strong></td>'
             f'<td style="text-align:right"><strong>{N(ttot)}</strong></td><td style="text-align:right"><strong>{N(tcol)}</strong></td><td></td><td></td></tr>')
    return ('<div class="scroll"><table><thead><tr><th>UF</th><th style="text-align:right">Seções no<br>Portal Resultados</th>'
            '<th style="text-align:right">Totalizadas</th><th style="text-align:right">Com os 4 arquivos</th><th>Auditada</th><th>Coleta</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
            '<p>A diferença entre "seções no Portal" e "totalizadas" são seções agregadas, que votam em outra urna e não têm arquivos próprios — o mesmo ocorre no 1º turno.</p>')

def tabela_uf_comparativo():
    rows = ""
    for uf in sorted(PORUF):
        d1 = PORUF[uf]; d2 = PORUF2.get(uf)
        b1 = _jan(d1, "final"); b2 = _jan(d2, "final") if d2 else {}
        def cell(v, strong=False):
            s = "—" if v is None else (N(v) if isinstance(v, int) else str(v))
            return f'<td style="text-align:right">{"<strong>"+s+"</strong>" if strong else s}</td>'
        rows += (f'<tr><td><a href="estados/{uf}.html">{uf}</a></td>'
                 + cell(b1.get("votos")) + cell(b2.get("votos") if d2 else None)
                 + cell(_pct(b1.get("votos",0), d1["votos_presidente"])) + cell(_pct(b2.get("votos",0), d2["votos_presidente"]) if d2 else None)
                 + cell(_f(b1.get("media_ate_120s"))) + cell(_f(b2.get("media_ate_120s")) if d2 else None)
                 + cell(b1.get("discrepantes")) + cell(b2.get("discrepantes") if d2 else None, True)
                 + cell(b1.get("abaixo_de_20s")) + cell(b2.get("abaixo_de_20s") if d2 else None, True)
                 + cell(_c4b(d1).get("secoes_final_rapida")) + cell(_c4b(d2).get("secoes_final_rapida") if d2 else None, True) + '</tr>')
    return ('<div class="scroll"><table><thead><tr><th>UF</th><th style="text-align:right">Votos após 17h<br>1T</th><th style="text-align:right">2T</th>'
            '<th style="text-align:right">% do total<br>1T</th><th style="text-align:right">2T</th>'
            '<th style="text-align:right">Atendimento após 17h<br>1T</th><th style="text-align:right">2T</th>'
            '<th style="text-align:right">Discrepantes<br>1T</th><th style="text-align:right">2T</th>'
            '<th style="text-align:right">&lt;20 s<br>1T</th><th style="text-align:right">2T</th>'
            '<th style="text-align:right">Seções rápidas<br>1T</th><th style="text-align:right">2T</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')

def tabela_nacional_comparativo():
    def g(d, path, default="—"):
        try:
            x = d
            for k in path: x = x[k]
            return x
        except Exception: return default
    itens = [
        ("Seções auditadas", ["secoes"]), ("Votos para Presidente", ["votos_presidente"]),
        ("Urnas identificadas", ["urnas_distintas"]),
        ("A2 — seções com boletim ≠ log", ["A2_triangulacao", "divergentes"]),
        ("A4 — urna divergente sem explicação", ["A4_identidade_da_urna", "sem_explicacao"]),
        ("C1 — seções com voto após o lacre", ["C1_secoes_com_voto_apos_lacre"]),
        ("C2 — votos após 17h", ["C2_votos_apos_17h"]), ("C2 — votos após 19h", ["C2_apos_19h"]),
        ("C4 — intervalos &lt; 20 s no dia inteiro", ["C4_intervalos", "abaixo_de_20s"]),
        ("C4b — votos discrepantes até 17h (bloco A)", ["C4b_reta_final", "janelas", "antes", "discrepantes"]),
        ("C4b — votos discrepantes após 17h (bloco B)", ["C4b_reta_final", "janelas", "final", "discrepantes"]),
        ("C4b — tempo médio por voto, bloco A", ["C4b_reta_final", "janelas", "antes", "media_s"]),
        ("C4b — tempo médio por voto, bloco B", ["C4b_reta_final", "janelas", "final", "media_s"]),
        ("C4b — atendimento (≤120 s), bloco A", ["C4b_reta_final", "janelas", "antes", "media_ate_120s"]),
        ("C4b — atendimento (≤120 s), bloco B", ["C4b_reta_final", "janelas", "final", "media_ate_120s"]),
        ("C4b — seções com mediana &lt; 20 s após 17h", ["C4b_reta_final", "secoes_final_rapida"]),
        ("C6 — habilitações sem voto computado", ["C6_hab_menos_comput"]),
    ]
    rows = ""
    for rot, path in itens:
        v1 = g(D, path); v2 = g(D2, path) if D2 else "—"
        # A2/A4 exigem boletim; sem bweb do 2T a comparacao nao existe (nao e "zero")
        if D2 and path[0] in ("A2_triangulacao", "A4_identidade_da_urna") and not g(D2, [path[0], "secoes_comparadas"], 0):
            v2 = "— (sem boletim)"
        fmt = lambda v: "—" if v in (None, "—") else (N(v) if isinstance(v, int) else (f"{v:.0f} s" if isinstance(v, float) else str(v)))
        rows += f'<tr><td>{rot}</td><td style="text-align:right">{fmt(v1)}</td><td style="text-align:right"><strong>{fmt(v2)}</strong></td></tr>'
    return ('<div class="scroll"><table><thead><tr><th>Medida</th><th style="text-align:right">1º turno</th><th style="text-align:right">2º turno</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')

def secao_e6():
    e6 = _analises().get("E6_janela_final_secoes") or {}
    if "secoes_comuns_com_10_votos_na_janela_2t" not in e6:
        return '<p><em>A comparação seção a seção (bloco E6) sai quando houver logs dos dois turnos para as mesmas seções.</em></p>'
    v = e6.get("variacao_media_final_2t_menos_1t_s") or {}
    return (f'<p>Seções presentes nos dois turnos com 10 ou mais votos depois das 17h no 2º: <strong>{N(e6["secoes_comuns_com_10_votos_na_janela_2t"])}</strong>. '
            f'Votos discrepantes depois das 17h nessas seções: <strong>{N(e6["votos_discrepantes_apos_17h_2t"])}</strong> no 2º turno contra '
            f'{N(e6["votos_discrepantes_apos_17h_1t_mesmas_secoes"])} no 1º. Seções com discrepantes no 2º <strong>sem ter tido nenhum no 1º</strong>: '
            f'<strong>{N(e6["secoes_2t_com_discrepantes_sem_ter_no_1t"])}</strong>. Seções com mediana abaixo de 20 s depois das 17h: '
            f'{N(e6["secoes_2t_mediana_final_abaixo_20s"])} no 2º turno ({N(e6["secoes_1t_mediana_final_abaixo_20s"])} no 1º). '
            f'Variação do tempo médio por voto depois das 17h (2º menos 1º), mediana {_f(v.get("mediana"))} (p10 {_f(v.get("p10"))}, p90 {_f(v.get("p90"))}).</p>')

# ---------------------------------------------------------------- 1. index.html (Resumo)
corpo_index = f'''
<h2>Objetivo</h2>
<p>Verificar, com os dados públicos do Tribunal Superior Eleitoral e por método publicado <strong>antes</strong> de os
dados existirem, se houve voto registrado fora das regras nas Eleições Gerais de 2026 — e, em especial, responder a
uma pergunta concreta sobre o 2º turno: <strong>nas duas horas a mais concedidas no dia 25 de outubro, entre 17h e
19h, houve votos registrados em ritmo incompatível com eleitor real, quantos foram e em quais urnas?</strong></p>
<p>A hipótese testada é a descrita por Flávio Dino em <a href="reta-final.html">discurso que motivou este trabalho</a>:
encerrada a fila, o mesário libera a urna com o número do título de eleitores ausentes e vota por eles. Voto assim é
voto rápido demais, e voto rápido demais fica gravado no log da urna, segundo a segundo.</p>
<p>O 1º turno, que encerrou às 17h e não teve contestação relevante, é a <strong>régua do tempo normal</strong>: ele
diz quanto dura um voto real, em cada seção, e quantos votos "rápidos demais" existem num dia comum.</p>

{cards_status()}

<h2>Como funciona</h2>
<ol>
<li><strong>Coleta e integridade.</strong> Boletins de urna, logs, RDV e arquivos de votação de todas as seções do país.
No 1º turno, os pacotes oficiais por UF (28 de 28), com integridade provada arquivo a arquivo. No 2º turno, os
mesmos arquivos coletados <a href="segundo-turno.html">seção por seção no Portal Resultados</a> — boletim, log, RDV e
contêiner de assinatura de cada seção —, porque o pacote consolidado por UF não tem prazo e ainda não saiu. <strong>Os logs do 2º turno já estão
no acervo e em análise</strong>; o que falta é só o pacote oficial, que servirá para conferência quando sair.</li>
<li><strong>Testes pré-registrados.</strong> O <a href="plano-2t.html">plano</a> foi publicado em 26/10/2026, antes dos
dados do 2º turno, com data ancorada na blockchain do Bitcoin: integridade (A), horários (B), comportamento das
urnas pelo log (C), impossibilidades lógicas (D), comparação entre turnos seção a seção (E), geografia (F) e dispersão
da ordem de prorrogação (G).</li>
<li><strong>Emenda datada.</strong> O teste C4b — tempo por voto até as 17h contra depois das 17h, com contagem de
votos discrepantes — foi acrescentado em 27/10, antes de qualquer dado do 2º turno, e está
<a href="reta-final.html">identificado como posterior ao plano</a>.</li>
<li><strong>Publicação contínua e verificável.</strong> Cada UF entra no site quando termina. Todo arquivo publicado tem
SHA-512 num manifesto carimbado; scripts, dados derivados e a lista de seções apontadas são públicos.</li>
</ol>

<h2>O que este trabalho pode e não pode afirmar</h2>
<p><strong>Pode:</strong> quantos votos, em cada seção, foram registrados num ritmo incompatível com um eleitor real,
e se isso aconteceu mais depois das 17h do que no dia normal — no 2º turno e, como régua, no 1º.</p>
<p><strong>Não pode:</strong> dizer em quem foi qualquer voto. O log registra o cargo, nunca o candidato; o RDV traz os
votos embaralhados. É o mecanismo do sigilo do voto, e nenhuma análise de dados públicos o atravessa.</p>

{secao_virada(D2)}

<h2>Onde está cada coisa</h2>
<ul>
<li><a href="primeiro-turno.html"><strong>1º turno — auditoria completa</strong></a>: todos os testes sobre as {len(PORUF)} UFs, estado por estado e município por município.</li>
<li><a href="segundo-turno.html"><strong>2º turno — em andamento</strong></a>: coleta por seção, o que aconteceu em 25/10 com fontes, e os mesmos testes conforme cada UF entra.</li>
<li><a href="comparativo.html"><strong>Comparativo 1º × 2º turno</strong></a>: as discrepâncias, explicadas, e a pergunta sobre o resultado.</li>
<li><a href="reta-final.html"><strong>Reta final</strong></a>: a hipótese, o vídeo, o teste C4b e as seções apontadas.</li>
<li><a href="verificar.html">Como verificar</a> · <a href="dados.html">Dados e hashes</a> · <a href="relatorio.html">Relatório técnico dos boletins do 1º turno</a></li>
</ul>

<h2>Análises posteriores ao plano (emenda de 28/10/2026)</h2>
<p>Acrescentadas depois de os dados existirem, a pedido de quem encomendou a auditoria, e por isso identificadas como posteriores — força probatória menor que
a dos testes pré-registrados. Os logs usados são os de todas as seções, obtidos do Portal Resultados do TSE e conferidos contra o hash que a própria urna assinou.</p>
<ul>
<li><a href="forense.html"><strong>Forense dos logs</strong></a>: há rastro de edição — humana, por programa ou por IA — nos logs do 1º e do 2º turno? Gramática, codificação, vocabulário, relógio, selo, hash assinado pela urna.</li>
<li><a href="soma-oficial.html"><strong>Soma dos boletins × resultado oficial</strong></a>: a totalização bate com a soma de todos os boletins? E alguém tinha 50% + 1 no 1º turno?</li>
<li><a href="votos-tardios.html"><strong>Votos depois das 17h: para quem?</strong></a>: o que o dado permite dizer, com os limites exatos, nos dois turnos.</li>
</ul>
'''
open(f"{SITE}/index.html", "w").write(pagina(
    "Auditoria independente das Eleições 2026", "Auditoria independente · Eleições Gerais 2026",
    "Auditoria independente das Eleições 2026",
    "Dados públicos do TSE, método publicado antes dos dados, resultados seção por seção.",
    corpo_index, "index.html", "index.html"))

# ---------------------------------------------------------------- 2. primeiro-turno.html
corpo_1t = f'''
<blockquote><p><strong>O 1º turno é a régua.</strong> Votação encerrada às 17h, sem contestação relevante. Tudo o que
se mede no 2º turno é confrontado com o que estes mesmos testes acharam aqui — e o que acharam está abaixo, sem omitir
os testes que não acusaram nada.</p></blockquote>
<h2>Universo e integridade</h2>
<p><strong>{len(PORUF)} de 28 unidades da Federação</strong>, {N(D["secoes"])} seções com log, {N(D["votos_presidente"])} votos para
Presidente, {N(D["urnas_distintas"])} urnas identificadas pelo número de série. Os 28 pacotes oficiais de log foram baixados
do portal de dados abertos do TSE e provados íntegros (o ZIP abre inteiro; o TSE não publica hash desses pacotes). Os
boletins de urna (28 de 28) tiveram SHA-512 conferido contra o publicado pelo TSE. {aviso_falta}</p>
<h2>Boletins de urna: horários e impossibilidades lógicas</h2>
<p>Sobre os 499.206 boletins do 1º turno (125,3 milhões de votantes): comparecimento maior que aptos, 0; encerramento
antes da abertura, 0; boletim emitido antes do encerramento, 0; seção com mais de um registro de urna, 0; abertura
após 8h30, 960; encerramento administrativo após 19h, 8.324 (1,67%) — cauda operacional ordinária.
<a href="relatorio.html">Relatório técnico completo</a>.</p>
''' + bloco(D, "nacional") + f'''
<h2>Estado por estado e município por município</h2>
<p>Os mesmos testes, isolados por UF, estão no <a href="estados/index.html">índice de estados</a>; cada estado abre em
páginas por município ({N(D.get("municipios",0))} municípios), com a curva de votação e a distribuição de intervalos daquela cidade.</p>
<h2>Seções apontadas pelo teste C4b (depois das 17h)</h2>
{tabela_rapidas(f"{P}/pipeline/secoes_rapidas_janela_final.csv")}
<p>Dados brutos: <code>dados/analises/demonstracao_1t.json</code>, <code>demonstracao_secoes.csv</code> (uma linha por seção),
<code>secoes_rapidas_janela_final.csv</code>.</p>
'''
html_1t = pagina("1º turno — auditoria completa — Auditoria TSE 2026", "1º turno · 4 de outubro de 2026",
                 "1º turno: a auditoria completa", "Todos os testes do plano, sobre todas as seções com log, publicados inteiros.",
                 corpo_1t, "primeiro-turno.html", "primeiro-turno.html")
open(f"{SITE}/primeiro-turno.html", "w").write(html_1t)
open(f"{SITE}/demonstracao.html", "w").write(html_1t.replace("primeiro-turno.html", "demonstracao.html", 2))  # alias de links antigos

# ---------------------------------------------------------------- 3. segundo-turno.html
cob = _cobertura_2t()
corpo_2t = f'''
<blockquote><p><strong>Auditoria em andamento.</strong> O 2º turno foi em 25/10/2026, com a votação prorrogada até as 19h
nas seções ainda abertas. O pacote oficial por UF ainda não foi publicado; os arquivos de cada seção estão públicos no
Portal Resultados desde a noite de 25/10 e é de lá que esta auditoria os coleta, UF por UF.</p></blockquote>
<h2>Cobertura da coleta</h2>
{tabela_cobertura_2t(cob)}
''' + (bloco(D2, "nacional") if D2 else '<h2>Testes</h2><p><em>Os testes saem aqui assim que a primeira UF for coletada e processada.</em></p>') + f'''
<h2>Seções apontadas pelo teste C4b (depois das 17h)</h2>
{tabela_rapidas(f"{P}/pipeline/secoes_rapidas_janela_final_2t.csv")}
{secao_contexto_2t()}
<h2>Estado por estado</h2>
<p>As UFs do 2º turno já processadas aparecem nas <a href="estados/index.html">páginas de estado</a>, ao lado do 1º turno,
e nas páginas de município. A comparação entre os turnos está no <a href="comparativo.html">comparativo</a>.</p>
<p>Dados brutos: <code>dados/analises/demonstracao_2t.json</code>, <code>demonstracao_secoes_2t.csv</code>,
<code>secoes_rapidas_janela_final_2t.csv</code>; registro da coleta por seção em <code>dados/2t/registro_secoes_UF.json</code>
(hash, data e hora de recebimento e situação de cada seção, conforme o Portal Resultados).</p>
'''
open(f"{SITE}/segundo-turno.html", "w").write(pagina(
    "2º turno — auditoria em andamento — Auditoria TSE 2026", "2º turno · 25 de outubro de 2026",
    "2º turno: a auditoria em andamento",
    "Coleta seção por seção, os mesmos testes do 1º turno e o que aconteceu no dia 25, com fontes.",
    corpo_2t, "segundo-turno.html", "segundo-turno.html"))

# ---------------------------------------------------------------- 4. comparativo.html
corpo_cmp = f'''
<blockquote><p>Cada medida do 2º turno ao lado da mesma medida no 1º. Diferença não é irregularidade: no 2º turno
o eleitor votou em menos cargos (voto mais rápido em todo o dia) e houve duas horas a mais de urna aberta nas seções
que ainda tinham fila. O que exige explicação está marcado: votos discrepantes do ritmo da própria seção, intervalos
abaixo de 20 segundos e seções com mediana abaixo de 20 segundos depois das 17h.</p></blockquote>
<h2>Nacional, medida a medida</h2>
{tabela_nacional_comparativo()}
<h2>Depois das 17h, janela a janela</h2>
{comparacao_turnos(_c4b(D), _c4b(D2)) if D2 else "<p><em>Aguardando as primeiras UFs do 2º turno.</em></p>"}
<h2>A mesma seção contra ela mesma (bloco E6)</h2>
{secao_e6()}
<h2>Estado por estado</h2>
{tabela_uf_comparativo()}
{secao_virada(D2)}
<h2>Como ler uma discrepância</h2>
<p>Quando uma medida do 2º turno destoa do 1º, o site mostra onde (UF, município, seção e urna) e o motivo pelo qual
foi apontada. Há três explicações a esgotar antes de falar em fraude, e todas são testáveis nos próprios dados:
a cédula menor do 2º turno (o atendimento cai em todo o dia, não só depois das 17h); fila legítima nas seções que
ficaram abertas (o tempo por voto cai, mas o atendimento e os votos discrepantes não); e troca de urna ou abertura
tardia (seção sem base antes das 17h, tratada pelo piso de 20 s e pelos testes A4 e B2). O que sobra depois disso é
o que esta auditoria publica como <strong>a explicar</strong>, com a urna identificada.</p>
'''
open(f"{SITE}/comparativo.html", "w").write(pagina(
    "Comparativo 1º × 2º turno — Auditoria TSE 2026", "Comparativo · 1º × 2º turno",
    "1º turno contra 2º turno", "As discrepâncias, explicadas, e a resposta à pergunta sobre o resultado.",
    corpo_cmp, "comparativo.html", "comparativo.html"))
print("paginas de sintese: index, primeiro-turno (+demonstracao), segundo-turno, comparativo")
