#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste K — concentração por horário × resultado, e RDV × boletim (emenda de 28/10/2026).

Agrega concentracao/{t}t/*.json (perfil horário por seção), rdv/{t}t/*.json (RDV × boletim)
e os votos por seção (resultados/{t}t/votos/*.csv) → pipeline/concentracao_{t}t.json,
repo/dados/analises/concentracao_secoes.csv e a página concentracao.html.
Roda sem argumentos; tolera dados parciais (mostra o que falta)."""
import collections, csv, datetime, glob, json, os, shutil
import numpy as np
from gera_forense import pagina, stat, tabela, N, PCT, P, PL, SITE, UFS, esc

CON = "/Volumes/SSD1TB/acervo-tse/auditoria/concentracao"
RDV = "/Volumes/SSD1TB/acervo-tse/auditoria/rdv"
DEMO = "/Volumes/SSD1TB/acervo-tse/auditoria/demo"
HORAS = list(range(7, 20))
MIN_VALIDOS = 30      # seção entra na comparação entre turnos com 30+ votos válidos (13+22) em cada turno
MIN_SEC_MUN = 5       # município entra como controle da própria seção com 5+ seções comparáveis
Z_ALERTA = 4.0        # desvio padronizado dentro do município que marca a seção para inspeção
R_ALERTA = 0.10       # e deslocamento absoluto de 10 pontos percentuais
TOPN = 30
NOMES = {}

def nome_mun(uf, cod):
    if uf not in NOMES:
        NOMES[uf] = {}
        for f in (f"{DEMO}/{uf}_municipios.json", f"{DEMO}2t/{uf}_municipios.json"):
            try:
                for k, v in (json.load(open(f)).get("municipios") or {}).items():
                    if isinstance(v, dict) and v.get("nome"): NOMES[uf][str(k)] = v["nome"]
                if NOMES[uf]: break
            except Exception: pass
    return NOMES[uf].get(str(cod), str(cod))

def votos(t, uf):
    """{(mun, zona, sec): [v13, v22, comparecimento]} do boletim (CSV extraído do bweb)."""
    f = f"{PL}/resultados/{t}t/votos/{uf}.csv"; d = {}
    if not os.path.exists(f): return d
    for r in csv.DictReader(open(f)):
        k = (int(r["municipio"]), int(r["zona"]), int(r["secao"]))
        e = d.setdefault(k, [0, 0, int(r["comparecimento"] or 0)])
        if r["tipo"] == "Nominal" and r["numero"] == "13": e[0] += int(r["votos"])
        elif r["tipo"] == "Nominal" and r["numero"] == "22": e[1] += int(r["votos"])
    return d

def perfil(t, uf):
    f = f"{CON}/{t}t/{uf}.json"
    if not os.path.exists(f): return None, None
    d = json.load(open(f)); cols = d["colunas"]
    return {(l[0], l[1], l[2]): dict(zip(cols, l)) for l in d["linhas"] if l[0] is not None}, d

def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 3 or x.std() == 0 or y.std() == 0: return None
    return float(np.corrcoef(x, y)[0, 1])

def quintis(x, y, rot):
    """Média de y por quintil de x (x com muitos zeros: o 1º grupo é x == 0)."""
    x = np.asarray(x, float); y = np.asarray(y, float); out = []
    zero = x == 0
    if zero.sum() > len(x) * 0.2:
        out.append([f"{rot} = 0", int(zero.sum()), float(y[zero].mean()) if zero.any() else None])
        xs, ys = x[~zero], y[~zero]
    else:
        xs, ys = x, y
    if len(xs) >= 5:
        q = np.quantile(xs, [0.2, 0.4, 0.6, 0.8]); b = np.digitize(xs, q)
        for i in range(5):
            m = b == i
            if m.any(): out.append([f"{rot} entre {xs[m].min():.3g} e {xs[m].max():.3g}", int(m.sum()), float(ys[m].mean())])
    return out

def svg_curva(series, titulo, w=820, h=240):
    """series: [(rotulo, cor, {'HH:MM': votos})] → % dos votos do turno por bloco de 10 min."""
    pad_l, pad_b, pad_t = 44, 34, 18
    blocos = sorted({k for _, _, s in series for k in s})
    if not blocos: return ""
    tot = [(r, c, s, sum(s.values())) for r, c, s in series if sum(s.values())]
    ymax = max(100 * s.get(k, 0) / n for _, _, s, n in tot for k in blocos) or 1
    gw = (w - pad_l - 8) / len(blocos); gh = h - pad_b - pad_t
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;font:11px ui-sans-serif,system-ui" role="img" aria-label="{esc(titulo)}">']
    for i in range(5):
        y = pad_t + gh - gh * i / 4; v = ymax * i / 4
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-8}" y2="{y:.1f}" stroke="#ddd8d0"/><text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" fill="#5c5955">{v:.1f}%</text>')
    for i, k in enumerate(blocos):
        if k.endswith(":00"):
            x = pad_l + i * gw
            out.append(f'<text x="{x:.1f}" y="{h-pad_b+16}" text-anchor="middle" fill="#5c5955">{k[:2]}h</text>')
            if k in ("17:00", "19:00"): out.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t+gh}" stroke="#8a2f2f" stroke-dasharray="4 3"/>')
    for j, (r, c, s, n) in enumerate(tot):
        pts = " ".join(f"{pad_l + i * gw + gw / 2:.1f},{pad_t + gh - gh * (100 * s.get(k, 0) / n) / ymax:.1f}" for i, k in enumerate(blocos))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2"/>')
        out.append(f'<rect x="{pad_l+8+j*200}" y="{pad_t-12}" width="10" height="10" fill="{c}"/><text x="{pad_l+22+j*200}" y="{pad_t-3}" fill="#1a1a1a">{esc(r)}</text>')
    out.append("</svg>")
    return "".join(out)

def k1(t):
    """RDV × boletim, agregado por turno."""
    A = {"ufs": [], "rdv_lidos": 0, "ilegiveis": 0, "sem_boletim": 0, "comparadas": 0, "iguais": 0, "diferentes": 0, "exemplos": [], "por_uf": {}, "totais_rdv": collections.Counter(), "totais_bu": collections.Counter()}
    for f in sorted(glob.glob(f"{RDV}/{t}t/??.json")):
        try: d = json.load(open(f))
        except Exception: continue
        A["ufs"].append(d["uf"])
        for k in ("rdv_lidos", "ilegiveis", "sem_boletim", "comparadas", "iguais", "diferentes"): A[k] += d.get(k, 0)
        A["por_uf"][d["uf"]] = {k: d.get(k, 0) for k in ("rdv_lidos", "ilegiveis", "sem_boletim", "comparadas", "iguais", "diferentes")}
        for k, v in d.get("totais_rdv", {}).items(): A["totais_rdv"][k] += v
        for k, v in d.get("totais_bu", {}).items(): A["totais_bu"][k] += v
        for e in d.get("exemplos_diferentes", [])[:10]:
            if len(A["exemplos"]) < 60: A["exemplos"].append({"uf": d["uf"], **e})
    A["faltam"] = [u for u in UFS if u not in A["ufs"]]
    A["totais_rdv"] = dict(A["totais_rdv"]); A["totais_bu"] = dict(A["totais_bu"])
    return A

def agrega():
    rows = []   # uma linha por seção presente nos dois turnos
    curva = {"1": collections.Counter(), "2": collections.Counter()}
    ufs_ok = {"1": [], "2": []}; secoes_perfil = {"1": 0, "2": 0}
    for uf in UFS:
        p1, d1 = perfil("1", uf); p2, d2 = perfil("2", uf)
        for t, d in (("1", d1), ("2", d2)):
            if d:
                ufs_ok[t].append(uf); secoes_perfil[t] += d["secoes"]
                for k, v in d["votos_por_bloco10"].items(): curva[t][k] += v
        if not p2: continue
        v1 = votos("1", uf); v2 = votos("2", uf)
        for k, r in p2.items():
            b2 = v2.get(k); b1 = v1.get(k)
            if not b2 or not b1: continue
            n2 = b2[0] + b2[1]; n1 = b1[0] + b1[1]
            if n2 < MIN_VALIDOS or n1 < MIN_VALIDOS: continue
            r1 = (p1 or {}).get(k) or {}
            rows.append({"uf": uf, "mun": k[0], "zona": k[1], "sec": k[2], "n1": n1, "n2": n2, "f1": b1[0] / n1, "f2": b2[0] / n2,
                         "comp2": b2[2], "votos_log": r["votos"], "apos17": r["apos17h"], "max10": r["max_bloco10min"], "bloco": r["bloco_max"],
                         "rajada": r["rajada"] if r["rajada"] is not None else 0.0, "horas": [r[f"h{h:02d}"] for h in HORAS],
                         "rajada1": r1.get("rajada") if r1.get("rajada") is not None else 0.0, "apos17_1": r1.get("apos17h", 0), "votos_log1": r1.get("votos", 0),
                         "horas1": [r1.get(f"h{h:02d}", 0) for h in HORAS]})
    return rows, curva, ufs_ok, secoes_perfil

def analisa(rows):
    R = {}
    if not rows: return R
    f1 = np.array([r["f1"] for r in rows]); f2 = np.array([r["f2"] for r in rows]); delta = f2 - f1
    vl = np.array([max(r["votos_log"], 1) for r in rows], float)
    apos = np.array([r["apos17"] for r in rows]) / vl
    raj = np.array([r["rajada"] for r in rows]); max10 = np.array([r["max10"] for r in rows]) / vl
    H = np.array([r["horas"] for r in rows], float) / vl[:, None]
    vl1 = np.array([max(r["votos_log1"], 1) for r in rows], float)
    H1 = np.array([r["horas1"] for r in rows], float) / vl1[:, None]   # controle: perfil horário da MESMA seção no 1º turno
    R["secoes"] = len(rows); R["delta_media_pp"] = float(delta.mean() * 100); R["delta_dp_pp"] = float(delta.std() * 100)
    R["delta_p1_pp"], R["delta_p50_pp"], R["delta_p99_pp"] = [float(x * 100) for x in np.quantile(delta, [0.01, 0.5, 0.99])]
    R["f13_medio_1t"] = float(f1.mean()); R["f13_medio_2t"] = float(f2.mean())
    # K2: a hora em que a seção concentra votos explica o deslocamento?
    R["por_hora"] = []
    for i, h in enumerate(HORAS):
        sh = H[:, i]
        if sh.sum() == 0: continue
        sh1 = H1[:, i]
        R["por_hora"].append({"hora": f"{h:02d}h", "secoes_com_voto": int((sh > 0).sum()), "fracao_media_dos_votos": float(sh.mean()),
                              "correlacao_com_delta13": pearson(sh, delta), "controle_correlacao_perfil_1t": pearson(sh1, delta) if sh1.sum() else None,
                              "delta_medio_pp_quinto_superior": float(delta[sh >= np.quantile(sh, 0.8)].mean() * 100) if (sh > 0).sum() > 10 else None})
    R["corr_apos17_delta"] = pearson(apos, delta); R["corr_rajada_delta"] = pearson(raj, delta); R["corr_max10_delta"] = pearson(max10, delta)
    R["quintis_apos17"] = quintis(apos, delta * 100, "fração de votos de 17h em diante")
    R["quintis_rajada"] = quintis(raj, delta * 100, "índice de rajada")
    R["quintis_max10"] = quintis(max10, delta * 100, "fração dos votos no bloco de 10 min mais cheio")
    # controle 1T: as mesmas medidas com a rajada do 1T (quando não houve prorrogação nem contestação)
    raj1 = np.array([r["rajada1"] for r in rows]); R["corr_rajada1t_delta"] = pearson(raj1, delta)
    # K3: a seção contra o próprio município
    mun = collections.defaultdict(list)
    for i, r in enumerate(rows): mun[(r["uf"], r["mun"])].append(i)
    z = np.zeros(len(rows)); res = np.zeros(len(rows)); ok = np.zeros(len(rows), bool)
    for key, idx in mun.items():
        if len(idx) < MIN_SEC_MUN: continue
        d = delta[idx]; m = d.mean(); s = max(d.std(), 0.02)
        for j, i in enumerate(idx):
            # leave-one-out na média
            m_loo = (d.sum() - d[j]) / (len(idx) - 1)
            res[i] = delta[i] - m_loo; z[i] = res[i] / s; ok[i] = True
    R["secoes_com_controle_municipal"] = int(ok.sum())
    alerta = ok & (np.abs(z) >= Z_ALERTA) & (np.abs(res) >= R_ALERTA)
    R["alertas"] = int(alerta.sum()); R["alertas_pro13"] = int((alerta & (res > 0)).sum()); R["alertas_pro22"] = int((alerta & (res < 0)).sum())
    R["alertas_esperados_normal"] = float(ok.sum() * 2 * 3.17e-5)   # P(|z|>=4) sob normalidade
    R["alertas_por_uf"] = collections.Counter(rows[i]["uf"] for i in np.where(alerta)[0])
    R["alertas_com_rajada_alta"] = int((alerta & (raj >= np.quantile(raj[ok], 0.9))).sum()) if ok.any() else 0
    R["alertas_com_votos_apos17"] = int((alerta & (apos > 0)).sum())
    ordem = np.argsort(-np.abs(res) * alerta)
    def linha(i):
        r = rows[i]
        return {"uf": r["uf"], "mun": r["mun"], "nome": nome_mun(r["uf"], r["mun"]), "zona": r["zona"], "sec": r["sec"], "n1": r["n1"], "n2": r["n2"],
                "f13_1t": round(r["f1"] * 100, 1), "f13_2t": round(r["f2"] * 100, 1), "delta_pp": round(delta[i] * 100, 1), "residuo_pp": round(res[i] * 100, 1), "z": round(float(z[i]), 1),
                "apos17": r["apos17"], "rajada": r["rajada"], "bloco": r["bloco"], "max10": r["max10"], "votos_log": r["votos_log"]}
    R["top_alertas"] = [linha(i) for i in ordem[:TOPN] if alerta[i]]
    # por UF
    R["por_uf"] = {}
    for uf in UFS:
        m = np.array([r["uf"] == uf for r in rows])
        if not m.any(): continue
        R["por_uf"][uf] = {"secoes": int(m.sum()), "delta_medio_pp": float(delta[m].mean() * 100), "delta_dp_pp": float(delta[m].std() * 100),
                           "corr_apos17": pearson(apos[m], delta[m]), "corr_rajada": pearson(raj[m], delta[m]), "alertas": int((alerta & m).sum())}
    R["delta_residuo_dp_pp"] = float(res[ok].std() * 100) if ok.any() else None
    # K2 dentro do município: a mesma correlação hora a hora, mas contra o resíduo municipal (remove a geografia:
    # regiões que votam cedo e regiões que se deslocaram mais entre os turnos são as mesmas regiões, não as mesmas urnas)
    for h in R["por_hora"]:
        i = HORAS.index(int(h["hora"][:2]))
        h["correlacao_residuo_municipal"] = pearson(H[ok, i], res[ok]) if ok.any() else None
        h["controle_residuo_perfil_1t"] = pearson(H1[ok, i], res[ok]) if ok.any() and H1[ok, i].sum() else None
        top = ok & (H[:, i] >= np.quantile(H[ok, i], 0.8)) if ok.any() else np.zeros(len(rows), bool)
        h["residuo_medio_pp_quinto_superior"] = float(res[top].mean() * 100) if top.any() else None
    R["corr_rajada_residuo"] = pearson(raj[ok], res[ok]) if ok.any() else None
    R["corr_apos17_residuo"] = pearson(apos[ok], res[ok]) if ok.any() else None
    return R

def pagina_concentracao(R, K1, K2, curva, ufs_ok, secoes_perfil):
    fmt = lambda v, nd=3: ("—" if v is None else f"{v:.{nd}f}".replace(".", ","))
    pp = lambda v: ("—" if v is None else f"{v:+.2f} p.p.".replace(".", ","))
    curva_svg = svg_curva([("1º turno (4/10)", "#8a2f2f", dict(curva["1"])), ("2º turno (25/10)", "#1f6b3a", dict(curva["2"]))], "Votos por bloco de 10 minutos, % do total do turno")
    def tab_k1(A, t):
        out = '<div class="grid">' + stat(f'{len(A["ufs"])}/28', "UFs") + stat(N(A["comparadas"]), "seções comparadas RDV × boletim") + stat(N(A["iguais"]), "iguais voto a voto", zero=(A["iguais"] == A["comparadas"] and A["comparadas"] > 0)) + stat(N(A["diferentes"]), "diferentes", zero=(A["diferentes"] == 0)) + "</div>"
        if A["faltam"]: out += f'<p><strong>Em processamento:</strong> {", ".join(A["faltam"])}.</p>'
        tr = A["totais_rdv"]; tb = A["totais_bu"]
        chaves = ["13", "22"] + [k for k in sorted(tr) if k not in ("13", "22", "branco", "nulo")] + ["branco", "nulo"]
        out += tabela(["Voto", "Soma dos RDV", "Soma dos boletins", "Diferença"], [[k, N(tr.get(k, 0)), N(tb.get(k, 0)), N(tr.get(k, 0) - tb.get(k, 0))] for k in chaves if tr.get(k) or tb.get(k)])
        if A["exemplos"]:
            out += '<details><summary>Seções diferentes (até 60 exemplos)</summary>' + tabela(["UF", "Seção", "RDV", "Boletim"], [[e["uf"], e["secao"], esc(json.dumps(e["rdv"], ensure_ascii=False)), esc(json.dumps(e["bu"], ensure_ascii=False))] for e in A["exemplos"]]) + "</details>"
        return out
    corpo = f'''
<blockquote><p><strong>Pergunta:</strong> com uma diferença de poucos pontos entre os candidatos, houve algum horário em que os votos se concentraram de forma
estranha num só candidato — urna por urna, cidade por cidade, estado por estado? O normal não seria "voto para um, voto para outro", alternando?</p>
<p><strong>Resposta curta:</strong> a sequência "um, outro" não existe em nenhum arquivo público — o log tem a hora de cada voto mas não o candidato, e o RDV tem
os candidatos mas sem hora e sem ordem. É o sigilo do voto, por construção. O que existe e foi medido: (1) o RDV de cada seção bate voto a voto com o boletim;
(2) o horário em que cada seção concentrou votos não explica o deslocamento do resultado dessa seção entre os turnos; (3) a seção comparada com as vizinhas do
próprio município não mostra concentração anormal associada a horário, rajada ou votação tardia. Os números e os limites estão abaixo.</p></blockquote>

<h2>Primeiro, o que é "normal"</h2>
<p>Numa seção em que o candidato A tem 52% e o B 48%, os votos não alternam: cada eleitor é um sorteio independente, e sequências longas do mesmo
candidato são a regra, não a exceção. A chance de 10 votos seguidos no mesmo candidato é de cerca de 2 × 0,52¹⁰ ≈ 0,3% para cada janela de 10 votos — em
128 milhões de votos, isso acontece dezenas de milhares de vezes por acaso; sequências de 20 ou 30 seguidos também ocorrem aos milhares. Por isso uma
"janela em que só um candidato recebe votos" não seria, por si, indício de nada, mesmo que fosse observável. O que seria indício é outra coisa: um
<em>conjunto de seções</em> em que a concentração num horário veio acompanhada de deslocamento do resultado para um lado só, acima do que a vizinhança e o
próprio 1º turno explicam. É isso que se testa.</p>
<p><strong>Por que a sequência não é observável.</strong> O log da urna registra «Voto confirmado para [Presidente]» com hora, sem o número digitado. O Registro
Digital do Voto grava o número de cada voto, mas a urna o escreve agrupado por número, sem hora e sem a ordem em que os votos entraram — abrindo o arquivo,
vê-se todos os votos de um candidato, depois todos do outro, depois brancos e nulos. Cruzar os dois arquivos para recuperar "quem votou às 17h20" é
impossível; se fosse possível, o voto não seria secreto.</p>

<h2>K1 — o RDV bate com o boletim, voto a voto?</h2>
<p>Se alguém alterasse o boletim de uma seção (ou os arquivos transmitidos), o RDV gravado pela urna não bateria. Decodificamos o RDV de cada seção —
formato DER/ASN.1 — e contamos, para Presidente, os votos por número digitado, brancos e nulos; depois comparamos com o boletim da mesma seção.
Código: <code>scripts/pipeline/rdv_bu.py</code>. Calibração do tipo de voto feita contra o próprio boletim e registrada no código.</p>
<h3>2º turno</h3>{tab_k1(K1["2"], "2")}
<h3>1º turno</h3>{tab_k1(K1["1"], "1")}

<h2>K2 — a hora em que a seção concentrou votos explica o resultado?</h2>
<p>Para cada seção com 30+ votos válidos (13 + 22) nos dois turnos, medimos o <strong>deslocamento</strong> Δ = fração de 13 no 2º turno − fração de 13 no
1º turno (sobre 13 + 22). Se houvesse injeção de votos para um candidato num horário, as seções com mais votos nesse horário teriam Δ deslocado para esse lado.
Medimos, hora a hora, a correlação entre a fração dos votos da seção naquela hora e Δ, e o Δ médio das seções que mais concentram votos naquela hora.
Fonte do horário: log da urna, hora de Brasília. Código: <code>scripts/pipeline/concentracao.py</code> e <code>gera_concentracao.py</code>.</p>
{curva_svg}
<p>Curva de votos por bloco de 10 minutos nos dois turnos (linhas tracejadas: 17h e 19h). No 2º turno a fila do fim do dia praticamente não existe: o voto de um
cargo é rápido e a prorrogação até 19h pegou seções quase vazias.</p>
<div class="grid">{stat(N(R.get("secoes", 0)), "seções comparadas entre os turnos")}{stat(pp(R.get("delta_media_pp")), "Δ médio (fração de 13, 2º − 1º turno)")}{stat(fmt(R.get("delta_dp_pp"), 2) + " p.p.", "desvio padrão de Δ")}{stat(fmt(R.get("corr_apos17_delta")), "correlação: fração de votos de 17h em diante × Δ")}{stat(fmt(R.get("corr_rajada_delta")), "correlação: índice de rajada × Δ")}{stat(fmt(R.get("corr_rajada1t_delta")), "controle: rajada do 1º turno × Δ")}</div>
<h3>Hora a hora</h3>
{tabela(["Hora", "Seções com voto nessa hora", "Fração média dos votos da seção", "Correlação com Δ, país inteiro", "Correlação com o resíduo (a seção contra o próprio município)", "Controle: perfil da seção no 1º turno × resíduo", "Resíduo médio do quinto de seções que mais concentra votos nessa hora"],
        [[h["hora"], N(h["secoes_com_voto"]), fmt(h["fracao_media_dos_votos"]), fmt(h["correlacao_com_delta13"]), fmt(h.get("correlacao_residuo_municipal")), fmt(h.get("controle_residuo_perfil_1t")), pp(h.get("residuo_medio_pp_quinto_superior"))] for h in R.get("por_hora", [])])}
<p>Leitura. Nas horas da prorrogação (17h e 18h) a correlação é zero em todas as colunas: concentrar votos nessas horas não deslocou o resultado de nenhuma seção
para nenhum lado. No país inteiro, as horas da manhã e do meio-dia mostram correlações pequenas e de sinais opostos (manhã para 22, meio-dia para 13). A coluna
seguinte explica de onde vêm: quando cada seção é comparada só com as vizinhas do próprio município, a correlação cai para perto de zero. É geografia — as
regiões onde se vota mais cedo são também as regiões que se deslocaram de forma diferente entre os turnos —, não algo que aconteceu dentro das urnas. Uma
injeção de votos num horário apareceria <em>dentro</em> do município: a seção que concentrou votos naquela hora teria se deslocado em relação às vizinhas.</p>
<h3>Rajada: a seção que votou "em bloco"</h3>
<p>Índice de rajada = votos no bloco de 10 minutos mais cheio ÷ média dos blocos com voto. Uma seção que recebeu muitos votos num intervalo curto tem índice alto.</p>
{tabela(["Faixa", "Seções", "Δ médio"], [[a, N(b), pp(c)] for a, b, c in R.get("quintis_rajada", [])])}
{tabela(["Fração de votos de 17h em diante", "Seções", "Δ médio"], [[a, N(b), pp(c)] for a, b, c in R.get("quintis_apos17", [])])}

<h2>K3 — a seção contra o próprio município</h2>
<p>Cada seção é comparada com as demais do mesmo município (5+ seções comparáveis): resíduo = Δ da seção − Δ médio das outras; z = resíduo ÷ desvio padrão do
município (mínimo 2 p.p.). Marcamos para inspeção as seções com |z| ≥ 4 <em>e</em> resíduo de 10 pontos ou mais — um deslocamento que nem o 1º turno nem a
vizinhança explicam. Sob normalidade esperam-se cerca de {fmt(R.get("alertas_esperados_normal"), 1)} seções assim por puro acaso.</p>
<div class="grid">{stat(N(R.get("secoes_com_controle_municipal", 0)), "seções com controle municipal")}{stat(N(R.get("alertas", 0)), "seções marcadas (|z| ≥ 4 e ≥ 10 p.p.)")}{stat(N(R.get("alertas_pro13", 0)), "deslocadas para 13")}{stat(N(R.get("alertas_pro22", 0)), "deslocadas para 22")}{stat(N(R.get("alertas_com_votos_apos17", 0)), "das marcadas, com voto após 17h")}{stat(N(R.get("alertas_com_rajada_alta", 0)), "das marcadas, com rajada no décimo superior")}</div>
<p>Se a concentração fosse fraude de um lado, as seções marcadas pesariam para um candidato e estariam associadas a horário, rajada ou votação tardia. Seções
marcadas repartidas entre os dois lados e sem associação com o horário são o que se espera de variação local real (seção de instituição, de zona rural, urna
substituída, mudança de eleitores entre turnos).</p>
<h3>Seções marcadas, maiores resíduos</h3>
{tabela(["UF", "Município", "Zona", "Seção", "Válidos 1T / 2T", "13 no 1T", "13 no 2T", "Δ", "Resíduo", "z", "Votos após 17h", "Rajada", "Bloco mais cheio"],
        [[e["uf"], (f'<a href="estados/{e["uf"]}/{e["mun"]}.html">{esc(e["nome"])}</a>' if os.path.exists(f'{SITE}/estados/{e["uf"]}/{e["mun"]}.html') else esc(e["nome"])), e["zona"], e["sec"], f'{N(e["n1"])} / {N(e["n2"])}',
          f'{e["f13_1t"]}%', f'{e["f13_2t"]}%', pp(e["delta_pp"]), pp(e["residuo_pp"]), e["z"], N(e["apos17"]), fmt(e["rajada"], 2), e["bloco"] or "—"] for e in R.get("top_alertas", [])]) if R.get("top_alertas") else "<p>Nenhuma seção marcada.</p>"}
<h3>Por UF</h3>
<details><summary>Δ médio, dispersão, correlações e seções marcadas por UF</summary>
{tabela(["UF", "Seções", "Δ médio", "Desvio padrão", "Corr. votos após 17h × Δ", "Corr. rajada × Δ", "Marcadas"],
        [[u, N(d["secoes"]), pp(d["delta_medio_pp"]), fmt(d["delta_dp_pp"], 2) + " p.p.", fmt(d["corr_apos17"]), fmt(d["corr_rajada"]), N(d["alertas"])] for u, d in R.get("por_uf", {}).items()])}</details>

<h2>Como se identificaria uma falcatrua de mesário — e o que foi testado</h2>
<ol>
<li><strong>Votar pelo ausente exige tempo de urna.</strong> Cada voto injetado é uma habilitação e um «Voto confirmado» no log, com hora. Rastro: ritmo e sequência
(<a href="pianista.html">pianista</a>, <a href="reta-final.html">C4b</a>), habilitações × votos computados (L9), comparecimento × aptos (D, V).</li>
<li><strong>Alterar o boletim depois do fechamento.</strong> Rastro: RDV ≠ boletim (K1), hash assinado pela urna ≠ arquivo (A5), soma dos boletins ≠ totalização (A3).</li>
<li><strong>Concentrar votos de um lado num horário.</strong> Rastro: seções com votação nesse horário deslocadas para um lado, contra o próprio 1º turno e contra a
vizinhança (K2, K3, <a href="votos-tardios.html">E4</a>).</li>
<li><strong>O que não deixa rastro em dado público:</strong> um eleitor real que vota diferente do que diria. Isso não é fraude, é voto.</li>
</ol>
<p>Dados: <code>dados/analises/concentracao_2t.json</code> (agregados, hora a hora, por UF, seções marcadas), <code>concentracao_secoes.csv</code> (uma linha por
seção comparável: frações nos dois turnos, Δ, resíduo, z, perfil horário) e <code>rdv_1t.json</code> / <code>rdv_2t.json</code>.</p>
'''
    falta = [u for u in UFS if u not in ufs_ok["2"]]
    if falta: corpo = f'<p><strong>Em processamento:</strong> perfil horário do 2º turno ainda sem {", ".join(falta)}; a página cresce conforme as UFs terminam.</p>' + corpo
    return pagina("Concentração por horário e RDV × boletim — Auditoria TSE 2026", "Teste K · emenda de 28/10 · horário × resultado · RDV voto a voto",
                  "Houve concentração de votos num candidato em algum horário?", "O que os arquivos permitem medir, urna por urna, cidade por cidade, estado por estado — e o que não permitem.",
                  corpo, "concentracao.html")

def main():
    rows, curva, ufs_ok, secoes_perfil = agrega()
    R = analisa(rows)
    K1 = {"1": k1("1"), "2": k1("2")}
    os.makedirs(f"{P}/repo/dados/analises", exist_ok=True)
    j = dict(R); j["alertas_por_uf"] = dict(R.get("alertas_por_uf", {})); j["gerado_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    j["ufs_perfil"] = ufs_ok; j["secoes_perfil"] = secoes_perfil; j["curva_10min"] = {t: dict(c) for t, c in curva.items()}
    json.dump(j, open(f"{PL}/concentracao_2t.json", "w"), ensure_ascii=False); shutil.copy(f"{PL}/concentracao_2t.json", f"{P}/repo/dados/analises/")
    for t in ("1", "2"):
        json.dump(K1[t], open(f"{PL}/rdv_{t}t.json", "w"), ensure_ascii=False); shutil.copy(f"{PL}/rdv_{t}t.json", f"{P}/repo/dados/analises/")
    with open(f"{P}/repo/dados/analises/concentracao_secoes.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["uf", "municipio", "zona", "secao", "validos_1t", "validos_2t", "fracao13_1t", "fracao13_2t", "delta", "votos_log_2t", "apos17h_2t", "max_bloco10min_2t", "bloco_max_2t", "rajada_2t", "rajada_1t"] + [f"h{h:02d}_2t" for h in HORAS])
        for r in rows: w.writerow([r["uf"], r["mun"], r["zona"], r["sec"], r["n1"], r["n2"], round(r["f1"], 5), round(r["f2"], 5), round(r["f2"] - r["f1"], 5), r["votos_log"], r["apos17"], r["max10"], r["bloco"], r["rajada"], r["rajada1"]] + r["horas"])
    open(f"{SITE}/concentracao.html", "w").write(pagina_concentracao(R, K1, None, curva, ufs_ok, secoes_perfil))
    print(f"concentracao: {len(rows)} seções comparáveis, {len(ufs_ok['2'])} UFs 2T; RDV 2T {K1['2']['comparadas']} comparadas, {K1['2']['diferentes']} diferentes; página gerada")

if __name__ == "__main__": main()
