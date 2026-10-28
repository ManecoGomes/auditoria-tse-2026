#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agrega pianista/{t}t/*.json → pipeline/pianista_{t}t.json, grava a página pianista.html
e copia dados (JSON + CSV seção a seção) para repo/dados/analises. Emenda de 28/10/2026.
Roda sem argumentos; tolera dados parciais (mostra o que falta)."""
import collections, csv, datetime, glob, json, os, shutil
from gera_forense import pagina, stat, tabela, N, PCT, P, PL, SITE, UFS, esc

PIA = "/Volumes/SSD1TB/acervo-tse/auditoria/pianista"
DEMO = "/Volumes/SSD1TB/acervo-tse/auditoria/demo"
LIM = (20, 30, 40)
# UFs com 2º turno de governador: o eleitor votou em DOIS cargos em 25/10 (régua interna do 2º turno)
GOV_2T = {"AC", "AM", "DF", "ES", "RN", "TO"}
CARGOS = {"1": 5, "2": 1}   # cargos por eleitor: 1T = presidente, governador, senador, dep. federal, dep. estadual
CORRIDAS = (3, 5, 10)
FAIXAS_10 = (100, 150, 200, 300)
TOPN = 25
NOMES = {}

def nome_mun(uf, cod):
    if uf not in NOMES:
        NOMES[uf] = {}
        for f in (f"{DEMO}/{uf}_municipios.json", f"{DEMO}2t/{uf}_municipios.json"):
            try:
                m = json.load(open(f)).get("municipios") or {}
                for k, v in m.items():
                    if isinstance(v, dict) and v.get("nome"): NOMES[uf][str(k)] = v["nome"]
                if NOMES[uf]: break
            except Exception: pass
    return NOMES[uf].get(str(cod), str(cod))

def agrega(t):
    A = {"turno": t, "ufs": [], "intervalos": 0, "abaixo": {L: 0 for L in LIM}, "final_intervalos": 0, "final_abaixo": {L: 0 for L in LIM},
         "secoes": 0, "secoes_com_votos": 0, "votos": 0, "dist": collections.Counter(), "dist_final": collections.Counter(),
         "dist_cargos": {},
         "corrida_secoes": {L: {k: 0 for k in CORRIDAS} for L in LIM}, "corrida_final_secoes": {L: {k: 0 for k in CORRIDAS} for L in LIM},
         "corrida_max": {L: 0 for L in LIM}, "corrida_final_max": {L: 0 for L in LIM},
         "min10_secoes": {f: 0 for f in FAIXAS_10}, "min10_min": None, "por_uf": {}, "top_corrida30": [], "top_min10": [], "top_final30": [],
         "membros_falhos": 0, "fontes": {}}
    linhas_csv = []
    for f in sorted(glob.glob(f"{PIA}/{t}t/??.json")):
        try: d = json.load(open(f))
        except Exception: continue
        uf = d["uf"]; A["ufs"].append(uf); A["membros_falhos"] += d.get("membros_falhos", 0); A["fontes"][uf] = d.get("fonte")
        dist = {int(k): v for k, v in d["dist"].items()}; distf = {int(k): v for k, v in d["dist_final"].items()}
        # cargos digitados pelo eleitor: 1T = 5 (so Presidente no Exterior); 2T = 1 (2 onde houve 2T de governador)
        cargos = (1 if uf == "ZZ" else 5) if t == "1" else (2 if uf in GOV_2T else 1)
        for k, v in dist.items():
            A["dist"][k] += v
            A["dist_cargos"].setdefault(cargos, collections.Counter())[k] += v
        for k, v in distf.items(): A["dist_final"][k] += v
        ni = sum(dist.values()); nf = sum(distf.values())
        u = {"uf": uf, "cargos": cargos, "secoes": d["secoes"], "intervalos": ni,
             "abaixo": {L: sum(v for k, v in dist.items() if k < L) for L in LIM},
             "final_intervalos": nf, "final_abaixo": {L: sum(v for k, v in distf.items() if k < L) for L in LIM},
             "corrida_secoes": {L: {k: 0 for k in CORRIDAS} for L in LIM}, "corrida_final_secoes": {L: {k: 0 for k in CORRIDAS} for L in LIM},
             "corrida_max": {L: 0 for L in LIM}, "min10_min": None, "min10_abaixo150": 0, "votos": 0}
        A["intervalos"] += ni; A["final_intervalos"] += nf; A["secoes"] += d["secoes"]
        for L in LIM: A["abaixo"][L] += u["abaixo"][L]; A["final_abaixo"][L] += u["final_abaixo"][L]
        for l in d["linhas"]:
            if len(l) != 20: l = l[:5] + [0] * 13 + [None, None]   # seção sem 2 votos (versão 1 gravava 23 colunas)
            mun, zona, sec, votos, nint, a20, a30, a40, nfi, f20, f30, f40, c20, c30, c40, cf20, cf30, cf40, min10, med = l
            u["votos"] += votos; A["votos"] += votos
            if nint: A["secoes_com_votos"] += 1
            cor = {20: c20, 30: c30, 40: c40}; corf = {20: cf20, 30: cf30, 40: cf40}
            for L in LIM:
                for k in CORRIDAS:
                    if cor[L] >= k: u["corrida_secoes"][L][k] += 1; A["corrida_secoes"][L][k] += 1
                    if corf[L] >= k: u["corrida_final_secoes"][L][k] += 1; A["corrida_final_secoes"][L][k] += 1
                u["corrida_max"][L] = max(u["corrida_max"][L], cor[L]); A["corrida_max"][L] = max(A["corrida_max"][L], cor[L])
                A["corrida_final_max"][L] = max(A["corrida_final_max"][L], corf[L])
            if min10 is not None:
                for fx in FAIXAS_10:
                    if min10 < fx: A["min10_secoes"][fx] += 1
                if min10 < 150: u["min10_abaixo150"] += 1
                if u["min10_min"] is None or min10 < u["min10_min"]: u["min10_min"] = min10
                if A["min10_min"] is None or min10 < A["min10_min"]: A["min10_min"] = min10
            row = {"uf": uf, "municipio": mun, "nome": nome_mun(uf, mun), "zona": zona, "secao": sec, "votos": votos, "intervalos": nint,
                   "abaixo30": a30, "abaixo40": a40, "corrida20": c20, "corrida30": c30, "corrida40": c40, "final_intervalos": nfi,
                   "final_corrida30": cf30, "final_corrida40": cf40, "min10": min10, "mediana": med}
            if c30 >= 3 or (min10 is not None and min10 < 200) or cf30 >= 3:
                A["top_corrida30"].append(row)
            linhas_csv.append([uf, mun, zona, sec, votos, nint, a20, a30, a40, nfi, f20, f30, f40, c20, c30, c40, cf20, cf30, cf40, min10, med])
        A["por_uf"][uf] = u
    cand = A["top_corrida30"]
    A["top_min10"] = sorted([r for r in cand if r["min10"] is not None], key=lambda r: (r["min10"], -r["corrida30"]))[:TOPN]
    A["top_final30"] = sorted([r for r in cand if r["final_corrida30"] >= 3], key=lambda r: (-r["final_corrida30"], -r["final_corrida40"]))[:TOPN]
    A["top_corrida30"] = sorted(cand, key=lambda r: (-r["corrida30"], -r["corrida40"], r["min10"] if r["min10"] is not None else 10**9))[:TOPN]
    A["faltam"] = [u for u in UFS if u not in A["ufs"]]
    A["gerado_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return A, linhas_csv

def svg_hist(series, titulo, xmax=120, w=820, h=230):
    """series: [(rotulo, cor, Counter)], barras de % por segundo, 0..xmax."""
    pad_l, pad_b, pad_t = 44, 34, 18
    tots = [(r, c, cnt, sum(cnt.values())) for r, c, cnt in series if sum(cnt.values())]
    if not tots: return ""
    ymax = max(100 * cnt.get(s, 0) / n for _, _, cnt, n in tots for s in range(xmax + 1)) or 1
    gw = (w - pad_l - 8) / (xmax + 1); gh = h - pad_b - pad_t
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;font:11px ui-sans-serif,system-ui" role="img" aria-label="{esc(titulo)}">']
    for i in range(5):
        y = pad_t + gh - gh * i / 4; v = ymax * i / 4
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-8}" y2="{y:.1f}" stroke="#ddd8d0" stroke-width="1"/>'
                   f'<text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" fill="#5c5955">{v:.1f}%</text>')
    for s in range(0, xmax + 1, 10):
        x = pad_l + s * gw
        out.append(f'<text x="{x:.1f}" y="{h-pad_b+16}" text-anchor="middle" fill="#5c5955">{s}s</text>')
    nser = len(tots); bw = max(gw / nser - 0.3, 0.6)
    for j, (r, c, cnt, n) in enumerate(tots):
        for s in range(xmax + 1):
            v = 100 * cnt.get(s, 0) / n
            if not v: continue
            bh = gh * v / ymax; x = pad_l + s * gw + j * bw
            out.append(f'<rect x="{x:.1f}" y="{pad_t+gh-bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{c}"/>')
    for j, (r, c, cnt, n) in enumerate(tots):
        out.append(f'<rect x="{pad_l+8+j*230}" y="{pad_t-12}" width="10" height="10" fill="{c}"/><text x="{pad_l+22+j*230}" y="{pad_t-3}" fill="#1a1a1a">{esc(r)} ({N(n)} intervalos)</text>')
    for L, cor in ((20, "#8a2f2f"), (30, "#8a5a00"), (40, "#1f6b3a")):
        x = pad_l + L * gw
        out.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+gh}" stroke="{cor}" stroke-dasharray="4 3"/>')
    out.append("</svg>")
    return "".join(out)

def tab_top(rows, t, col_extra=None):
    cols = ["UF", "Município", "Zona", "Seção", "Votos", "Corrida < 20 s", "Corrida < 30 s", "Corrida < 40 s", "Corrida < 30 s após 17h", "10 votos em", "Mediana"]
    ln = []
    for r in rows:
        mun = f'<a href="estados/{r["uf"]}/{r["municipio"]}.html">{esc(r["nome"])}</a>' if os.path.exists(f'{SITE}/estados/{r["uf"]}/{r["municipio"]}.html') else esc(r["nome"])
        ln.append([r["uf"], mun, r["zona"], r["secao"], N(r["votos"]), r["corrida20"], r["corrida30"], r["corrida40"], r["final_corrida30"],
                   (f'{r["min10"]} s' if r["min10"] is not None else "—"), (f'{r["mediana"]:.0f} s' if r["mediana"] is not None else "—")])
    return tabela(cols, ln)

def pagina_pianista(A1, A2):
    def bloco(A):
        t = A["turno"]; n = A["intervalos"]; nf = A["final_intervalos"]
        out = f'<div class="grid">' + stat(f'{len(A["ufs"])}/28', "UFs com log analisado") + stat(N(A["secoes"]), "seções") + stat(N(n), "intervalos entre votos (até 600 s)")
        for L in LIM:
            out += stat(PCT(A["abaixo"][L], n, 3), f"intervalos abaixo de {L} s ({N(A['abaixo'][L])})", zero=(A["abaixo"][L] == 0))
        out += "</div>"
        if A["faltam"]: out += f'<p><strong>Em processamento:</strong> {", ".join(A["faltam"])}.</p>'
        out += '<h3>Corridas: votos consecutivos abaixo do limiar</h3>'
        out += tabela(["Limiar", "Seções com 3+ seguidos", "Seções com 5+ seguidos", "Seções com 10+ seguidos", "Maior corrida no país", "— só de 17h em diante: 3+ / 5+ / 10+", "Maior corrida de 17h em diante"],
                      [[f"< {L} s", N(A["corrida_secoes"][L][3]), N(A["corrida_secoes"][L][5]), N(A["corrida_secoes"][L][10]), A["corrida_max"][L],
                        f'{N(A["corrida_final_secoes"][L][3])} / {N(A["corrida_final_secoes"][L][5])} / {N(A["corrida_final_secoes"][L][10])}', A["corrida_final_max"][L]] for L in LIM])
        out += '<h3>Os 10 votos mais rápidos de cada urna</h3>'
        out += tabela(["Seções cujos 10 votos consecutivos mais rápidos levaram menos de…", "Seções"],
                      [[f"{fx} s ({fx/10:.0f} s por voto)", N(A["min10_secoes"][fx])] for fx in FAIXAS_10]
                      + [["Menor tempo registrado para 10 votos seguidos (país)", f'{A["min10_min"]} s' if A["min10_min"] is not None else "—"]])
        return out
    def tab_uf(A):
        rows = []
        for uf in UFS:
            u = A["por_uf"].get(uf)
            if not u: rows.append([uf, "—", "em processamento", "", "", "", "", "", ""]); continue
            n = u["intervalos"]
            rows.append([uf, u["cargos"], N(u["secoes"]), N(n), PCT(u["abaixo"][20], n, 4), PCT(u["abaixo"][30], n, 3), PCT(u["abaixo"][40], n, 2),
                         f'{N(u["corrida_secoes"][30][5])} / {N(u["corrida_secoes"][40][10])}', f'{u["min10_min"]} s' if u["min10_min"] is not None else "—"])
        return tabela(["UF", "Cargos na urna", "Seções", "Intervalos", "< 20 s", "< 30 s", "< 40 s", "Seções com corrida 5+ (<30 s) / 10+ (<40 s)", "10 votos mais rápidos"], rows)
    h2 = svg_hist([("1º turno, 5 cargos", "#8a2f2f", A1["dist_cargos"].get(5, collections.Counter())),
                   ("1º turno, Exterior (só Presidente)", "#c47a7a", A1["dist_cargos"].get(1, collections.Counter())),
                   ("2º turno, 1 cargo", "#1f6b3a", A2["dist_cargos"].get(1, collections.Counter())),
                   ("2º turno, 2 cargos (AC AM DF ES RN TO)", "#8a5a00", A2["dist_cargos"].get(2, collections.Counter()))],
                  "Distribuição do intervalo entre votos consecutivos, 0 a 120 s")
    hf = svg_hist([("2º turno, dia inteiro", "#1f6b3a", A2["dist"]), ("2º turno, de 17h em diante", "#8a2f2f", A2["dist_final"])], "2º turno: antes e depois das 17h")
    r1_30 = PCT(A1["abaixo"][30], A1["intervalos"], 4); r2_30 = PCT(A2["abaixo"][30], A2["intervalos"], 3)
    corpo = f'''
<blockquote><p><strong>Pergunta:</strong> com limiar de 20 s não apareceu "pianista" — um mesário votando em série por eleitores ausentes. E com 30 s? E com 40 s?</p>
<p><strong>Resposta curta:</strong> a contagem solta de intervalos abaixo de 30 s ou 40 s cresce muito no 2º turno, mas por uma razão física — o eleitor votou em
<em>um</em> cargo em 25/10 e em <em>cinco</em> em 4/10 — e não por sequências. O que um pianista deixaria no log é uma <strong>corrida</strong>: muitos votos
seguidos, todos rápidos. As corridas estão medidas abaixo, seção por seção, nos dois turnos, inclusive só na janela das 17h às 19h.</p></blockquote>

<h2>O que se mede</h2>
<p>Para cada seção, a partir dos registros «Voto confirmado para [Presidente]» do dia do pleito: o intervalo entre votos consecutivos; quantos ficaram abaixo
de 20 s, 30 s e 40 s; a <strong>maior corrida</strong> (votos consecutivos todos abaixo do limiar); o mesmo só com votos de 17h em diante; e o <strong>menor tempo em
que a urna registrou 10 votos seguidos</strong>. O teste de 20 s é o C4 pré-registrado. Os limiares de 30 s e 40 s e as corridas são posteriores ao plano
(emenda de 28/10/2026) e, por isso, valem menos que os testes pré-registrados.</p>
<p><strong>Por que 30 s e 40 s não são o mesmo em cada turno.</strong> No 1º turno o eleitor digitou cinco cargos; no 2º, um só (dois em AC, AM, DF, ES, RN e TO,
que tiveram 2º turno de governador). Um voto de um cargo leva poucos segundos; a fila anda no ritmo da habilitação pelo mesário. Por isso o intervalo típico
cai de um turno para o outro, e as seis UFs com dois cargos são a régua interna do próprio 2º turno: se o 2º turno "rápido" fosse pianista, elas não seriam
mais lentas que as demais pelo simples número de cargos. Há ainda uma régua de um cargo <em>dentro do 1º turno</em>: no Exterior (ZZ) o eleitor vota só para
Presidente — e é exatamente lá que estão as seções mais rápidas do 1º turno, com a mesma cara do 2º.</p>

<h2>Distribuição dos intervalos</h2>
{h2}
<p>Linhas tracejadas: 20 s, 30 s e 40 s. O 1º turno quase não tem intervalo abaixo de 40 s ({PCT(A1["abaixo"][40], A1["intervalos"], 3)}); o 2º turno com um cargo tem
{PCT(A2["abaixo"][40], A2["intervalos"], 2)} — é o custo de digitar um número em vez de cinco.</p>
{hf}

<h2>2º turno (25/10/2026)</h2>
{bloco(A2)}
<h2>1º turno (4/10/2026) — régua</h2>
{bloco(A1)}

<h2>Leitura</h2>
<p>Um pianista precisa de tempo por voto perto do mínimo físico da urna <em>e</em> de sequência: dezenas de votos seguidos nesse ritmo, concentrados depois que a
fila acabou. As tabelas acima mostram quantas seções têm 3, 5 ou 10 votos seguidos abaixo de cada limiar, no dia inteiro e só de 17h em diante, e qual foi o
menor tempo para 10 votos seguidos em todo o país. Intervalos abaixo de 30 s: {r1_30} no 1º turno e {r2_30} no 2º. Corridas de 10 ou mais votos abaixo de 30 s:
{N(A1["corrida_secoes"][30][10])} seções no 1º turno e {N(A2["corrida_secoes"][30][10])} no 2º; de 17h em diante no 2º turno, {N(A2["corrida_final_secoes"][30][10])}.
As seções mais rápidas estão listadas abaixo, com link para a página do município, para que qualquer pessoa confira o log original no Portal Resultados.</p>
<p><em>Limite:</em> o log não identifica o eleitor. Uma corrida rápida é compatível com fila organizada e eleitores ágeis; o que o teste exclui é a
<em>ausência</em> de corridas — se não há sequências longas de votos rápidos, não há o rastro que a hipótese do pianista exige.</p>

<h2>Seções mais rápidas — 2º turno</h2>
<h3>Maiores corridas abaixo de 30 s</h3>
{tab_top(A2["top_corrida30"], "2")}
<h3>Maiores corridas abaixo de 30 s de 17h em diante</h3>
{tab_top(A2["top_final30"], "2") if A2["top_final30"] else "<p>Nenhuma seção com 3 ou mais votos seguidos abaixo de 30 s de 17h em diante.</p>"}
<h3>Menor tempo para 10 votos seguidos</h3>
{tab_top(A2["top_min10"], "2")}
<h2>Seções mais rápidas — 1º turno (régua)</h2>
<h3>Maiores corridas abaixo de 30 s</h3>
{tab_top(A1["top_corrida30"], "1")}
<h3>Menor tempo para 10 votos seguidos</h3>
{tab_top(A1["top_min10"], "1")}

<h2>Por UF</h2>
<details><summary>2º turno</summary>{tab_uf(A2)}</details>
<details><summary>1º turno</summary>{tab_uf(A1)}</details>
<p>Código: <code>scripts/pipeline/pianista.py</code> e <code>gera_pianista.py</code>. Dados: <code>dados/analises/pianista_1t.json</code>, <code>pianista_2t.json</code>
e, seção a seção, <code>pianista_secoes_1t.csv</code> e <code>pianista_secoes_2t.csv</code>.</p>
'''
    return pagina("Pianista: votos em série rápida demais? — Auditoria TSE 2026", "Teste C4 ampliado · 20, 30 e 40 s · corridas (emenda de 28/10)",
                  "Houve «pianista» na urna?", "Intervalos abaixo de 20, 30 e 40 s e sequências de votos rápidos, seção por seção, nos dois turnos.", corpo, "pianista.html")

def main():
    A1, csv1 = agrega("1"); A2, csv2 = agrega("2")
    os.makedirs(f"{P}/repo/dados/analises", exist_ok=True)
    cols = ["uf", "municipio", "zona", "secao", "votos", "intervalos", "abaixo20", "abaixo30", "abaixo40", "intervalos_final", "final_abaixo20", "final_abaixo30",
            "final_abaixo40", "corrida20", "corrida30", "corrida40", "corrida_final20", "corrida_final30", "corrida_final40", "menor_tempo_10_votos_s", "mediana_s"]
    for t, A, rows in (("1", A1, csv1), ("2", A2, csv2)):
        j = dict(A); j["dist"] = dict(A["dist"]); j["dist_final"] = dict(A["dist_final"]); j["dist_cargos"] = {k: dict(v) for k, v in A["dist_cargos"].items()}
        json.dump(j, open(f"{PL}/pianista_{t}t.json", "w"), ensure_ascii=False)
        shutil.copy(f"{PL}/pianista_{t}t.json", f"{P}/repo/dados/analises/")
        with open(f"{P}/repo/dados/analises/pianista_secoes_{t}t.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(cols); w.writerows(rows)
    open(f"{SITE}/pianista.html", "w").write(pagina_pianista(A1, A2))
    print(f"pianista: {len(A1['ufs'])} UFs 1T, {len(A2['ufs'])} UFs 2T; página gerada")

if __name__ == "__main__": main()
