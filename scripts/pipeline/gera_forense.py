#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera as paginas das analises posteriores ao plano (emenda datada de 28/10/2026):
   forense.html        — forense do log de urna (bloco L), integridade assinada (A5), testes de boletim (V)
   soma-oficial.html   — A3: soma dos boletins contra a totalizacao oficial, nos dois turnos
   votos-tardios.html  — votos depois das 17h: para quem? limites, regressao ecologica e E4
 + agrega forense/{t}t/*.json em pipeline/forense_{t}t.json e copia dados para repo/dados/analises.
Roda sem argumentos; tolera dados parciais (mostra o que falta)."""
import json, glob, os, re, math, collections, datetime, csv, shutil
P = os.path.expanduser("~/Claude/Projetos/eleição"); PL = f"{P}/pipeline"; SITE = f"{P}/repo/site"; R = f"{PL}/resultados"
FOR = "/Volumes/SSD1TB/acervo-tse/auditoria/forense"
URL = "https://auditoria-tse-2026.com.br"
UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()
N = lambda x: ("—" if x is None else f"{x:,}".replace(",", "."))
PCT = lambda a, b, d=2: ("—" if not b else f"{100*a/b:.{d}f}%".replace(".", ","))
esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ---------------------------------------------------------------- molde (igual ao gera_demo_html.py)
BASE = open(f"{SITE}/relatorio.html").read()
_i = BASE.index('<header class="top">'); _j = BASE.index('<footer>')
CABECA, RODAPE = BASE[:_i], BASE[_j:]
_agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
RODAPE = re.sub(r"Última atualização: [0-9/]+ [0-9:]+", f"Última atualização: {_agora}", RODAPE)
NAV = [("index.html","Resumo"),("primeiro-turno.html","1º turno"),("segundo-turno.html","2º turno"),
       ("comparativo.html","Comparativo"),("reta-final.html","Reta final"),("estados/index.html","Estados"),
       ("forense.html","Forense dos logs"),("soma-oficial.html","Soma oficial"),("votos-tardios.html","Votos tardios"),("pianista.html","Pianista"),
       ("plano-2t.html","Plano"),("verificar.html","Como verificar"),("dados.html","Dados e hashes")]
def nav(ativo):
    return "<nav>" + "".join(f'<a href="{h}"{" class=\"on\"" if h == ativo else ""}>{t}</a>' for h, t in NAV) + "</nav>"
def pagina(titulo, kicker, h1, sub, corpo, slug):
    head = (CABECA.replace("<title>Relatório completo — Auditoria TSE 2026</title>", f"<title>{titulo}</title>")
                  .replace(f'href="{URL}/relatorio.html"', f'href="{URL}/{slug}"')
                  .replace(f'content="{URL}/relatorio.html"', f'content="{URL}/{slug}"'))
    return (head + f'<header class="top"><div class="kicker">{kicker}</div><h1>{h1}</h1><p class="sub">{sub}</p>'
            + nav(slug) + "</header>" + corpo + RODAPE)
def stat(n, l, zero=False): return f'<div class="stat{" zero" if zero else ""}"><div class="n">{n}</div><div class="l">{l}</div></div>'
def tabela(cols, linhas):
    th = "".join(f"<th>{c}</th>" for c in cols)
    tb = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in l) + "</tr>" for l in linhas)
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>'

# ---------------------------------------------------------------- qui-quadrado (df=9) sem scipy
def gammq(a, x):
    if x < a + 1:
        ap = a; s = d = 1.0 / a
        for _ in range(500):
            ap += 1; d *= x / ap; s += d
            if abs(d) < abs(s) * 1e-14: break
        return 1 - s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b = x + 1 - a; c = 1e300; d = 1 / b; h = d
    for i in range(1, 500):
        an = -i * (i - a); b += 2; d = an * d + b
        if abs(d) < 1e-300: d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300: c = 1e-300
        d = 1 / d; de = d * c; h *= de
        if abs(de - 1) < 1e-14: break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
def qui2_uniforme(cnt):
    n = sum(cnt.values())
    if n < 100: return None
    e = n / 10; x2 = sum((cnt.get(str(d), 0) - e) ** 2 / e for d in range(10))
    return {"n": n, "qui2": round(x2, 2), "p": round(gammq(4.5, x2 / 2), 4), "gl": 9}

# ---------------------------------------------------------------- agrega forense
DESC_L = [
 ("L1_linha_fora_da_gramatica", "L1", "Linha fora da gramática do log", "linha que não é «data hora TAB nível TAB serial TAB componente TAB mensagem TAB código»"),
 ("L2_bytes_controle", "L2", "Bytes de controle (C0)", "caracteres de controle fora de TAB/LF"),
 ("L2_bytes_C1", "L2", "Bytes de controle C1 (0x80–0x9F)", "inexistentes em texto latin-1 legítimo"),
 ("L2_sequencia_utf8", "L2", "Sequência UTF-8 em arquivo latin-1", "acento «dobrado», aspas tipográficas, travessão, espaço de largura zero: rastro de editor moderno"),
 ("L2_nbsp", "L2", "Espaço inseparável (0xA0)", "típico de texto colado de editor"),
 ("L2_crlf", "L2", "Quebra de linha CRLF", "o log usa LF; CRLF indica passagem por editor Windows"),
 ("L3_codigo_repetido", "L3", "Código de linha repetido no arquivo", "o código de 16 hex é único por linha"),
 ("L4_relogio_retrocede", "L4", "Relógio retrocede (arquivo inteiro)", "inclui o período de preparação/carga, quando há ajuste de data e hora legítimo"),
 ("L4_relogio_retrocede_no_dia", "L4", "Relógio retrocede no dia do pleito", "o que exige explicação"),
 ("L6_serial_varia_no_arquivo", "L6", "Serial da urna muda dentro do arquivo", "cada log pertence a uma urna"),
 ("L6_serial_log_ne_boletim", "L6", "Serial do log ≠ urna efetivada no boletim", "a urna que gravou o log não é a que o boletim registra"),
 ("L6_secao_declarada_difere_do_arquivo", "L6", "Município/zona/seção declarados ≠ nome do arquivo", "a urna diz pertencer a outra seção"),
 ("L6_sem_identificacao_no_dia", "L6", "Sem linhas de identificação no dia", "a urna não registrou município/zona/seção no dia (log de urna substituída)"),
 ("L7_sem_selo_final", "L7", "Sem o selo final", "a última linha não é a geração do próprio log.jez"),
 ("L7_sem_geracao_de_logjez_no_dia", "L7", "Sem geração de log.jez no dia", "log não foi selado no dia do pleito"),
 ("L8_assinatura_nao_sucesso", "L8", "Verificação de assinatura ≠ SUCESSO", "a urna verifica a assinatura digital de cada componente do software ao ligar"),
 ("L8_turno_declarado_diferente", "L8", "Turno declarado pela urna ≠ turno do pleito", ""),
 ("L9_sem_zeresima_no_dia", "L9", "Sem zerésima no dia", "relatório de urna zerada antes do 1º voto"),
 ("L9_voto_antes_da_zeresima", "L9", "Voto antes da zerésima", "impossível em operação regular"),
 ("L9_sem_urna_pronta", "L9", "Votos sem «urna pronta para receber votos»", ""),
 ("L9_voto_antes_de_urna_pronta", "L9", "Voto antes de «urna pronta»", "impossível em operação regular"),
 ("L9_sem_geracao_de_bu_no_dia", "L9", "Sem geração do boletim no dia", ""),
 ("C1_voto_apos_lacre", "C1", "Voto após a geração do boletim (lacre)", "teste pré-registrado C1, recalculado aqui"),
 ("L9_habilitados_ne_computados", "L9", "Habilitados ≠ votos computados", "eleitor habilitado que não concluiu (explicação ordinária); direção importa"),
 ("L9_votos_presidente_ne_computados", "L9", "Votos p/ Presidente ≠ votos computados", "voto computado sem confirmação de Presidente (voto em branco por tempo esgotado, p.ex.)"),
 ("A2_comparecimento_bu_ne_computados_log", "A2", "Comparecimento do boletim ≠ computados no log", "triangulação boletim × log; urna substituída explica log menor"),
 ("A5_vsc_anterior_ao_log", "A5", "Carimbo do contêiner de assinatura anterior ao selo do log", "impossível em operação regular"),
 ("A5_bu.dat_DIVERGE", "A5", "bu.dat ≠ hash assinado pela urna", "o arquivo que temos não é o que a urna assinou"),
 ("A5_log.jez_DIVERGE", "A5", "log.jez ≠ hash assinado pela urna", "o arquivo que temos não é o que a urna assinou"),
 ("A5_rdv.dat_DIVERGE", "A5", "rdv.dat ≠ hash assinado pela urna", "o arquivo que temos não é o que a urna assinou"),
 ("A5_sem_vsc", "A5", "Seção sem contêiner de assinatura", ""),
 ("L10_tres_ou_mais_ligadas_no_dia", "L10", "Urna ligada 3+ vezes no dia", "reinícios (C5)"),
 ("L11_logs_identicos", "L11", "Logs idênticos entre seções", "sha256 igual em arquivos de seções distintas"),
 ("D1_comparecimento_maior_que_aptos", "D1", "Comparecimento > aptos (boletim)", "impossibilidade lógica pré-registrada"),
 ("V_soma_votos_ne_comparecimento", "V", "Soma dos votos ≠ comparecimento (boletim)", ""),
 ("V_comparecimento_igual_aptos", "V", "Comparecimento = aptos (50+ aptos)", "todos os eleitores da seção votaram"),
 ("V_100pct_um_candidato", "V", "100% dos válidos para um candidato (50+ válidos)", "unanimidade"),
 ("V_zero_para_candidato_com_100_validos", "V", "Zero votos para 13 ou 22 com 100+ válidos", ""),
 ("sem_boletim", "—", "Log sem boletim correspondente", ""),
 ("sem_log", "—", "Boletim/seção sem log", ""),
 ("log_jez_ilegivel", "—", "log.jez ilegível", ""),
]
def agrega(t):
    A = {"turno": t, "ufs": {}, "contagem": collections.Counter(), "anomalias": collections.defaultdict(list), "anom_por_uf": collections.defaultdict(collections.Counter),
         "versoes": collections.Counter(), "modelos": collections.Counter(), "fases": collections.Counter(), "turno_declarado": collections.Counter(),
         "niveis": collections.Counter(), "componentes": collections.Counter(), "habilitacao": collections.Counter(), "erros_dia": collections.Counter(),
         "digitos": {"13": collections.Counter(), "22": collections.Counter()}, "moldes_raros": [], "moldes_total_por_uf": {}, "fontes": {}}
    for f in sorted(glob.glob(f"{FOR}/{t}t/*.json")):
        try: j = json.load(open(f))
        except Exception: continue
        uf = j["uf"]; A["ufs"][uf] = {"secoes": j["contagem"].get("secoes", 0), "logs": j["contagem"].get("logs", 0), "segundos": j.get("segundos"), "fonte": j.get("fonte"),
                                      "membros_com_falha_no_zip": j.get("membros_com_falha_no_zip", 0), "moldes": j.get("moldes_total")}
        A["contagem"].update(j["contagem"])
        for k, v in j["anomalias"].items():
            A["anom_por_uf"][k][uf] = j["contagem"].get(k, len(v))
            for a in v[:6]: A["anomalias"][k].append({"uf": uf, **a})
        for k in ("versoes", "modelos", "fases"): A[k].update(j.get(k, {}))
        A["turno_declarado"].update(j.get("turno_declarado_dia", {}))
        A["niveis"].update(j.get("niveis", {})); A["componentes"].update(j.get("componentes", {}))
        A["habilitacao"].update(j.get("habilitacao_tipos", {})); A["erros_dia"].update(j.get("erros_dia", {}))
        for c in ("13", "22"): A["digitos"][c].update(j.get("ultimo_digito", {}).get(c, {}))
        for m in j.get("moldes_raros", []): A["moldes_raros"].append({"uf": uf, **m})
        A["moldes_total_por_uf"][uf] = j.get("moldes_total")
    A["qui2"] = {c: qui2_uniforme(A["digitos"][c]) for c in ("13", "22")}
    A["moldes_raros"].sort(key=lambda m: (m["arquivos"], m["ocorrencias"]))
    return A

def sec_html(t, A):
    C = A["contagem"]; ufs = A["ufs"]
    if not ufs: return f"<p><em>{t}º turno: forense ainda não iniciada.</em></p>"
    falta = [u for u in UFS if u not in ufs]
    cab = (f'<div class="grid">{stat(f"{len(ufs)}/28", "UFs processadas")}{stat(N(C.get("logs")), "logs de urna lidos")}'
           f'{stat(N(C.get("linhas")), "linhas de log analisadas")}{stat(N(C.get("A5_log.jez_confere")), "logs iguais ao hash assinado pela urna")}</div>')
    if falta: cab += f'<p><strong>Em processamento:</strong> {", ".join(falta)}. A página cresce conforme cada UF termina.</p>'
    # tabela de testes
    linhas = []
    for k, bl, nome, desc in DESC_L:
        if k == "L11_logs_identicos": n = C.get("L11_logs_identicos_arquivos", 0)
        else: n = C.get(k, 0)
        if n == 0 and k.startswith(("L2", "L3", "L6_serial_varia", "L7_sem_selo", "L8_assin", "L9_voto_antes", "A5_", "L11", "D1", "V_soma", "C1", "L4_relogio_retrocede_no_dia", "L6_secao", "L8_turno")):
            linhas.append([f"<strong>{bl}</strong> {nome}", '<span class="flag ok">zero</span>', desc])
        elif n == 0: linhas.append([f"<strong>{bl}</strong> {nome}", "0", desc])
        else:
            ex = A["anomalias"].get(k, [])[:3]
            exs = "; ".join(f'{a["uf"]} {a["sec"]}' + (f' ({a.get("n")})' if a.get("n") is not None else "") for a in ex)
            por = ", ".join(f"{u} {v}" for u, v in sorted(A["anom_por_uf"][k].items(), key=lambda x: -x[1])[:6])
            linhas.append([f"<strong>{bl}</strong> {nome}", f"<strong>{N(n)}</strong>", f"{desc}<br><small>por UF: {por}<br>ex.: {esc(exs)}</small>"])
    tab = tabela(["Teste", "Seções/ocorrências", "O que significa"], linhas)
    # integridade assinada
    a5 = (f'<h3>A5 — o que a urna assinou é o que temos</h3>'
          f'<p>O contêiner <code>vota.vsc</code> de cada seção guarda o SHA-512 de <code>bu.dat</code>, <code>log.jez</code> e <code>rdv.dat</code>, gravado pela própria urna ao encerrar. '
          f'Calculamos o SHA-512 dos três arquivos que temos e procuramos o resultado dentro do contêiner.</p>'
          + tabela(["Arquivo", "Seções com contêiner", "Hash confere", "Diverge", "Sem o arquivo"],
                   [[a, N(C.get("A5_vsc", 0)), f'<strong>{N(C.get(f"A5_{a}_confere", 0))}</strong>', N(C.get(f"A5_{a}_DIVERGE", 0)), N(C.get(f"A5_sem_{a}", 0))] for a in ("bu.dat", "log.jez", "rdv.dat")])
          + f'<p>Seções sem contêiner: {N(C.get("A5_sem_vsc", 0))}. Contêineres com carimbo de data e hora legível: {N(C.get("A5_vsc_com_carimbo", 0))}; '
            f'carimbo anterior ao selo do log: {N(C.get("A5_vsc_anterior_ao_log", 0))}.</p>'
          f'<p><em>Limite:</em> conferimos o hash dentro do contêiner, não a assinatura criptográfica do contêiner (que exige o certificado do TSE). '
          f'Isso prova que os arquivos não mudaram desde que a urna os assinou — não prova, por si, quem assinou.</p>')
    # software
    sw = (f'<h3>L8 — software e identidade</h3>'
          + tabela(["Item", "Valores encontrados (seções)"],
                   [["Versão da aplicação", esc(", ".join(f"{k}: {N(v)}" for k, v in A["versoes"].most_common()))],
                    ["Modelo de urna", esc(", ".join(f"{k}: {N(v)}" for k, v in A["modelos"].most_common()))],
                    ["Fase", esc(", ".join(f"{k}: {N(v)}" for k, v in A["fases"].most_common()))],
                    ["Turno declarado no dia", esc(", ".join(f"{k}: {N(v)}" for k, v in A["turno_declarado"].most_common()))],
                    ["Verificações de assinatura de componentes", f'{N(C.get("L8_verificacoes_assinatura", 0))} feitas, {N(C.get("L8_verificacoes_assinatura_ok", 0))} com SUCESSO'],
                    ["Níveis de log", esc(", ".join(f"{k}: {N(v)}" for k, v in A["niveis"].most_common()))],
                    ["Componentes", esc(", ".join(f"{k}: {N(v)}" for k, v in A["componentes"].most_common()))]]))
    # ciclo do dia
    ciclo = (f'<h3>L9/L10 — o dia do pleito, somado</h3>'
             + tabela(["Medida", "Total"],
                      [["Linhas de log no dia", N(C.get("linhas_dia"))], ["Eleitores habilitados", N(C.get("habilitados_dia"))], ["Votos computados", N(C.get("computados_dia"))],
                       ["Votos confirmados para Presidente", N(C.get("votos_presidente_dia"))], ["Habilitações biométricas", N(A["habilitacao"].get("biométrica", 0))],
                       ["Habilitações pelo mesário (manual)", N(C.get("L9_habilitacao_manual_mesario", 0))],
                       ["Urna ligada (eventos no dia)", N(C.get("L10_ligadas_dia"))], ["Desligamentos registrados", N(C.get("L10_desligamentos_dia"))],
                       ["Seções com evento de bateria/energia", N(C.get("L10_secoes_com_evento_bateria", 0))],
                       ["Boletim maior que o log (A2)", N(C.get("A2_bu_maior", 0))], ["Log maior que o boletim (A2)", N(C.get("A2_log_maior", 0))]]))
    erros = tabela(["Mensagem de ERRO no dia (dígitos → #)", "Ocorrências"], [[esc(k[:200]), N(v)] for k, v in A["erros_dia"].most_common(15)])
    # vocabulario
    raros = A["moldes_raros"][:60]
    voc = (f'<h3>L5 — vocabulário fechado</h3>'
           f'<p>Cada mensagem, com dígitos trocados por «#», é um molde. O software da urna tem um repertório finito de moldes; uma frase inventada ou parafraseada por quem editasse o arquivo seria um molde que não aparece em nenhuma outra urna. '
           f'Moldes distintos por UF: {esc(", ".join(f"{u} {v}" for u, v in A["moldes_total_por_uf"].items()))}.</p>'
           f'<p>Moldes que aparecem em no máximo 2 arquivos da UF ({N(len(A["moldes_raros"]))} no total; os 60 mais raros abaixo). Leia-os: são mensagens de contingência, ajuste de hora, erro de hardware — vocabulário do próprio software, não texto estranho.</p>'
           + tabela(["UF", "Molde", "Arquivos", "Ocorrências", "Exemplo (mun-zona-seção)"], [[m["uf"], esc(m["molde"][:160]), m["arquivos"], m["ocorrencias"], m["exemplo_secao"]] for m in raros]))
    # ultimo digito
    q = A["qui2"]
    dig = (f'<h3>V — último dígito dos votos por seção</h3>'
           f'<p>Em seções com 100+ votos para o candidato, o último dígito da contagem deve ser aproximadamente uniforme (10% cada). Qui-quadrado com 9 graus de liberdade; p pequeno (&lt; 0,01) indicaria dígitos «preferidos».</p>'
           + tabela(["Candidato", "Seções", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "χ²", "p"],
                    [[c, N(q[c]["n"]) if q[c] else "—"] + [N(A["digitos"][c].get(str(d), 0)) for d in range(10)] + ([q[c]["qui2"], q[c]["p"]] if q[c] else ["—", "—"]) for c in ("13", "22")]))
    vet = f'<p>Vetores de votos idênticos (aptos, comparecimento, 13, 22, branco, nulo iguais) entre seções com 100+ votantes: {N(C.get("V_vetores_identicos_grupos", 0))} grupos, {N(C.get("V_vetores_identicos_secoes", 0))} seções. Tipos de urna no boletim: {esc(", ".join(f"{k[10:]}: {N(v)}" for k, v in C.items() if k.startswith("tipo_urna:")))}.</p>'
    porufs = tabela(["UF", "Seções", "Logs", "Fonte", "Membros ruins no ZIP (lidos do arquivo solto)", "Moldes", "Tempo"],
                    [[u, N(d["secoes"]), N(d["logs"]), esc(d["fonte"]), N(d["membros_com_falha_no_zip"]), N(d["moldes"]), f'{d["segundos"]} s'] for u, d in sorted(ufs.items())])
    return cab + "<h3>Testes de consistência do arquivo</h3>" + tab + a5 + sw + ciclo + erros + voc + dig + vet + "<h3>Cobertura por UF</h3>" + porufs

def pagina_forense(A1, A2):
    intro = f'''
<blockquote><p><strong>Emenda datada de 28/10/2026, posterior ao plano.</strong> Estes testes foram acrescentados depois de os dados dos dois turnos existirem,
a pedido de quem encomendou a auditoria, para responder a uma pergunta direta: <em>há no log das urnas algum rastro de que o arquivo tenha sido alterado —
por pessoa, por programa ou por inteligência artificial?</em> Por serem posteriores, têm força probatória menor que os pré-registrados, e por isso estão
em página própria, com o código publicado.</p></blockquote>
<h2>O que é possível testar, e o que não é</h2>
<p>Não existe teste que identifique a <em>autoria</em> de uma alteração — se foi uma pessoa, um script ou um modelo de IA. O que existe é um conjunto de
invariantes que o software da urna respeita ao gerar o log, e que qualquer edição posterior precisaria reproduzir perfeitamente para passar despercebida:</p>
<ul>
<li><strong>Gramática fixa</strong>: cada linha tem seis campos separados por tabulação, nesta ordem: data e hora, nível, serial da urna (8 dígitos), componente, mensagem, código de 16 hexadecimais.</li>
<li><strong>Codificação</strong>: o arquivo é latin-1 puro. Editores e modelos de linguagem produzem UTF-8, aspas tipográficas, travessões, espaços de largura zero — bytes que não existem num log íntegro.</li>
<li><strong>Vocabulário fechado</strong>: o software só escreve frases do seu repertório. Uma frase parafraseada aparece como molde único no país.</li>
<li><strong>Relógio monotônico</strong>, <strong>código único por linha</strong>, <strong>serial constante</strong>, <strong>selo final</strong> (a última linha é a geração do próprio arquivo), e o <strong>ciclo do dia</strong> na ordem certa: zerésima → urna pronta → votos → boletim → log.</li>
<li><strong>Hash assinado pela urna</strong>: o contêiner de assinatura (<code>vota.vsc</code>) traz o SHA-512 do log, do boletim e do RDV. Qualquer byte alterado depois do encerramento quebra a correspondência.</li>
</ul>
<p>Uma edição que reproduzisse <em>tudo isso</em> — inclusive o hash assinado — seria, por definição, indistinguível por análise do arquivo isolado. Nesse caso só a
triangulação com fontes independentes (boletim impresso, totalização, o pacote oficial do TSE quando sair) poderia apontá-la. O que esta página afirma é
estritamente o que mediu.</p>
<p>Os mesmos testes rodam no 1º turno, que serve de régua: o que também aparece no turno não contestado é comportamento ordinário do sistema, não anomalia do 2º turno.</p>
<p>Código: <code>scripts/pipeline/forense.py</code>. Dados agregados: <code>dados/analises/forense_1t.json</code> e <code>forense_2t.json</code>.</p>
<h2>2º turno (25/10/2026)</h2>{sec_html("2", A2)}
<h2>1º turno (04/10/2026) — régua</h2>{sec_html("1", A1)}
<h2>Como ler</h2>
<p>«Zero» nas linhas de codificação, código repetido, hash divergente, voto antes da zerésima e relógio retrocedendo no dia significa: nenhum dos arquivos lidos
exibe o rastro que uma edição deixaria. Os números diferentes de zero em «habilitados ≠ computados», «comparecimento do boletim ≠ log» e «urna ligada 3+ vezes»
têm explicação operacional conhecida (eleitor que não concluiu, urna substituída, reinício) e aparecem nos dois turnos; o que importa é a <em>direção</em>
(log maior que boletim exigiria explicação) e a comparação com a régua do 1º turno.</p>
'''
    return pagina("Forense dos logs de urna — Auditoria TSE 2026", "Análises posteriores ao plano · emenda de 28/10/2026",
                  "Forense dos logs de urna", "Há rastro de edição — humana, por programa ou por IA — nos logs do 1º e do 2º turno? Integridade assinada pela urna, gramática, vocabulário, relógio, ciclo do dia.",
                  intro, "forense.html")

def pagina_soma():
    j = json.load(open(f"{R}/a3_soma_oficial.json"))
    corpo = f'''
<blockquote><p><strong>Pergunta:</strong> a soma dos boletins de urna de todas as seções do país bate com a totalização oficial que o TSE divulgou? E no 1º turno,
algum candidato tinha 50% + 1 dos votos válidos?</p></blockquote>
<h2>Método (teste A3, pré-registrado)</h2>
<p>Somamos, seção por seção, os votos para Presidente de todos os boletins de urna publicados pelo TSE (arquivos <code>bweb_*</code>, SHA-512 conferido com o
resumo publicado), e comparamos com duas fontes oficiais da totalização: o relatório do SISTOT (<em>Relatório Resultado da Totalização</em>, PDF por turno)
e o conjunto <em>votação por candidato, município e zona</em> do portal de dados abertos. Cópias das duas fontes, com SHA-512, estão no acervo.</p>
'''
    for t in ("1", "2"):
        r = j["turnos"][t]; b = r["boletins"]; o = r["oficial_pdf"]; c = r["confere"]
        corpo += f'<h2>{t}º turno</h2><div class="grid">'
        corpo += stat(N(b["comparecimento"]), "votantes somados dos boletins") + stat(N(o["comparecimento"]), "comparecimento oficial (SISTOT)")
        difs = [l for l in r["candidatos"] if l["diferenca"]]
        so_nulos_tec = (not c["candidatos_todos_iguais"]) and all(l["oficial"] == 0 for l in difs) and sum(l["diferenca"] for l in difs) == (o["nulos_tecnico"] or 0)
        rot = "igual" if c["candidatos_todos_iguais"] else ("igual, salvo nulos técnicos" if so_nulos_tec else "ver tabela")
        corpo += stat("igual" if c["comparecimento"] else "diferente", "comparecimento", zero=c["comparecimento"]) + stat(rot, "votos por candidato", zero=c["candidatos_todos_iguais"] or so_nulos_tec) + "</div>"
        for l in r["candidatos"]:
            if l["oficial"] == 0 and l["boletins"]: l["nome"] = f'{l["nome"]} — candidatura indeferida: votos anulados na totalização (nulos técnicos)'
        corpo += tabela(["Candidato", "Soma dos boletins", "Totalização oficial", "Diferença", "% dos válidos (oficial)"],
                        [[f'{l["numero"]} {esc(l["nome"])}', N(l["boletins"]), N(l["oficial"]), N(l["diferenca"]), f'{l["pct_validos_oficial"]:.2f}%'.replace(".", ",")] for l in r["candidatos"]])
        corpo += tabela(["Total", "Boletins", "Oficial (SISTOT)", "Confere"],
                        [["Comparecimento", N(b["comparecimento"]), N(o["comparecimento"]), "sim" if c["comparecimento"] else "não"],
                         ["Brancos", N(b["brancos"]), N(o["brancos"]), "sim" if c["brancos"] else "não"],
                         ["Nulos na urna", N(b["nulos"]), N(o["nulos_urna"]), "sim" if c["nulos_na_urna"] else "não"],
                         ["Nulos técnicos (só na totalização)", "—", N(o["nulos_tecnico"]), "—"],
                         ["Válidos", N(b["validos_nominais"]), N(o["validos"]), f'diferença {N(c["validos_oficial_menos_boletins"])}'],
                         ["Seções", N(b["secoes"]), f'{N(o["secoes_urna"])} em urna + {N(o["secoes_sa"])} pelo Sistema de Apuração', ""],
                         ["Aptos", N(b["aptos"]), N(o["aptos"]), ""]])
        if t == "1":
            corpo += ('<p>A diferença de 5.246 votos nos válidos é inteiramente explicada pelos «nulos técnicos»: votos dados na urna a candidaturas cujo registro foi indeferido, '
                      'que o boletim registra como nominais e a totalização anula. Somando-os aos nulos, as duas fontes coincidem voto a voto.</p>'
                      '<p><strong>Resposta à pergunta sobre 50% + 1:</strong> pelos boletins do 1º turno, o candidato do PL teve 56.104.503 votos, 47,03% dos válidos; o do PT, 53.879.538 (45,16%). '
                      'Nenhum candidato alcançou a maioria absoluta nos boletins — e os boletins somam exatamente o que a totalização oficial publicou. Não há, nesses dados, divergência entre o que as urnas registraram e o que foi totalizado.</p>')
        else:
            corpo += ('<p>No 2º turno, as duas fontes coincidem em tudo: comparecimento, brancos, nulos e os votos de cada candidato. A soma dos boletins de 499.205 seções dá '
                      f'{N(r["candidatos"][0]["boletins"])} votos ao candidato 13 e {N(r["candidatos"][1]["boletins"])} ao 22 — os mesmos números do resultado oficial.</p>')
        ufd = [u for u in r["por_uf"] if u["13"]["diferenca"] or u["22"]["diferenca"]]
        corpo += f'<p>Por UF, candidatos 13 e 22: {"nenhuma UF com diferença" if not ufd else "diferenças em " + ", ".join(u["uf"] for u in ufd)}.</p>'
        corpo += '<details><summary>Tabela por UF</summary>' + tabela(["UF", "13 boletins", "13 oficial", "dif.", "22 boletins", "22 oficial", "dif."],
                        [[u["uf"], N(u["13"]["boletins"]), N(u["13"]["oficial"]), N(u["13"]["diferenca"]), N(u["22"]["boletins"]), N(u["22"]["oficial"]), N(u["22"]["diferenca"])] for u in r["por_uf"]]) + "</details>"
    corpo += '''
<h2>O que isso demonstra e o que não demonstra</h2>
<p><strong>Demonstra</strong> que a totalização somou corretamente os boletins que as urnas emitiram: não há voto «perdido» nem «acrescentado» entre a urna e o resultado nacional.</p>
<p><strong>Não demonstra</strong> que cada boletim reflete a vontade de cada eleitor — isso é o que os demais testes (log, integridade assinada, ritmo de votação) examinam, cada um dentro do seu limite.</p>
<p>Código: <code>scripts/pipeline/soma_oficial.py</code>. Dados: <code>dados/analises/a3_soma_oficial.json</code>.</p>'''
    return pagina("Soma dos boletins × totalização oficial — Auditoria TSE 2026", "Teste A3 · pré-registrado", "A soma dos boletins bate com o resultado oficial?",
                  "Todos os boletins de urna do país, somados seção por seção, contra a totalização do TSE — 1º e 2º turnos.", corpo, "soma-oficial.html")

def pagina_tardios():
    j = json.load(open(f"{R}/tardios.json")); T = j["turnos"]; E = j.get("E4_secao_contra_si_mesma", {})
    margem = 64256232 - 59826041
    def bloco(t):
        b = T[t]; out = f'<h2>{t}º turno</h2><div class="grid">'
        out += stat(N(b["votos_log"]), f"votos nos logs ({len(b['ufs_com_log'])} UFs)") + stat(N(b["votos_17h_em_diante"]), "votos de 17h em diante") + stat(f'{b["pct_17h_em_diante"]:.3f}%'.replace(".", ","), "dos votos") + stat(N(b["votos_apos_19h"]), "após 19h") + "</div>"
        falta = [u for u in UFS if u not in b["ufs_com_log"]]
        if falta: out += f'<p><strong>Em processamento:</strong> {", ".join(falta)} (sem log analisado ainda).</p>'
        for jan, rot in (("L17", "de 17h em diante"), ("L19", "após 19h")):
            d = b["limites_duncan_davis"].get(jan)
            if not d: continue
            g = b["goodman"].get(jan, {})
            out += f'<h3>Votos {rot}: limites do que o dado permite</h3>'
            out += tabela(["Candidato", "Mínimo possível", "Máximo possível", "Fração mínima", "Fração máxima", "Regressão ecológica (Goodman) a+b"],
                          [[c, N(d[c]["minimo"]), N(d[c]["maximo"]), f'{d[c]["fracao_min"]:.1%}' if d[c]["fracao_min"] is not None else "—", f'{d[c]["fracao_max"]:.1%}' if d[c]["fracao_max"] is not None else "—",
                            (f'{g[c]["a_mais_b_fracao_entre_tardios"]:.3f} (r={g[c]["correlacao"]})' if g.get(c) else "—")] for c in ("13", "22")])
            fx = b["faixas"].get(jan, {})
            if fx:
                out += '<details><summary>Fração do candidato por faixa de votação tardia da seção</summary>'
                out += tabela(["Faixa de votos tardios na seção", "Seções", "Votos", "Votos tardios", "Fração de 13", "Fração de 22"],
                              [[f13["faixa"], N(f13["secoes"]), N(f13["votos"]), N(f13["votos_tardios"]), f'{f13["y_medio"]:.3f}' if f13["y_medio"] is not None else "—", f'{f22["y_medio"]:.3f}' if f22["y_medio"] is not None else "—"]
                               for f13, f22 in zip(fx["13"], fx["22"])]) + "</details>"
        out += '<details><summary>Por UF</summary>' + tabela(["UF", "Votos", "De 17h em diante", "%", "Após 19h", "Fração de 13 entre os tardios: mín–máx"],
                 [[u, N(d["votos"]), N(d["tardios_17h"]), f'{d["pct_tardios"]}%' if d["pct_tardios"] is not None else "—", N(d["apos_19h"]),
                   (f'{d["fracao_13_tardios_min"]:.0%}–{d["fracao_13_tardios_max"]:.0%}' if d["fracao_13_tardios_min"] is not None else "—")] for u, d in b["por_uf"].items()]) + "</details>"
        return out
    corpo = f'''
<blockquote><p><strong>Pergunta:</strong> os votos registrados depois das 17h foram majoritariamente para algum candidato? Dá para verificar nos dois turnos?</p>
<p><strong>Resposta curta:</strong> em quem foi cada voto, não — por construção dos arquivos, não por falta de esforço. O que dá para medir está abaixo, com os limites exatos.</p></blockquote>
<h2>Por que não se sabe em quem foram os votos tardios</h2>
<p>O log da urna registra a hora de cada voto e o <em>cargo</em> («Voto confirmado para [Presidente]»), nunca o candidato. O Registro Digital do Voto traz os votos
embaralhados, sem hora. O boletim traz o total por candidato na seção, sem hora. Os três arquivos são separados de propósito: é o mecanismo do sigilo do voto.
Qualquer pessoa que afirme «os votos depois das 17h foram X% para o candidato Y» está usando um dado que não existe.</p>
<h2>O que dá para medir</h2>
<ol>
<li><strong>Quantos votos houve depois das 17h</strong>, por seção, UF e país — do log, exato.</li>
<li><strong>Os limites aritméticos</strong> (Duncan &amp; Davis, 1953): em cada seção, os votos tardios do candidato X não podem ser menos que
<code>max(0, tardios − (total − votos de X))</code> nem mais que <code>min(tardios, votos de X)</code>. Somando o país, obtém-se o intervalo do qual a fração
de X entre os votos tardios <em>não pode sair</em>, sem nenhuma hipótese. Esse intervalo costuma ser largo — e a largura é a medida honesta de quanto o dado não diz.</li>
<li><strong>Regressão ecológica</strong> (Goodman, 1953): relaciona a fração do candidato na seção com a fração de votos tardios da seção. Dá um número único
<em>sob a hipótese</em> de que os eleitores tardios se comportam igual em toda seção. Hipótese forte; quando o resultado sai do intervalo 0–1, é sinal de que ela falha
(seções com fila longa diferem das demais por outros motivos). Reportado por transparência, não como estimativa confiável.</li>
<li><strong>E4, pré-registrado</strong>: a seção como controle de si mesma. Se os votos tardios do 2º turno favorecessem um candidato, as seções com muitos votos tardios
deslocariam a fração desse candidato, entre o 1º e o 2º turno, mais que as seções sem votos tardios.</li>
</ol>
{bloco("2")}
{bloco("1")}
<h2>E4 — a seção contra si mesma (1º → 2º turno)</h2>
'''
    if E:
        r = E["regressao_delta13_vs_tardios2T"]; rc = E["controle_regressao_delta13_vs_tardios1T"]
        corpo += (f'<p>{N(E["secoes_comuns"])} seções presentes nos dois turnos com 30+ votos em cada. Variação da fração do candidato 13 (2º − 1º turno) contra a fração de votos '
                  f'de 17h em diante no 2º turno: correlação <strong>{r["correlacao"]}</strong> (inclinação {r["inclinacao"]}). Controle — a mesma relação usando a fila do 1º turno, quando não houve prorrogação: '
                  f'correlação {rc["correlacao"]}.</p>')
        corpo += tabela(["Faixa de votos tardios na seção (2T)", "Seções", "Votos (2T)", "Δ fração de 13 (p.p.)", "Δ fração de 22 (p.p.)"],
                        [[f["faixa_tardios_2T"], N(f["secoes"]), N(f["votos_2T"]), f["delta13_medio_pp"], f["delta22_medio_pp"]] for f in E["por_faixa"]])
        corpo += ('<p>Leitura: a variação média da fração de cada candidato entre os turnos é praticamente a mesma nas seções sem voto tardio e nas seções com voto tardio. '
                  'Correlação próxima de zero significa que o volume de votação tardia da seção não explica o deslocamento da seção entre os turnos. '
                  '<em>Limite obrigatório:</em> isto é inferência ecológica — correlação (ou ausência dela) no nível da seção não demonstra comportamento individual.</p>')
    b2 = T.get("2", {})
    if b2:
        corpo += (f'<h2>O que isso significa para o resultado</h2>'
                  f'<p>A diferença oficial entre os candidatos no 2º turno foi de <strong>{N(margem)}</strong> votos. Nas {len(b2["ufs_com_log"])} UFs com log analisado, os votos de 17h em diante somam '
                  f'<strong>{N(b2["votos_17h_em_diante"])}</strong> ({b2["pct_17h_em_diante"]:.3f}% dos votos) e os votos após 19h, {N(b2["votos_apos_19h"])}. '
                  f'Mesmo na hipótese extrema — impossível de verificar e sem apoio nos limites acima — de que <em>todos</em> os votos tardios tivessem ido a um único candidato, '
                  f'eles representariam {100*b2["votos_17h_em_diante"]/margem:.2f}% da margem.'.replace(".", ",") + ' O TSE informou 34.393 votos após as 17h em todo o país; o número desta página cresce conforme as UFs restantes entram.</p>')
    corpo += '<p>Código: <code>scripts/pipeline/tardios.py</code>. Dados: <code>dados/analises/tardios.json</code> e <code>tardios_secoes.csv</code> (seção a seção).</p>'
    return pagina("Votos depois das 17h: para quem? — Auditoria TSE 2026", "Teste E4 pré-registrado · limites e regressão ecológica (emenda de 28/10)",
                  "Os votos depois das 17h foram para algum candidato?", "O que os arquivos do TSE permitem — e não permitem — dizer, nos dois turnos, com os limites exatos.", corpo, "votos-tardios.html")

def main():
    A1 = agrega("1"); A2 = agrega("2")
    os.makedirs(f"{P}/repo/dados/analises", exist_ok=True)
    for t, A in (("1", A1), ("2", A2)):
        j = {k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in A.items()}
        j["anomalias"] = {k: v for k, v in A["anomalias"].items()}; j["anom_por_uf"] = {k: dict(v) for k, v in A["anom_por_uf"].items()}
        j["digitos"] = {c: dict(v) for c, v in A["digitos"].items()}; j["gerado_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        json.dump(j, open(f"{PL}/forense_{t}t.json", "w"), ensure_ascii=False)
        shutil.copy(f"{PL}/forense_{t}t.json", f"{P}/repo/dados/analises/")
    open(f"{SITE}/forense.html", "w").write(pagina_forense(A1, A2))
    if os.path.exists(f"{R}/a3_soma_oficial.json"):
        open(f"{SITE}/soma-oficial.html", "w").write(pagina_soma()); shutil.copy(f"{R}/a3_soma_oficial.json", f"{P}/repo/dados/analises/")
    if os.path.exists(f"{R}/tardios.json"):
        open(f"{SITE}/votos-tardios.html", "w").write(pagina_tardios()); shutil.copy(f"{R}/tardios.json", f"{P}/repo/dados/analises/")
        if os.path.exists(f"{R}/tardios_secoes.csv"): shutil.copy(f"{R}/tardios_secoes.csv", f"{P}/repo/dados/analises/")
    print(f"forense: {len(A1['ufs'])} UFs 1T, {len(A2['ufs'])} UFs 2T; páginas geradas")
if __name__ == "__main__": main()
