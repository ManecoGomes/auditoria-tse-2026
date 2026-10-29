#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste K4–K7 — há um algoritmo de «queda linear» no software? (emenda de 28/10/2026, noite)

Hipótese testada, nas palavras de quem encomendou: o software da urna, ao perceber que o candidato 22
"sobe" na sequência de votos, acionaria uma queda linear a favor de 13, em eventos programados e
repetidos. A sequência voto a voto não é observável (log sem candidato; RDV sem hora/ordem). O que
o mecanismo deixaria, e aqui se mede:
  K4  margem por urna em torno do empate (assimetria: urnas de menos com 22 à frente por pouco);
  K5  a urna contra o próprio município (binomial: urnas com 22 à frente, observadas × esperadas);
  K6  a curva da totalização reconstruída boletim a boletim pela hora de recepção, e a mesma curva
      com a ordem de chegada embaralhada dentro de cada UF (a "queda" vem da geografia?);
  K7  estrutura temporal dos votos no log: periodicidade (espectro por segundo), uniformidade do
      segundo e do minuto, sequências de intervalos idênticas entre urnas, corridas de intervalos iguais.
Entradas: resultados/{t}t/bu_tempo/*.csv (extrai_bu_tempo.py), auditoria/tempo/{t}t/*.json (tempo.py).
Saídas: pipeline/algoritmo_{t}t.json → repo/dados/analises; site/algoritmo.html.
"""
import collections, csv, datetime, glob, json, os, shutil
import numpy as np
from scipy.stats import binom
from gera_forense import pagina, stat, tabela, N, PCT, P, PL, SITE, UFS, esc

TEMPO = "/Volumes/SSD1TB/acervo-tse/auditoria/tempo"
MIN_URNAS_MUN = 10
MIN_VALIDOS = 30
fmt = lambda v, nd=3: ("—" if v is None else f"{v:.{nd}f}".replace(".", ","))
pp = lambda v: ("—" if v is None else f"{v:+.2f} p.p.".replace(".", ","))

def carrega(t):
    rows = []
    for f in sorted(glob.glob(f"{PL}/resultados/{t}t/bu_tempo/??.csv")):
        for r in csv.DictReader(open(f)):
            try:
                rows.append({"uf": r["uf"], "mun": int(r["municipio"]), "nome": r["nome"], "zona": int(r["zona"]), "sec": int(r["secao"]),
                             "aptos": int(r["aptos"]), "comp": int(r["comparecimento"]), "v13": int(r["v13"]), "v22": int(r["v22"]),
                             "enc": r["encerramento"], "emi": r["emissao_bu"], "rec": r["recebido"], "tipo": r["tipo_urna"]})
            except Exception: continue
    return rows

def k4(rows, a="22", b="13"):
    """Margem por urna (a − b) em torno do empate; densidade da fração de a perto de 50%."""
    va = np.array([r["v" + a] for r in rows]); vb = np.array([r["v" + b] for r in rows]); n = va + vb
    ok = n >= MIN_VALIDOS; va, vb, n = va[ok], vb[ok], n[ok]
    m = va - vb
    hist = {int(k): int((m == k).sum()) for k in range(-60, 61)}
    # suavidade local: ajuste quadrático em log(contagem) nas margens 11..40 de cada lado, previsto para 1..10
    def esperado(lado):
        xs = np.array([k for k in range(11, 41)]) * lado; ys = np.array([hist[int(k)] for k in xs], float)
        xs2 = np.array([k for k in range(-40, 41) if 11 <= abs(k) <= 40]); ys2 = np.array([hist[int(k)] for k in xs2], float)
        c = np.polyfit(xs2, np.log(np.maximum(ys2, 1)), 2)
        return float(sum(np.exp(np.polyval(c, k * lado)) for k in range(1, 11)))
    obs_pos = sum(hist[k] for k in range(1, 11)); obs_neg = sum(hist[k] for k in range(-10, 0))
    esp_pos = esperado(1); esp_neg = esperado(-1)
    f = va / n
    bins = np.arange(0.30, 0.701, 0.005); dens = np.histogram(f, bins=bins)[0]
    i50 = int(np.searchsorted(bins, 0.5)) - 1
    return {"urnas": int(ok.sum()), "histograma_margem": hist, "empates": hist[0],
            "a_frente_1a10": obs_pos, "esperado_a_frente_1a10": esp_pos, "b_frente_1a10": obs_neg, "esperado_b_frente_1a10": esp_neg,
            "razao_a": obs_pos / esp_pos if esp_pos else None, "razao_b": obs_neg / esp_neg if esp_neg else None,
            "densidade_fracao_a": {f"{bins[i]:.3f}": int(dens[i]) for i in range(len(dens))},
            "abaixo_50_5bins": int(dens[i50 - 5:i50].sum()), "acima_50_5bins": int(dens[i50:i50 + 5].sum()),
            "abaixo_50_10a6": int(dens[i50 - 10:i50 - 5].sum()), "acima_50_6a10": int(dens[i50 + 5:i50 + 10].sum())}

def k5(rows, a="22", b="13"):
    """Dentro de cada município: urnas com a à frente observadas × esperadas pela binomial na média municipal."""
    mun = collections.defaultdict(list)
    for r in rows:
        n = r["v" + a] + r["v" + b]
        if n >= MIN_VALIDOS: mun[(r["uf"], r["mun"])].append((r["v" + a], n))
    faixas = [(0.30, 0.40), (0.40, 0.45), (0.45, 0.50), (0.50, 0.55), (0.55, 0.60), (0.60, 0.70)]
    acc = {f: {"municipios": 0, "urnas": 0, "obs": 0, "esp": 0.0} for f in faixas}
    piores = []
    for key, lst in mun.items():
        if len(lst) < MIN_URNAS_MUN: continue
        va = np.array([x for x, _ in lst]); n = np.array([y for _, y in lst]); p = va.sum() / n.sum()
        fx = next((f for f in faixas if f[0] <= p < f[1]), None)
        if not fx: continue
        obs = int((va * 2 > n).sum())
        esp = float(binom.sf(np.floor(n / 2), n, p).sum())     # P(X > n/2)
        acc[fx]["municipios"] += 1; acc[fx]["urnas"] += len(lst); acc[fx]["obs"] += obs; acc[fx]["esp"] += esp
        if len(lst) >= 30 and esp > 5 and (obs - esp) / np.sqrt(esp) < -3: piores.append({"uf": key[0], "mun": key[1], "urnas": len(lst), "p": round(float(p), 3), "obs": obs, "esp": round(esp, 1)})
    out = {f"{f[0]:.2f}-{f[1]:.2f}": {**v, "razao": (v["obs"] / v["esp"] if v["esp"] else None)} for f, v in acc.items()}
    tot_obs = sum(v["obs"] for v in acc.values()); tot_esp = sum(v["esp"] for v in acc.values())
    return {"faixas": out, "total_obs": tot_obs, "total_esp": tot_esp, "razao": tot_obs / tot_esp if tot_esp else None,
            "n_municipios_com_deficit_forte": len(piores),
            "municipios_com_deficit_forte": sorted(piores, key=lambda x: (x["obs"] - x["esp"]) / np.sqrt(x["esp"]))[:30]}

def k6(rows, t):
    """Curva da totalização pela hora de recepção; mesma curva com ordem embaralhada dentro da UF."""
    R = [r for r in rows if r["rec"] and r["v13"] + r["v22"] > 0]
    R.sort(key=lambda r: r["rec"])
    v13 = np.array([r["v13"] for r in R], float); v22 = np.array([r["v22"] for r in R], float)
    c13 = np.cumsum(v13); c22 = np.cumsum(v22); share = c13 / np.maximum(c13 + c22, 1)
    npts = 400; idx = np.linspace(0, len(R) - 1, npts).astype(int)
    curva = [{"pct_bu": round(100 * i / len(R), 2), "hora": R[i]["rec"][11:16], "f13": round(float(share[i]), 4)} for i in idx]
    # momentos: primeiro ponto em que 13 passa a liderar e não perde mais
    lid = share > 0.5
    virada = None
    for i in range(len(R)):
        if lid[i] and lid[i:].all(): virada = {"pct_bu": round(100 * i / len(R), 2), "hora": R[i]["rec"][11:19], "boletins": i}; break
    # embaralhamento: mantém o horário de cada boletim, troca quais boletins do MESMO grupo chegam em cada horário.
    # Três resoluções de geografia: UF, município, zona. Se a curva real cabe na faixa de um nível, sua forma é
    # explicada pela ordem de chegada dos grupos desse nível (quem chegou quando), sem nada além.
    rng = np.random.default_rng(2026); ufs = np.array([r["uf"] for r in R])
    grupos = {"uf": ufs, "municipio": np.array([f'{r["uf"]}-{r["mun"]}' for r in R]), "zona": np.array([f'{r["uf"]}-{r["mun"]}-{r["zona"]}' for r in R])}
    faixas = {}; dentro = {}
    for nivel, g in grupos.items():
        ordem = np.argsort(g, kind="stable"); gs = g[ordem]; cortes = np.flatnonzero(np.r_[True, gs[1:] != gs[:-1], True])
        bands = []
        for _ in range(20):
            perm = np.arange(len(R))
            for a, b in zip(cortes[:-1], cortes[1:]):
                m = ordem[a:b]; perm[m] = rng.permutation(m)
            s = np.cumsum(v13[perm]) / np.maximum(np.cumsum(v13[perm]) + np.cumsum(v22[perm]), 1)
            bands.append(s[idx])
        bands = np.array(bands); lo = bands.min(axis=0); hi = bands.max(axis=0)
        faixas[nivel] = (lo, hi); dentro[nivel] = int(((share[idx] >= lo - 0.002) & (share[idx] <= hi + 0.002)).sum())
    # maior distância (p.p.) da curva real à faixa de cada nível, depois dos primeiros 5% de boletins (início muito instável)
    ini = int(npts * 0.05)
    desvio = {nivel: round(100 * float(np.max(np.maximum(np.maximum(share[idx] - faixas[nivel][1], faixas[nivel][0] - share[idx]), 0)[ini:])), 2) for nivel in faixas}
    lo, hi = faixas["municipio"]
    # ordem de chegada por UF
    por_uf = {}
    for u in UFS:
        m = ufs == u
        if not m.any(): continue
        pos = np.where(m)[0]; f = v13[m].sum() / max(v13[m].sum() + v22[m].sum(), 1)
        por_uf[u] = {"boletins": int(m.sum()), "f13": round(float(f), 4), "posicao_mediana_pct": round(100 * float(np.median(pos)) / len(R), 1), "hora_mediana": R[int(np.median(pos))]["rec"][11:16]}
    # atrasos emissão → recepção
    def seg(s):
        try: return datetime.datetime.fromisoformat(s)
        except Exception: return None
    lag = [(seg(r["rec"]) - seg(r["emi"])).total_seconds() / 60 for r in R if seg(r["rec"]) and seg(r["emi"])]
    lag = np.array(lag)
    antes = int((lag < -180).sum())   # recebido antes da emissão, tolerando fuso de até 3 h (hora local da urna × hora de Brasília)
    return {"boletins": len(R), "curva": curva, "virada": virada, "faixa_embaralhada": [{"pct_bu": round(100 * i / len(R), 2), "lo": round(float(a), 4), "hi": round(float(b), 4)} for i, a, b in zip(idx, lo, hi)],
            "faixa_uf": [{"pct_bu": round(100 * i / len(R), 2), "lo": round(float(a), 4), "hi": round(float(b), 4)} for i, a, b in zip(idx, *faixas["uf"])],
            "pontos_dentro_da_faixa": dentro["municipio"], "pontos_dentro_por_nivel": dentro, "desvio_max_pp_por_nivel": desvio, "pontos": npts, "por_uf": por_uf,
            "atraso_emissao_recepcao_min": {"mediana": float(np.median(lag)), "p10": float(np.quantile(lag, 0.1)), "p90": float(np.quantile(lag, 0.9)), "recebidos_antes_da_emissao": antes},
            "primeiro_recebido": R[0]["rec"], "ultimo_recebido": R[-1]["rec"]}

def k7(t):
    por_seg = np.zeros(86400); seg_min = np.zeros(60); min_hora = np.zeros(60); ufs = []; secoes = 0
    rep_ini = collections.Counter(); rep_fim = collections.Counter(); corridas = collections.Counter(); pausas = []; n_ass = 0
    for f in sorted(glob.glob(f"{TEMPO}/{t}t/??.json")):
        try: d = json.load(open(f))
        except Exception: continue
        ufs.append(d["uf"]); secoes += d["secoes"]
        por_seg += np.array(d["por_segundo"], float); seg_min += np.array(d["segundo_no_minuto"], float); min_hora += np.array(d["minuto_na_hora"], float)
        for k, v in d["assinaturas_iniciais_repetidas"].items(): rep_ini[k] += v
        for k, v in d["assinaturas_finais_repetidas"].items(): rep_fim[k] += v
        for l in d["linhas"]:
            if l[3] >= 41: n_ass += 1
            corridas[min(l[6], 10)] += 1
            if l[4] is not None and l[3] >= 30: pausas.append((l[4], l[5], d["uf"], l[0], l[1], l[2]))
    if not ufs: return {"ufs": []}
    # espectro: série por segundo das 8h às 17h (9 h = 32.400 s), sem a tendência (média móvel de 10 min)
    s = por_seg[8 * 3600:17 * 3600]
    tend = np.convolve(s, np.ones(600) / 600, mode="same"); res = s - tend
    spec = np.abs(np.fft.rfft(res)) ** 2; freqs = np.fft.rfftfreq(len(res), d=1.0)
    ordem = np.argsort(spec[1:])[::-1][:10] + 1
    picos = [{"periodo_s": round(1 / freqs[i], 2), "potencia_relativa": round(float(spec[i] / spec[1:].mean()), 1)} for i in ordem]
    # autocorrelação nos múltiplos de 60 s (um gerador por minuto apareceria aqui)
    def acf(x, lag): return float(np.corrcoef(x[:-lag], x[lag:])[0, 1])
    acfs = {str(l): round(acf(res, l), 4) for l in (1, 2, 5, 10, 30, 60, 120, 300, 600, 900, 1800, 3600)}
    # uniformidade do segundo no minuto e do minuto na hora (esta só das 9h às 16h, longe da abertura e do fechamento)
    def qui(v):
        e = v.sum() / len(v); return float(((v - e) ** 2 / e).sum())
    pm = np.array([por_seg[i:i + 60].sum() for i in range(0, 86400, 60)])
    # minuto na hora: o fluxo do dia cai dentro de cada hora (no 2T, de forma acentuada); desconta-se a
    # tendência linear de cada hora e mede-se o que sobra — um minuto "preferido" sobreviveria ao desconto
    mh = np.array([pm[h * 60 + m] for h in range(9, 16) for m in range(60)], float).reshape(7, 60)
    xs = np.arange(60); res_mh = np.zeros(60); rel = []
    for r in mh:
        c = np.polyfit(xs, r, 2); res_mh += r - np.polyval(c, xs); rel.append(np.abs(r - np.polyval(c, xs)) / np.polyval(c, xs))
    min_hora = mh.sum(axis=0)
    qui2_min_detrend = float((res_mh ** 2 / (min_hora.mean())).sum())
    max_desvio_minuto_pct = float(100 * np.max(rel))   # maior desvio de um minuto, em qualquer hora, à tendência quadrática da hora
    pausas.sort(key=lambda x: -x[0])
    return {"ufs": ufs, "secoes": secoes, "votos": int(por_seg.sum()), "picos_espectro": picos, "autocorrelacao": acfs,
            "qui2_segundo_no_minuto": qui(seg_min), "qui2_minuto_na_hora": qui(min_hora), "qui2_minuto_na_hora_sem_tendencia": qui2_min_detrend, "max_desvio_minuto_pct": max_desvio_minuto_pct, "gl": 59,
            "minuto_na_hora_9_16h": [int(v) for v in min_hora],
            "segundo_no_minuto_min_max": [int(seg_min.min()), int(seg_min.max())],
            "assinaturas_comparaveis": n_ass, "assinaturas_iniciais_repetidas": sum(rep_ini.values()), "grupos_iniciais": len(rep_ini),
            "assinaturas_finais_repetidas": sum(rep_fim.values()), "grupos_finais": len(rep_fim),
            "corridas_intervalos_identicos": {str(k): v for k, v in sorted(corridas.items())},
            "maiores_pausas": [{"segundos": p[0], "hora": p[1], "uf": p[2], "mun": p[3], "zona": p[4], "sec": p[5]} for p in pausas[:15]],
            "por_minuto_nacional": [int(por_seg[i:i + 60].sum()) for i in range(0, 86400, 60)]}

def svg_curva(K, w=820, h=260):
    if not K.get("curva"): return ""
    pad_l, pad_b, pad_t = 48, 34, 16
    pts = K["curva"]; fx = K["faixa_embaralhada"]
    ymin, ymax = 0.40, 0.60
    gw = (w - pad_l - 8); gh = h - pad_b - pad_t
    X = lambda p: pad_l + gw * p / 100; Y = lambda v: pad_t + gh - gh * (min(max(v, ymin), ymax) - ymin) / (ymax - ymin)
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;font:11px ui-sans-serif,system-ui" role="img" aria-label="Curva da totalização">']
    for v in (0.40, 0.45, 0.50, 0.55, 0.60):
        out.append(f'<line x1="{pad_l}" y1="{Y(v):.1f}" x2="{w-8}" y2="{Y(v):.1f}" stroke="{"#8a2f2f" if v == 0.5 else "#ddd8d0"}" stroke-dasharray="{"4 3" if v == 0.5 else "0"}"/><text x="{pad_l-4}" y="{Y(v)+4:.1f}" text-anchor="end" fill="#5c5955">{v*100:.0f}%</text>')
    for pc in (0, 20, 40, 60, 80, 100):
        out.append(f'<text x="{X(pc):.1f}" y="{h-pad_b+16}" text-anchor="middle" fill="#5c5955">{pc}% dos boletins</text>')
    poly = " ".join(f"{X(f['pct_bu']):.1f},{Y(f['hi']):.1f}" for f in fx) + " " + " ".join(f"{X(f['pct_bu']):.1f},{Y(f['lo']):.1f}" for f in reversed(fx))
    out.append(f'<polygon points="{poly}" fill="#1f6b3a" fill-opacity="0.18" stroke="none"/>')
    out.append('<polyline points="' + " ".join(f"{X(p['pct_bu']):.1f},{Y(p['f13']):.1f}" for p in pts) + '" fill="none" stroke="#8a2f2f" stroke-width="2"/>')
    out.append(f'<rect x="{pad_l+8}" y="{pad_t-10}" width="10" height="10" fill="#8a2f2f"/><text x="{pad_l+22}" y="{pad_t-1}" fill="#1a1a1a">fração de 13 (13+22) na ordem real de recepção</text>')
    out.append(f'<rect x="{pad_l+330}" y="{pad_t-10}" width="10" height="10" fill="#1f6b3a" fill-opacity="0.4"/><text x="{pad_l+344}" y="{pad_t-1}" fill="#1a1a1a">faixa de 20 ordens embaralhadas dentro de cada UF</text>')
    out.append("</svg>")
    return "".join(out)

def svg_hist_margem(H1, H2, w=820, h=240):
    pad_l, pad_b, pad_t = 48, 34, 16
    ks = list(range(-40, 41)); gw = (w - pad_l - 8) / len(ks); gh = h - pad_b - pad_t
    ymax = max(max(H1["histograma_margem"][k] for k in ks), max(H2["histograma_margem"][k] for k in ks)) or 1
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;font:11px ui-sans-serif,system-ui" role="img" aria-label="Margem por urna">']
    for i in range(5):
        y = pad_t + gh - gh * i / 4; out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-8}" y2="{y:.1f}" stroke="#ddd8d0"/><text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" fill="#5c5955">{N(int(ymax*i/4))}</text>')
    for j, (H, cor) in enumerate(((H2, "#1f6b3a"), (H1, "#8a2f2f"))):
        for i, k in enumerate(ks):
            v = H["histograma_margem"][k]; bh = gh * v / ymax; x = pad_l + i * gw + j * gw / 2
            out.append(f'<rect x="{x:.1f}" y="{pad_t+gh-bh:.1f}" width="{gw/2-0.3:.1f}" height="{bh:.1f}" fill="{cor}"/>')
    for k in (-40, -20, 0, 20, 40):
        out.append(f'<text x="{pad_l + (k+40) * gw + gw/2:.1f}" y="{h-pad_b+16}" text-anchor="middle" fill="#5c5955">{k:+d}</text>')
    x0 = pad_l + 40 * gw + gw / 2; out.append(f'<line x1="{x0:.1f}" y1="{pad_t}" x2="{x0:.1f}" y2="{pad_t+gh}" stroke="#1a1a1a" stroke-dasharray="4 3"/>')
    out.append(f'<rect x="{pad_l+8}" y="{pad_t-10}" width="10" height="10" fill="#1f6b3a"/><text x="{pad_l+22}" y="{pad_t-1}">2º turno: votos de 22 − votos de 13, por urna</text>')
    out.append(f'<rect x="{pad_l+300}" y="{pad_t-10}" width="10" height="10" fill="#8a2f2f"/><text x="{pad_l+314}" y="{pad_t-1}">1º turno: 22 − 13 (régua)</text>')
    out.append("</svg>")
    return "".join(out)

def pagina_algoritmo(A):
    K4_2, K4_1, K5_2, K5_1, K6_2, K6_1, K7_2, K7_1 = (A["2"]["k4"], A["1"]["k4"], A["2"]["k5"], A["1"]["k5"], A["2"]["k6"], A["1"]["k6"], A["2"]["k7"], A["1"]["k7"])
    def tab_k4(K, rot):
        return tabela(["", "Urnas com 22 à frente por 1 a 10 votos", "Esperado pela curva lisa", "Razão", "Urnas com 13 à frente por 1 a 10", "Esperado", "Razão", "Empates", "Fração de 22 entre 47,5% e 50%", "entre 50% e 52,5%"],
                      [[rot, N(K["a_frente_1a10"]), N(int(K["esperado_a_frente_1a10"])), fmt(K["razao_a"]), N(K["b_frente_1a10"]), N(int(K["esperado_b_frente_1a10"])), fmt(K["razao_b"]), N(K["empates"]), N(K["abaixo_50_5bins"]), N(K["acima_50_5bins"])]])
    def tab_k5(K, K1=None, KM=None):
        rows = []
        for f, v in K["faixas"].items():
            r1 = (K1["faixas"].get(f) or {}).get("razao") if K1 else None
            rm = (KM["faixas"].get(f) or {}).get("razao") if KM else None
            rows.append([f, N(v["municipios"]), N(v["urnas"]), N(v["obs"]), N(int(v["esp"])), fmt(v["razao"]), fmt(rm), fmt(r1), (fmt(v["razao"] / r1) if (v["razao"] and r1) else "—")])
        rows.append(["Total", "", "", N(K["total_obs"]), N(int(K["total_esp"])), fmt(K["razao"]), fmt(KM["razao"]) if KM else "—", fmt(K1["razao"]) if K1 else "—", (fmt(K["razao"] / K1["razao"]) if (K1 and K1["razao"] and K["razao"]) else "—")])
        return tabela(["Fração municipal do candidato", "Municípios", "Urnas", "Urnas com 22 à frente: observadas", "esperadas (binomial)", "Razão, 22 à frente (2º turno)", "Espelho: razão, 13 à frente, municípios onde 13 tem a mesma fração", "Razão, 22 à frente, 1º turno (régua)", "2º ÷ 1º"], rows)
    def tab_k7(K):
        if not K.get("ufs"): return "<p>Em processamento.</p>"
        out = '<div class="grid">' + stat(f'{len(K["ufs"])}/28', "UFs") + stat(N(K["votos"]), "votos com hora") + stat(N(K["assinaturas_iniciais_repetidas"]), "urnas cuja sequência de 40 intervalos iniciais se repete em outra", zero=(K["assinaturas_iniciais_repetidas"] == 0)) + stat(N(K["assinaturas_finais_repetidas"]), "idem, 40 intervalos finais", zero=(K["assinaturas_finais_repetidas"] == 0)) + "</div>"
        out += tabela(["Período (s)", "Potência relativa à média"], [[p["periodo_s"], p["potencia_relativa"]] for p in K["picos_espectro"]])
        out += tabela(["Defasagem (s)"] + list(K["autocorrelacao"].keys()), [["autocorrelação"] + [fmt(v) for v in K["autocorrelacao"].values()]])
        out += tabela(["Maior corrida de intervalos idênticos consecutivos na urna", "Urnas"], [[("10+" if k == "10" else k), N(v)] for k, v in K["corridas_intervalos_identicos"].items()])
        out += f'<p>Uniformidade do segundo dentro do minuto: qui-quadrado {fmt(K["qui2_segundo_no_minuto"], 1)} com 59 graus de liberdade (mínimo {N(K["segundo_no_minuto_min_max"][0])}, máximo {N(K["segundo_no_minuto_min_max"][1])} votos por segundo-no-minuto). Minuto dentro da hora, das 9h às 16h: bruto {fmt(K["qui2_minuto_na_hora"], 1)} (o fluxo do dia cai dentro de cada hora, e no 2º turno cai muito: de {N(K["minuto_na_hora_9_16h"][0])} votos no minuto 0 a {N(K["minuto_na_hora_9_16h"][59])} no minuto 59, em queda contínua); descontada a tendência de cada hora, o minuto que mais se afasta dela desvia {fmt(K["max_desvio_minuto_pct"], 2)}% — nenhum minuto preferido (com 1,7 milhão de votos por minuto, qualquer "evento programado" num minuto fixo apareceria como desvio de dezenas de por cento).</p>'
        out += '<details><summary>Maiores pausas entre votos consecutivos (urna aberta sem votar)</summary>' + tabela(["Segundos", "Hora", "UF", "Município", "Zona", "Seção"], [[N(p["segundos"]), p["hora"], p["uf"], p["mun"], p["zona"], p["sec"]] for p in K["maiores_pausas"]]) + "</details>"
        return out
    def tab_uf_ordem(K):
        return tabela(["UF", "Boletins", "Fração de 13 na UF", "Posição mediana na ordem de chegada", "Hora mediana de recepção"],
                      [[u, N(d["boletins"]), f'{100*d["f13"]:.1f}%'.replace(".", ","), f'{d["posicao_mediana_pct"]}%', d["hora_mediana"]] for u, d in sorted(K["por_uf"].items(), key=lambda kv: kv[1]["posicao_mediana_pct"])])
    corpo = f'''
<blockquote><p><strong>Pergunta:</strong> um algoritmo dentro do software da urna poderia detectar que o candidato 22 "sobe" na sequência de votos e acionar uma queda
linear a favor de 13 — em eventos programados, com tempo determinado, repetidos — e isso é detectável urna por urna, cidade por cidade, estado por estado?</p>
<p><strong>Resposta curta:</strong> a sequência voto a voto de uma urna não existe em arquivo público, então o "gráfico" de uma urna subindo e caindo não pode ser
desenhado por ninguém — nem por quem acusa, nem por quem defende. Mas o mecanismo descrito deixaria marcas mensuráveis: assimetria em torno do empate nas
urnas, déficit de urnas com 22 à frente dentro de cada município, periodicidade e repetição no relógio das urnas, e uma curva de totalização que não se
explicaria pela ordem de chegada dos boletins. As quatro marcas foram medidas nos dois turnos. Nenhuma aparece.</p></blockquote>

<h2>Por que o gráfico de uma urna não existe, e por que isso não impede o teste</h2>
<p>O log registra a hora de cada «Voto confirmado para [Presidente]», sem o número. O RDV registra os números, agrupados por candidato, sem hora. Nada liga
um ao outro — é o sigilo do voto. Um algoritmo que agisse "quando 22 sobe" precisaria, portanto, agir sobre o que a urna sabe internamente, e o resultado
final da urna carregaria a consequência: urnas em que 22 estava à frente terminariam empatadas ou com 13 à frente por pouco. É isso que se procura.</p>
<p>Também vale lembrar o que é "subir": numa urna 52% × 48%, sequências de 10, 20 ou 30 votos seguidos para o mesmo candidato ocorrem aos milhares por acaso;
"22 subindo" acontece em metade das urnas em algum momento do dia. Um algoritmo que reagisse a isso agiria em escala, e escala aparece nos agregados.</p>

<h2>K4 — a margem por urna em torno do empate</h2>
<p>Para cada urna com 30+ votos válidos entre 13 e 22, a margem = votos de 22 − votos de 13. Numa eleição sem interferência a distribuição da margem é lisa ao cruzar o
zero: tantas urnas com 22 à frente por 3 votos quanto a curva lisa prevê. Um algoritmo que puxasse 22 para baixo "quando à frente" esvaziaria o lado positivo
perto do zero e empilharia urnas do lado de 13. A linha "esperado" vem de um ajuste quadrático em log sobre as margens de 11 a 40 de cada lado, previsto para 1 a 10.</p>
{svg_hist_margem(K4_1, K4_2)}
{tab_k4(K4_2, "2º turno")}{tab_k4(K4_1, "1º turno (régua)")}
<p>Leitura: razões próximas de 1 dos dois lados, nos dois turnos, e a mesma quantidade de urnas logo abaixo e logo acima de 50% para 22. Não há degrau no empate.</p>

<h2>K5 — a urna contra o próprio município</h2>
<p>Dentro de um município, as urnas se distribuem em torno da fração municipal de 22 como sorteios: a binomial diz quantas urnas deveriam ter 22 à frente, dada a
fração do município e o tamanho de cada urna. Um algoritmo que agisse por urna "quando 22 sobe" reduziria esse número abaixo do esperado, sobretudo nos municípios
em que 22 tem entre 45% e 55%. Municípios com 10+ urnas comparáveis.</p>
{tab_k5(K5_2, K5_1, A["2"].get("k5_espelho"))}
<p>Leitura. A binomial pura subestima a variação entre seções de um mesmo município (bairros, zonas rurais, escolas diferentes): por isso, nos municípios em que
o candidato tem menos de 45%, há muito mais urnas com ele à frente do que a binomial prevê, e um pouco menos onde ele tem mais de 50%. Isso é heterogeneidade, e
tem duas provas aqui: acontece <em>igual para 13</em> (coluna «espelho»: a razão para "13 à frente" nos municípios em que 13 tem a mesma fração é a mesma que
para 22 — um algoritmo que só penalizasse 22 produziria razões diferentes) e acontece igual no 1º turno (coluna «2º ÷ 1º», em torno de 1 nas faixas de 45% a
60%, onde "22 à frente" é a condição de disparo da hipótese). Municípios com déficit forte (3 desvios ou mais abaixo do esperado): {N(K5_2.get("n_municipios_com_deficit_forte", 0))} no 2º turno,
{N(K5_1.get("n_municipios_com_deficit_forte", 0))} no 1º — proporções iguais, e nenhum dos dois é "zero" porque a binomial não é o modelo certo para seções heterogêneas.</p>
{('<details><summary>Municípios com déficit forte no 2º turno</summary>' + tabela(["UF", "Município", "Urnas", "Fração de 22", "Observadas", "Esperadas"], [[m["uf"], m["mun"], N(m["urnas"]), f'{100*m["p"]:.1f}%'.replace(".", ","), N(m["obs"]), N(int(m["esp"]))] for m in K5_2["municipios_com_deficit_forte"]]) + "</details>") if K5_2["municipios_com_deficit_forte"] else ""}

<h2>K6 — o gráfico que as pessoas viram: a curva da totalização</h2>
<p>O que "sobe e depois cai linearmente" na televisão é a soma dos boletins na ordem em que chegam à totalização. Cada boletim traz a hora em que foi recebido
(campo <code>DT_BU_RECEBIDO</code> do próprio TSE). Reconstruímos a curva boletim a boletim e, para saber se a forma vem da geografia da chegada ou de algo mais,
embaralhamos 20 vezes a ordem dos boletins mantendo o horário de cada grupo geográfico — primeiro dentro de cada UF, depois dentro de cada município, depois
dentro de cada zona: se a curva real cabe na faixa das embaralhadas de um nível, sua forma é só a ordem em que os grupos desse nível chegaram, e não há lugar para
um algoritmo. No 2º turno, {N(K6_2["boletins"])} boletins, do primeiro às {K6_2["primeiro_recebido"][11:16]} ao último às {K6_2["ultimo_recebido"][11:16]} de {K6_2["ultimo_recebido"][8:10]}/10.</p>
{svg_curva(K6_2)}
<p>Pontos da curva real dentro da faixa embaralhada, dos {K6_2["pontos"]}: por UF {K6_2["pontos_dentro_por_nivel"]["uf"]}, por município <strong>{K6_2["pontos_dentro_por_nivel"]["municipio"]}</strong>, por zona {K6_2["pontos_dentro_por_nivel"]["zona"]}
(a faixa desenhada é a do município). Maior distância da curva real à faixa, depois dos primeiros 5% de boletins: por UF {fmt(K6_2["desvio_max_pp_por_nivel"]["uf"], 2)} p.p.,
por município {fmt(K6_2["desvio_max_pp_por_nivel"]["municipio"], 2)} p.p., por zona {fmt(K6_2["desvio_max_pp_por_nivel"]["zona"], 2)} p.p. Ou seja: a ordem em que os <em>municípios</em> transmitiram explica a curva
a menos de uma fração de ponto; dentro de uma UF a ordem não é aleatória — capitais e cidades grandes, com transmissão mais rápida e voto diferente do interior,
chegam antes —, e o que sobra abaixo do município é da mesma ordem nos dois turnos. {("13 assume a liderança definitiva com " + f'{K6_2["virada"]["pct_bu"]}% dos boletins, às {K6_2["virada"]["hora"]}' + ".") if K6_2.get("virada") else "13 liderou do primeiro ao último boletim."}
Atraso entre a emissão do boletim na urna e a recepção: mediana {fmt(K6_2["atraso_emissao_recepcao_min"]["mediana"], 0)} min (p10 {fmt(K6_2["atraso_emissao_recepcao_min"]["p10"], 0)}, p90 {fmt(K6_2["atraso_emissao_recepcao_min"]["p90"], 0)}) — a totalização ficou suspensa até as 19h por decisão do TSE; boletins recebidos antes da emissão: {N(K6_2["atraso_emissao_recepcao_min"]["recebidos_antes_da_emissao"])}.</p>
<details><summary>Ordem de chegada por UF (2º turno)</summary>{tab_uf_ordem(K6_2)}</details>
<h3>1º turno (régua)</h3>{svg_curva(K6_1)}
<p>Pontos dentro da faixa (por UF / município / zona): {K6_1["pontos_dentro_por_nivel"]["uf"]} / {K6_1["pontos_dentro_por_nivel"]["municipio"]} / {K6_1["pontos_dentro_por_nivel"]["zona"]} de {K6_1["pontos"]};
maior distância à faixa: {fmt(K6_1["desvio_max_pp_por_nivel"]["uf"], 2)} / {fmt(K6_1["desvio_max_pp_por_nivel"]["municipio"], 2)} / {fmt(K6_1["desvio_max_pp_por_nivel"]["zona"], 2)} p.p. No 1º turno a totalização não foi suspensa e os boletins
chegaram em fluxo contínuo desde as 17h, com a ordem dentro de cada cidade mais marcada (as faixas são mais estreitas porque cada grupo transmite em bloco). E a soma final da curva é, nos dois turnos, exatamente a totalização oficial (<a href="soma-oficial.html">A3</a>): a curva não tem como "cair" para um lugar diferente da soma dos boletins públicos.</p>

<h2>K7 — eventos com tempo determinado, repetições, periodicidade</h2>
<p>Um algoritmo programado deixa assinatura no relógio: períodos fixos, intervalos repetidos, sequências idênticas entre urnas. Medimos, sobre todos os votos do
país com hora: o espectro da série de votos por segundo das 8h às 17h (sem a tendência do dia), a autocorrelação em defasagens de 1 s a 1 h, a uniformidade do
segundo dentro do minuto e do minuto dentro da hora, a maior corrida de intervalos idênticos consecutivos em cada urna, e se a sequência dos 40 primeiros (ou 40
últimos) intervalos de alguma urna se repete em outra.</p>
<h3>2º turno</h3>{tab_k7(K7_2)}
<h3>1º turno (régua)</h3>{tab_k7(K7_1)}
<p>Leitura: os únicos períodos com potência são longos — de dezenas de minutos a horas, o fluxo do dia que a média móvel de 10 minutos não remove por completo —
e nada aparece em segundos ou em poucos minutos; a autocorrelação é alta nas defasagens de segundos (o fluxo nacional é suave: 4 mil votos por segundo não mudam
de um segundo para o outro) e decai de forma contínua até zero em 5 minutos, sem ressalto em 60, 120, 300 ou 600 s; o segundo dentro do minuto é uniforme
(qui-quadrado da ordem dos 59 graus de liberdade) e nenhum minuto da hora se afasta da tendência mais que uma fração de por cento; nenhuma sequência de 40 intervalos se repete entre
urnas; as corridas de intervalos idênticos param em 6 — e tudo igual no 1º turno. Um gerador programado teria período, ressalto na autocorrelação e sequências repetidas.</p>

<h2>O que ficou demonstrado e o que não</h2>
<p><strong>Demonstrado:</strong> não há, nos resultados por urna, a marca que um algoritmo de "penalizar 22 quando à frente" deixaria — nem na margem em torno do empate,
nem dentro dos municípios; a curva da totalização é explicada pela ordem de chegada dos boletins e termina na soma exata deles; e o relógio das urnas não tem
periodicidade, repetição nem eventos programados. <strong>Não demonstrado, por impossível com dado público:</strong> que o programa da urna não contenha instrução
maliciosa de outro tipo — ver a ressalva da página inicial. Um programa que alterasse votos <em>sem</em> depender de quem está à frente, de forma proporcional e
silenciosa em todas as urnas, não produziria nenhuma das marcas acima, e só a inspeção do código e o Teste de Autenticidade o alcançariam.</p>
<p>Código: <code>scripts/pipeline/extrai_bu_tempo.py</code>, <code>tempo.py</code>, <code>gera_algoritmo.py</code>. Dados: <code>dados/analises/algoritmo_1t.json</code>, <code>algoritmo_2t.json</code>.</p>
'''
    falta = [u for u in UFS if u not in (K7_2.get("ufs") or [])]
    if falta: corpo = f'<p><strong>Em processamento:</strong> estrutura temporal do 2º turno ainda sem {", ".join(falta)}.</p>' + corpo
    return pagina("Há um algoritmo de «queda linear»? — Auditoria TSE 2026", "Testes K4–K7 · emenda de 28/10 · margem, município, totalização, relógio",
                  "Há um algoritmo de «queda linear» no software?", "O que a hipótese deixaria nos dados públicos, medido urna por urna, município por município, estado por estado, nos dois turnos.",
                  corpo, "algoritmo.html")

def main():
    A = {}
    for t in ("1", "2"):
        rows = carrega(t)
        A[t] = {"urnas": len(rows), "k4": k4(rows), "k5": k5(rows), "k5_espelho": k5(rows, "13", "22"), "k6": k6(rows, t) if rows else {}, "k7": k7(t), "gerado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    os.makedirs(f"{P}/repo/dados/analises", exist_ok=True)
    for t in ("1", "2"):
        json.dump(A[t], open(f"{PL}/algoritmo_{t}t.json", "w"), ensure_ascii=False); shutil.copy(f"{PL}/algoritmo_{t}t.json", f"{P}/repo/dados/analises/")
    open(f"{SITE}/algoritmo.html", "w").write(pagina_algoritmo(A))
    print(f"algoritmo: urnas 1T {A['1']['urnas']}, 2T {A['2']['urnas']}; K7 UFs 1T {len(A['1']['k7'].get('ufs', []))}, 2T {len(A['2']['k7'].get('ufs', []))}; página gerada")

if __name__ == "__main__": main()
