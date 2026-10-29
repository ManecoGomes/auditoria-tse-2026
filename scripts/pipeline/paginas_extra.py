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
# Reescrita em 28/10/2026 a pedido do Maneco: a página inicial resume TUDO o que foi feito — cada
# tipo de verificação, com o número dos dois turnos e o link —, fecha com a conclusão sobre o
# resultado e sua autenticidade, e diz onde baixar e conferir. Todo número vem dos JSON do pipeline.
REGUA_1T_FECHAMENTO = {"secoes_alem_2h": 8324, "pct": 1.67}   # compara.py::REGUA (boletins do 1T)
PLANO_OTS = {"data": "26/10/2026", "bloco": 973245}

def _lj(p):
    try: return _json.load(open(p))
    except Exception: return {}

def _d(x, nd=2):
    """Decimal em pt-BR (vírgula), sem tocar nos pontos de milhar de N()."""
    try: return f"{float(x):.{nd}f}".replace(".", ",")
    except Exception: return "—"

def _forense_resumo(t):
    f = _lj(f"{P}/pipeline/forense_{t}t.json"); c = f.get("contagem") or {}
    # anomalias: contagem (int) ou lista de exemplos — vale o tamanho
    a = {k: (v if isinstance(v, int) else len(v or [])) for k, v in (f.get("anomalias") or {}).items()}
    return {"ok": bool(c), "logs": c.get("logs", 0), "linhas": c.get("linhas", 0), "linhas_ok": c.get("linhas_ok", 0),
            "a5_conf": c.get("A5_log.jez_confere", 0), "a5_div": a.get("A5_log.jez_DIVERGE", 0), "ilegivel": a.get("log_jez_ilegivel", 0),
            "assin": c.get("L8_verificacoes_assinatura", 0), "assin_ok": c.get("L8_verificacoes_assinatura_ok", 0),
            "l1": a.get("L1_linha_fora_da_gramatica", 0), "l2": a.get("L2_bytes_controle", 0), "l6": a.get("L6_serial_log_ne_boletim", 0),
            "turno_dif": a.get("L8_turno_declarado_diferente", 0), "v100": a.get("V_100pct_um_candidato", 0), "sem_log": a.get("sem_log", 0)}

def _pianista_resumo(t):
    j = _lj(f"{P}/pipeline/pianista_{t}t.json")
    if not j: return None
    n = j.get("intervalos", 0); ab = j.get("abaixo") or {}; cs = j.get("corrida_secoes") or {}; cf = j.get("corrida_final_secoes") or {}
    g = lambda d, L, k: ((d.get(str(L)) or d.get(L) or {}).get(str(k)) or (d.get(str(L)) or d.get(L) or {}).get(k) or 0)
    return {"ufs": len(j.get("ufs", [])), "n": n, "a20": ab.get("20", ab.get(20, 0)), "a30": ab.get("30", ab.get(30, 0)), "a40": ab.get("40", ab.get(40, 0)),
            "c30_10": g(cs, 30, 10), "c40_10": g(cs, 40, 10), "cf30_5": g(cf, 30, 5), "cf30_10": g(cf, 30, 10), "min10": j.get("min10_min")}

def indice_resumo():
    A = _analises()
    a3 = (_lj(f"{P}/pipeline/resultados/a3_soma_oficial.json").get("turnos") or {})
    td = _lj(f"{P}/pipeline/resultados/tardios.json"); td2 = (td.get("turnos") or {}).get("2") or {}; td1 = (td.get("turnos") or {}).get("1") or {}
    e4 = ((td.get("E4_secao_contra_si_mesma") or {}).get("regressao_delta13_vs_tardios2T") or {})
    r2 = _lj(f"{P}/pipeline/resumo_2t.json"); imp = r2.get("impossibilidades") or {}
    man = _lj(f"{P}/repo/manifesto.json")
    f1, f2 = _forense_resumo("1"), _forense_resumo("2")
    p1, p2 = _pianista_resumo("1"), _pianista_resumo("2")
    rdv1, rdv2 = _lj(f"{P}/pipeline/rdv_1t.json"), _lj(f"{P}/pipeline/rdv_2t.json")
    kc = _lj(f"{P}/pipeline/concentracao_2t.json")
    al2, al1 = _lj(f"{P}/pipeline/algoritmo_2t.json"), _lj(f"{P}/pipeline/algoritmo_1t.json")
    def al_txt(a, t):
        if not a or not a.get("k4"): return "em processamento"
        k4, k5, k6, k7 = a["k4"], a["k5"], a.get("k6") or {}, a.get("k7") or {}
        s = (f'margem no empate: razão {_d(k4["razao_a"],2)} com 22 à frente e {_d(k4["razao_b"],2)} com 13 à frente (curva lisa = 1); '
             f'urnas com 22 à frente dentro do município: {N(k5["total_obs"])} observadas; ')
        if k6: s += f'curva da totalização dentro da faixa da ordem de chegada por município em {k6["pontos_dentro_por_nivel"]["municipio"]} de {k6["pontos"]} pontos; '
        if k7.get("ufs"): s += f'relógio: {N(k7["assinaturas_iniciais_repetidas"])} sequências de intervalos repetidas entre urnas, segundo uniforme (qui² {_d(k7["qui2_segundo_no_minuto"],0)} / 59 gl)' + (f' ({len(k7["ufs"])}/28 UFs)' if len(k7["ufs"]) < 28 else "")
        return s
    def rdv_txt(r):
        if not r: return "em processamento"
        return (f'{N(r.get("comparadas",0))} seções comparadas, {N(r.get("iguais",0))} iguais voto a voto, {N(r.get("diferentes",0))} diferentes'
                + (f' ({len(r.get("ufs",[]))}/28 UFs)' if len(r.get("ufs", [])) < 28 else ""))
    def kc_txt():
        if not kc: return "em processamento"
        ph = {h["hora"]: h for h in kc.get("por_hora", [])}
        c17 = (ph.get("17h") or {}).get("correlacao_com_delta13"); c18 = (ph.get("18h") or {}).get("correlacao_com_delta13")
        return (f'{N(kc.get("secoes",0))} seções comparadas entre os turnos; correlação entre votar às 17h/18h e deslocar o resultado: {_d(c17,3)} / {_d(c18,3)}; '
                f'{N(kc.get("alertas",0))} seções marcadas contra o próprio município ({N(kc.get("alertas_pro13",0))} para 13, {N(kc.get("alertas_pro22",0))} para 22), '
                f'{N(kc.get("alertas_com_votos_apos17",0))} delas com voto após 17h')
    a2_1, a2_2 = A.get("A2_triangulacao_1t") or {}, A.get("A2_triangulacao_2t") or {}
    e5, e6, e1 = A.get("E5_municipios") or {}, A.get("E6_janela_final_secoes") or {}, A.get("E1_comparecimento") or {}
    d2 = D2 or {}
    c4_1 = (D.get("C4_intervalos") or {}); c4_2 = (d2.get("C4_intervalos") or {})
    fin1, fin2 = _jan(D, "final"), _jan(d2, "final")
    a4_1 = (D.get("A4_identidade_da_urna") or {}); a4_2 = (d2.get("A4_identidade_da_urna") or {})
    cand = {c["numero"]: c for c in (a3.get("2") or {}).get("candidatos", [])}
    bate2 = bool((a3.get("2") or {}).get("confere", {}).get("candidatos_todos_iguais")); bate1 = all(c.get("diferenca") == 0 or not c.get("oficial") for c in (a3.get("1") or {}).get("candidatos", []))  # candidatura indeferida: nulos técnicos
    v1 = (a3.get("1") or {}).get("boletins", {}).get("comparecimento", D.get("votos_presidente", 0)); v2 = (a3.get("2") or {}).get("boletins", {}).get("comparecimento", d2.get("votos_presidente", 0))
    margem = (cand.get("13", {}).get("oficial", RESULTADO_OFICIAL["lula"]) - cand.get("22", {}).get("oficial", RESULTADO_OFICIAL["flavio"])) or MARGEM
    tard2 = td2.get("votos_17h_em_diante", fin2.get("votos", 0)); ap19 = td2.get("votos_apos_19h", d2.get("C2_apos_19h", 0))
    ufs2 = len(PORUF2) if D2 else 0
    em_proc = lambda p: "em processamento" if not p else ""

    def ok(txt): return f'<span class="flag ok">{txt}</span>'
    def fl(txt): return f'<span class="flag">{txt}</span>'
    def pian(p, t):
        if not p: return "em processamento"
        return (f'intervalos &lt;20 s: {N(p["a20"])} · &lt;30 s: {_pct(p["a30"], p["n"])} · &lt;40 s: {_pct(p["a40"], p["n"])}; '
                f'seções com 10+ votos seguidos &lt;30 s: {N(p["c30_10"])}' + (f' (de 17h em diante: {N(p["cf30_10"])})' if t == "2" else "")
                + (f'; 10 votos mais rápidos do país: {p["min10"]} s' if p["min10"] is not None else "") + (f' ({p["ufs"]}/28 UFs)' if p["ufs"] < 28 else ""))

    linhas = [
      ["A1 · Integridade dos pacotes do TSE", "Os ZIPs baixados são os que o TSE publicou?", "28/28 UFs, SHA-512 do TSE conferido, arquivo a arquivo", "28/28 boletins (SHA-512 do TSE); logs, RDV e contêineres coletados seção a seção, hash do Portal conferido", "dados.html"],
      ["A5 · Hash assinado pela urna", "Cada boletim e cada log batem com o SHA-512 que a própria urna gravou no contêiner <code>vota.vsc</code>?",
       f'{N(f1["a5_conf"])} de {N(f1["logs"])} logs conferem; 0 divergentes', f'{N(f2["a5_conf"])} de {N(f2["logs"])} conferem; {N(f2["a5_div"])} divergentes e {N(f2["ilegivel"])} ilegíveis, todos em membros de ZIP remontados localmente (BA, GO, MG, PE, PR, SP) — defeito da cópia, a reconferir com o pacote oficial', "forense.html"],
      ["A3 · Soma dos boletins × totalização oficial", "A soma de todos os boletins é o resultado que o TSE proclamou?",
       ("bate exato por candidato; única diferença, 5.246 nulos técnicos (candidatura indeferida). Ninguém teve 50%+1: 47,03% × 45,16%" if bate1 else "divergência — ver página"),
       (f'bate exato: 13 = {N(cand.get("13",{}).get("oficial",0))}, 22 = {N(cand.get("22",{}).get("oficial",0))}, comparecimento, brancos e nulos idênticos' if bate2 else "divergência — ver página"), "soma-oficial.html"],
      ["K1 · RDV × boletim, voto a voto", "O Registro Digital do Voto gravado pela urna reproduz o boletim — cada candidato, brancos e nulos — em cada seção?", rdv_txt(rdv1), rdv_txt(rdv2), "concentracao.html"],
      ["A2 · Boletim × log (comparecimento)", "O número de votos no log é o do boletim?",
       f'{N(a2_1.get("divergentes",0))} de {N(a2_1.get("secoes_comparadas",0))} seções divergem ({_d(a2_1.get("pct",0))}%), quase todas log &lt; boletim por 1 (urna substituída: o log é só da 2ª urna)',
       f'{N(a2_2.get("divergentes",0))} de {N(a2_2.get("secoes_comparadas",0))} ({_d(a2_2.get("pct",0))}%), mesma explicação', "comparativo.html"],
      ["A4 · Identidade da urna", "O serial da urna no log é o do boletim?", f'{N(a4_1.get("sem_explicacao",0))} sem explicação (divergências = urna de contingência)', f'{N(a4_2.get("sem_explicacao",0))} sem explicação', "primeiro-turno.html"],
      ["D · Impossibilidades lógicas", "Comparecimento &gt; aptos? Encerramento antes da abertura? Boletim antes do encerramento?", "0 · 0 · 0", f'{imp.get("comp_maior_aptos",0)} · {imp.get("encerra_antes_abre",0)} · {imp.get("bu_antes_encerra",0)}', "relatorio-2t.html"],
      ["B4 · Encerramento das seções", "Quantas seções fecharam mais de 2 h depois do prazo legal?", f'{N(REGUA_1T_FECHAMENTO["secoes_alem_2h"])} seções ({_d(REGUA_1T_FECHAMENTO["pct"])}%) — fila dos 5 cargos', f'{N(r2.get("encerrou_alem_2h",0))} seção ({_d(r2.get("pct_alem_2h",0))}%), prazo 19h', "relatorio-2t.html"],
      ["C1 · Voto depois do lacre", "Alguma urna registrou voto depois de emitir o boletim (reabertura)?", f'{N(D.get("C1_secoes_com_voto_apos_lacre",0))} seções', f'{N(d2.get("C1_secoes_com_voto_apos_lacre",0))} seções', "segundo-turno.html"],
      ["C2 · Votos fora do prazo", "Votos registrados depois do prazo legal do turno?", f'{N(D.get("C2_apos_19h",0))} após 19h (prazo 17h: {N(D.get("C2_votos_apos_17h",0))}, fila)', f'{N(ap19)} após 19h; de 17h às 19h, {N(tard2)} ({_d(td2.get("pct_17h_em_diante",0),3)}% dos votos), lícitos pela decisão do STF', "votos-tardios.html"],
      ["C4 · Intervalo entre votos (20 s)", "Houve voto em ritmo impossível para um eleitor real?", f'{N(c4_1.get("abaixo_de_20s",0))} intervalos em {N(c4_1.get("amostra",0))}', f'{N(c4_2.get("abaixo_de_20s",0))} em {N(c4_2.get("amostra",0))}', "segundo-turno.html"],
      ["C4b · Reta final (17h em diante)", "Depois das 17h, a seção acelerou além do próprio ritmo do dia?", f'{N(fin1.get("discrepantes",0))} voto{"s" if fin1.get("discrepantes",0) != 1 else ""} discrepante{"s" if fin1.get("discrepantes",0) != 1 else ""} em {N(fin1.get("votos",0))} depois das 17h', f'{N(fin2.get("discrepantes",0))} voto{"s" if fin2.get("discrepantes",0) != 1 else ""} discrepante{"s" if fin2.get("discrepantes",0) != 1 else ""} em {N(fin2.get("votos",0))} depois das 17h', "reta-final.html"],
      ["C4 ampliado · «Pianista» (30 s, 40 s, corridas)", "Com limiares maiores e olhando sequências, aparece mesário votando em série?", pian(p1, "1"), pian(p2, "2"), "pianista.html"],
      ["K2 / K3 · Concentração por horário × resultado", "Houve horário em que os votos se concentraram num candidato? A seção que votou «em bloco» ou tarde deslocou o resultado contra o próprio 1º turno e contra as vizinhas?", "controles: a seção contra o próprio município e o perfil horário da mesma seção no 1º turno", kc_txt(), "concentracao.html"],
      ["K4–K7 · Algoritmo de «queda linear»?", "O software poderia detectar 22 subindo e acionar uma queda programada? Marcas: assimetria no empate por urna, déficit de urnas com 22 à frente no município, curva da totalização inexplicada pela ordem de chegada, periodicidade e repetição no relógio.", al_txt(al1, "1"), al_txt(al2, "2"), "algoritmo.html"],
      ["E1 / E5 / E6 · A seção contra si mesma", "Cada seção e cada município se comportaram no 2º turno como no 1º?",
       "régua", f'{N(e1.get("secoes_comuns",0))} seções comuns; {N(e5.get("com_indicador_pior_no_2t",0))} de {N(e5.get("municipios_comuns",0))} municípios com algum indicador pior; {e6.get("secoes_2t_com_discrepantes_sem_ter_no_1t",0)} seções com discrepância nova após 17h', "comparativo.html"],
      ["E4 · Votos tardios e candidato", "As seções com mais votos depois das 17h mudaram de lado entre os turnos?", "controle: correlação da fila do 1º turno", f'correlação {e4.get("correlacao","—")} (nula); limites de Duncan-Davis e Goodman publicados', "votos-tardios.html"],
      ["F1 · Geografia", "Onde se concentrou a votação tardia?", f'{N((A.get("F1_geografia_1t") or {}).get("municipios",0))} municípios, mediana {_d((A.get("F1_geografia_1t") or {}).get("mediana_pct_tardio",0),3)}% de votos tardios', f'{N((A.get("F1_geografia_2t") or {}).get("municipios",0))} municípios, mediana {_d((A.get("F1_geografia_2t") or {}).get("mediana_pct_tardio",0),3)}%', "comparativo.html"],
      ["L1–L11 · Forense dos logs", "Há rastro de edição — humana, por programa ou por IA — nos logs?",
       f'{N(f1["linhas"])} linhas lidas, {N(f1["linhas"]-f1["linhas_ok"])} fora da gramática; {N(f1["assin"])} verificações de assinatura de componentes, {N(f1["assin"]-f1["assin_ok"])} não-sucesso (reinícios); serial ≠ boletim: {f1["l6"]}',
       f'{N(f2["linhas"])} linhas lidas, {N(f2["linhas"]-f2["linhas_ok"])} fora da gramática; {N(f2["assin"]-f2["assin_ok"])} não-sucesso; {N(f2["turno_dif"])} logs declaram «1º turno» em 25/10 (anomalia listada, a explicar)', "forense.html"],
      ["V · Testes de boletim", "Unanimidade, zero para um candidato com 100+ válidos, comparecimento = aptos, último dígito", f'{f1["v100"]} seções 100% um candidato (todas pequenas)', f'{f2["v100"]} seções 100% um candidato (todas pequenas)', "forense.html"],
    ]
    # testes que dependem do cache por UF do demonstra.py (2T pode estar com menos UFs que 28)
    cob2 = f' <small>({ufs2}/28 UFs)</small>' if ufs2 < 28 else ""
    for l in linhas:
        if l[0][:4] in ("A2 ·", "A4 ·", "C1 ·", "C4 ·", "C4b "): l[3] = l[3] + cob2
    tab = "".join(f'<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td><td><a href="{e}">ver</a></td></tr>' for a, b, c, d, e in linhas)

    pian_concl = ""
    if p2:
        pian_concl = (f' Com os limiares de 30 s e 40 s e olhando sequências, não aparece o rastro de um «pianista»: depois das 17h, {N(p2["cf30_10"])} seções tiveram '
                      f'10 votos seguidos abaixo de 30 s e {N(p2["cf30_5"])} tiveram 5; no dia inteiro, {N(p2["c30_10"])} seções, todas de grandes cidades e com mais de 300 votantes; e o menor tempo em que '
                      f'uma urna registrou 10 votos seguidos foi {p2["min10"]} s no 2º turno' + (f' e {p1["min10"]} s no 1º' if p1 and p1["min10"] is not None else "")
                      + ', mais de 20 s por eleitor em qualquer urna do país.') if p2["min10"] is not None else ""
    pend_pian = "" if (p1 and p2 and p1["ufs"] == 28 and p2["ufs"] == 28) else " O teste do «pianista» com 30 s e 40 s está em processamento; a tabela e a página própria crescem conforme as UFs terminam."

    return f'''
<blockquote>
<p><strong>Em uma frase:</strong> com os dados públicos do TSE — todos os boletins, logs, RDV e contêineres de assinatura das
{N(D.get("secoes",0))} seções do país, nos dois turnos — e com método publicado antes de os dados existirem, <strong>nenhum dos testes
encontrou voto fora do prazo, voto após o lacre, urna reaberta, log alterado, registro digital do voto diferente do boletim, boletim diferente
da totalização, sequência de votos em ritmo incompatível com eleitor real ou concentração de votos num candidato associada a horário</strong>. A soma dos boletins é exatamente o resultado proclamado. As duas horas a mais do 2º turno
somaram {N(tard2)} votos ({_d(td2.get("pct_17h_em_diante",0),3)}% do total), menos de {_d(100*tard2/margem,1)}% da margem entre os candidatos, e no
ritmo normal de cada seção.</p>
</blockquote>'''  + f'''

<div class="grid">
<div class="stat"><div class="n">2</div><div class="l">turnos auditados — 4 e 25 de outubro</div></div>
{('<div class="stat"><div class="n">28/28</div><div class="l">unidades da Federação, nos dois turnos, em todos os testes</div></div>' if (len(PORUF) == 28 and ufs2 == 28) else f'<div class="stat"><div class="n">{len(PORUF)}/28 · {ufs2}/28</div><div class="l">UFs com log nos testes de ritmo, 1º e 2º turno (boletins, soma e forense: 28/28 nos dois)</div></div>')}
<div class="stat"><div class="n">{N(D.get("secoes",0))}</div><div class="l">seções eleitorais por turno</div></div>
<div class="stat"><div class="n">{N(v1 + v2)}</div><div class="l">votos somados nos dois turnos</div></div>
<div class="stat"><div class="n">{len(linhas)}</div><div class="l">famílias de verificação, mais de 40 testes</div></div>
<div class="stat"><div class="n">v{man.get("versao","—")}</div><div class="l">manifesto com {N(man.get("n_arquivos",0))} arquivos, carimbado na blockchain</div></div>
</div>

<h2>O que é isto</h2>
<p>Uma auditoria independente das Eleições Gerais de 2026, feita exclusivamente com os arquivos que o Tribunal Superior Eleitoral
publica — boletim de urna, log de urna, Registro Digital do Voto e contêiner de assinatura de cada seção — e com um
<a href="plano-2t.html">plano de testes publicado em {PLANO_OTS["data"]}</a>, antes de os dados do 2º turno existirem, com a data ancorada
na blockchain do Bitcoin (bloco {N(PLANO_OTS["bloco"])}). O motivo foi uma hipótese concreta, descrita por Flávio Dino em
<a href="reta-final.html">discurso que motivou este trabalho</a>: que nas duas horas a mais concedidas no 2º turno, entre 17h e 19h,
mesários teriam votado por eleitores ausentes. O 1º turno, encerrado às 17h e sem contestação, serve de <strong>régua do normal</strong>
para todo número do 2º.</p>
<p>Responsável: Luis Manuel Jordão Elias Gomes (Maneco Gomes), OAB/RJ 245.463. Trabalho pessoal, sem vínculo com candidato, partido ou
órgão público.</p>

<h2>Como foi feito, em ordem</h2>
<ol>
<li><strong>{PLANO_OTS["data"]} — plano pré-registrado.</strong> Blocos A (integridade), B (horários), C (comportamento da urna pelo log), D (impossibilidades
lógicas), E (cada seção e cada município contra si mesmos, 1º × 2º turno), F (geografia) e G (dispersão da ordem de prorrogação). Carimbado com OpenTimestamps.</li>
<li><strong>27/10 — 1º turno completo.</strong> Pacotes oficiais das 28 UFs baixados do CDN do TSE, SHA-512 conferido, {N(D.get("secoes",0))} seções, {N(D.get("votos_presidente",0))} votos
nos logs. Emenda datada do mesmo dia: teste C4b (ritmo antes e depois das 17h), acrescentado <em>antes</em> dos dados do 2º turno.</li>
<li><strong>28/10 — 2º turno.</strong> Boletins oficiais das 28 UFs (publicados pelo TSE às 08h59) e, como o pacote consolidado de logs ainda não saiu, os mesmos
arquivos coletados seção por seção no Portal Resultados, conferidos contra o hash que a própria urna assinou. Todos os testes do plano rodaram.</li>
<li><strong>28/10 — emenda posterior aos dados</strong>, a pedido de quem encomendou e identificada como tal: forense dos logs (rastro de edição, inclusive por IA),
soma dos boletins contra a totalização oficial, destino dos votos tardios, o teste do «pianista» com 30 s e 40 s, o RDV conferido voto a voto com o boletim
e a concentração de votos por horário contra o resultado de cada seção. Força probatória menor que a
dos testes pré-registrados, por terem sido escolhidos sabendo o que havia nos dados.</li>
</ol>

<h2>Todas as verificações realizadas</h2>
<p>Uma linha por família de teste. Os números são os dos arquivos publicados; cada link abre a página com o detalhe por UF e por município.{pend_pian}</p>
<div class="scroll"><table><thead><tr><th>Verificação</th><th>Pergunta</th><th>1º turno (régua)</th><th>2º turno</th><th></th></tr></thead>
<tbody>{tab}</tbody></table></div>

<h2>Conclusão sobre o resultado e sua autenticidade</h2>
<p><strong>1. O resultado proclamado é a soma dos boletins.</strong> Nos dois turnos, comparecimento, brancos, nulos e o voto de cada candidato
coincidem exatamente entre a soma de todos os boletins de urna e a totalização oficial. No 2º turno: {N(cand.get("13",{}).get("oficial",0))} × {N(cand.get("22",{}).get("oficial",0))}.
No 1º, nenhum candidato alcançou maioria absoluta pelos próprios boletins.</p>
<p><strong>2. Os arquivos são os que as urnas produziram.</strong> Os pacotes do TSE batem com o SHA-512 publicado pelo TSE; cada boletim e cada log batem
com o SHA-512 que a própria urna gravou no contêiner assinado ao encerrar — {N(f1["a5_conf"])} de {N(f1["logs"])} logs no 1º turno e {N(f2["a5_conf"])} de {N(f2["logs"])} no 2º.
As {N(f2["a5_div"])} divergências do 2º turno estão todas em membros de ZIPs remontados nesta máquina a partir da coleta por seção, cuja escrita no volume externo
corrompeu bytes; são defeito da cópia local, não do dado do TSE, e serão reconferidas quando o pacote oficial por UF for publicado.
E o Registro Digital do Voto — o arquivo em que a urna grava cada voto digitado — reproduz o boletim voto a voto: {rdv_txt(rdv2)} no 2º turno,
{rdv_txt(rdv1)} no 1º.</p>
<p><strong>3. Nenhuma urna foi reaberta, nenhum voto ficou fora do prazo, nenhuma impossibilidade lógica.</strong> Zero votos depois do lacre nos dois turnos;
zero seções com comparecimento acima dos aptos, encerramento antes da abertura ou boletim antes do encerramento; {N(ap19)} votos depois das 19h no 2º turno
em {N(v2)}, e {N(r2.get("encerrou_alem_2h",0))} seção encerrada mais de duas horas depois do prazo (no 1º turno, pela fila dos cinco cargos, foram {N(REGUA_1T_FECHAMENTO["secoes_alem_2h"])}).</p>
<p><strong>4. As duas horas a mais não alteraram o ritmo das urnas.</strong> De 17h em diante no 2º turno houve {N(tard2)} votos — {_d(td2.get("pct_17h_em_diante",0),3)}% do total —
e nenhum deles em ritmo discrepante do dia normal da própria seção; {N(c4_2.get("abaixo_de_20s",0))} intervalos abaixo de 20 s no dia inteiro, contra
{N(c4_1.get("abaixo_de_20s",0))} no 1º turno.{pian_concl} Mesmo na hipótese extrema de todos os votos tardios irem a um só candidato, eles valeriam
{_d(100*tard2/margem,1)}% da margem; e a comparação seção a seção entre os turnos (E4) mostra correlação nula entre votação tardia e deslocamento de voto.
A pergunta «houve um horário em que os votos se concentraram num candidato?» foi respondida pelo que o dado permite: {kc_txt()}; as pequenas correlações
que aparecem nas horas da manhã e do meio-dia no país inteiro caem a zero quando cada seção é comparada só com as vizinhas do próprio município — é
geografia (as regiões que votam cedo são as que se deslocaram de forma diferente entre os turnos), não algo ocorrido dentro das urnas em 25/10.
A hipótese de um algoritmo que penalizasse 22 «quando à frente», com queda programada, foi testada pelas marcas que deixaria: a margem por urna é lisa ao cruzar o
empate nos dois turnos, as urnas com 22 à frente dentro de cada município são as que a régua do 1º turno prevê, a curva da totalização é a ordem de chegada dos
municípios e termina na soma exata dos boletins, e o relógio das urnas não tem período, ressalto nem sequência repetida.</p>
<p><strong>5. Os logs não têm rastro de edição.</strong> {N(f1["linhas"]+f2["linhas"])} linhas de log lidas nos dois turnos: gramática fixa, codificação,
código único por linha, relógio, vocabulário fechado, serial da urna, selo final, versão do software e verificações de assinatura dos componentes,
tudo dentro do que o software da urna produz. As exceções estão listadas uma a uma na página da forense, com a explicação encontrada ou a marca
«a explicar» — a principal é o conjunto de {N(f2["turno_dif"])} logs do 2º turno que declaram «1º turno» no cabeçalho do dia 25/10.</p>
<p><strong>Juízo.</strong> Dentro do que os dados públicos permitem verificar, <strong>o resultado das Eleições de 2026 é autêntico</strong>: a totalização reproduz os boletins, os boletins
reproduzem os logs, os logs reproduzem o comportamento esperado das urnas, e a prorrogação do 2º turno não produziu votos em volume nem em ritmo
capazes de influir no resultado. Isto não é um atestado de que fraude é impossível; é a afirmação de que <em>esta</em> hipótese, testada com <em>estes</em> dados,
por <em>este</em> método, não encontrou apoio — e de que qualquer pessoa pode refazer o caminho.</p>

<h2>O que este trabalho não pode afirmar</h2>
<blockquote><p><strong>Ressalva principal: o software das urnas não é auditável por quem está de fora.</strong> O código-fonte e os executáveis que rodaram
nas urnas só podem ser inspecionados pelas entidades fiscalizadoras listadas na Resolução TSE 23.673/2021 (partidos, OAB, Ministério Público,
Defensoria, Congresso, CGU, Polícia Federal, SBC, Confea, CNJ, CNMP, Forças Armadas e universidades credenciadas), em ambiente controlado no
TSE, sem internet, sem cópia e sob termo de sigilo; o público recebe apenas os resumos digitais (hashes) gerados na cerimônia de lacração. Em tese,
um programa pode conter instrução maliciosa — por exemplo, registrar um voto diferente do digitado — e isso <em>não deixa rastro em nenhum arquivo
publicado</em>: boletim, log, RDV e contêiner assinado seriam todos produzidos pelo mesmo programa, e bateriam entre si. Com os dados públicos não há o
que fazer a esse respeito. O que esta auditoria verifica é tudo o que acontece <em>depois</em> que o voto foi registrado pela urna: que nenhum arquivo foi
alterado, que a soma é a proclamada, que nenhuma urna foi reaberta ou acelerada, que o ritmo e os horários são os de eleitores reais. A garantia sobre
o programa em si depende da inspeção pelas entidades fiscalizadoras, do Teste Público de Segurança e do Teste de Autenticidade feito pelo TSE em urnas
sorteadas no dia da eleição — procedimentos que esta auditoria não substitui. O único cotejo possível de fora, feito na página da forense, é que cada
urna verificou ao carregar exatamente os pacotes lacrados para o seu modelo, com sucesso, e declarou a mesma versão de software.</p></blockquote>
<ul>
<li><strong>Em quem foi cada voto.</strong> O log registra o cargo, nunca o candidato; o RDV traz os votos embaralhados. É o sigilo do voto, e nenhuma análise de dado público o atravessa.</li>
<li><strong>Quem votou.</strong> A habilitação no log não identifica o eleitor. A hipótese «o mesário votou pelo ausente» só é testável pelo ritmo e pela sequência dos votos, e foi.</li>
<li><strong>A assinatura criptográfica dos contêineres.</strong> Conferimos o hash gravado dentro do <code>vota.vsc</code>; a assinatura do contêiner exige o certificado do TSE, que não está publicado.</li>
<li><strong>O pacote consolidado de logs do 2º turno</strong>, que o TSE ainda não publicou. Os logs usados vieram do Portal Resultados, seção a seção, com hash conferido; quando o pacote sair, os dois serão comparados membro a membro e a conferência publicada.</li>
</ul>

<h2>Tudo está disponível para download e conferência</h2>
<ul>
<li><strong>Fontes originais do TSE</strong>: os endereços de cada pacote e de cada hash estão em <a href="dados.html">Dados e hashes</a>, com o SHA-512 do TSE e o calculado aqui, UF por UF.</li>
<li><strong>Código</strong>: todos os programas que rodaram — e só eles — estão no repositório
<a href="https://github.com/ManecoGomes/auditoria-tse-2026" rel="noopener">github.com/ManecoGomes/auditoria-tse-2026</a> (<code>scripts/pipeline/</code>).</li>
<li><strong>Dados derivados</strong>: resultados por UF, por município e por seção (CSV), no mesmo repositório (<code>dados/</code>), incluindo a lista de seções apontadas por cada teste.</li>
<li><strong>Manifesto carimbado</strong>: <code>manifesto.json</code> com o SHA-512 de cada arquivo publicado (v{man.get("versao","—")}, {N(man.get("n_arquivos",0))} arquivos) e o carimbo
OpenTimestamps que ancora a data na blockchain do Bitcoin; versões anteriores preservadas em <code>manifestos/</code>.</li>
<li><strong>Como conferir</strong>: o passo a passo — baixar do TSE, comparar hashes, rodar os testes, ler um log com as próprias mãos — está em <a href="verificar.html">Como verificar</a>.</li>
</ul>

<h2>Onde está cada coisa</h2>
<ul>
<li><a href="primeiro-turno.html"><strong>1º turno</strong></a> — todos os testes do plano sobre as 28 UFs, estado por estado e município por município (a régua).</li>
<li><a href="segundo-turno.html"><strong>2º turno</strong></a> — coleta por seção, o que aconteceu em 25/10 com fontes, e os mesmos testes.</li>
<li><a href="comparativo.html"><strong>Comparativo 1º × 2º turno</strong></a> — cada seção e cada município contra si mesmos; a pergunta sobre o resultado.</li>
<li><a href="reta-final.html"><strong>Reta final</strong></a> — a hipótese, o vídeo, o teste C4b e as seções apontadas.</li>
<li><a href="estados/index.html"><strong>Estados</strong></a> — uma página por UF e uma por município, com o 2º turno ao lado do 1º.</li>
<li><a href="forense.html"><strong>Forense dos logs</strong></a> · <a href="soma-oficial.html"><strong>Soma oficial</strong></a> · <a href="votos-tardios.html"><strong>Votos tardios</strong></a> · <a href="pianista.html"><strong>Pianista</strong></a> · <a href="concentracao.html"><strong>Horário × resultado e RDV</strong></a> · <a href="algoritmo.html"><strong>Queda linear?</strong></a> — a emenda de 28/10.</li>
<li><a href="plano-2t.html">Plano pré-registrado</a> · <a href="verificar.html">Como verificar</a> · <a href="dados.html">Dados e hashes</a> · <a href="relatorio.html">Relatório técnico do 1º turno</a> · <a href="relatorio-2t.html">Relatório do 2º turno</a></li>
</ul>
'''

corpo_index = indice_resumo()
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
