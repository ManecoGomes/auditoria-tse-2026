#!/usr/bin/env python3
"""Votos depois das 17h: para quem foram? — o que o dado permite dizer, nos dois turnos.
EMENDA DATADA de 2026-10-28 (E4 e pre-registrado; os limites de Duncan-Davis e a regressao de Goodman
sao acrescimos posteriores, de menor forca probatoria, e estao identificados como tais).

Por construcao, nenhum arquivo do TSE liga hora a candidato (o log registra o cargo; o RDV embaralha a ordem).
O que se pode fazer com boletim (votos por candidato na secao) + log (quantos votos depois das 17h na secao):

  1. LIMITES DETERMINISTICOS (Duncan & Davis, 1953): em cada secao, os votos tardios do candidato X ficam entre
     max(0, L - (N - vX)) e min(L, vX), onde L = votos depois das 17h, N = votos da secao, vX = votos de X.
     Somando as secoes, obtem-se o intervalo do qual a fracao de X entre os votos tardios NAO PODE sair.
     Sem hipotese nenhuma. Normalmente largo — e isso e informacao: mostra o quanto o dado nao diz.
  2. REGRESSAO ECOLOGICA (Goodman, 1953): fracao de X na secao ~ a + b * (fracao tardia da secao), ponderada por N.
     a + b estima a fracao de X entre os tardios SOB a hipotese de que o comportamento dos tardios e o mesmo em
     toda secao. Essa hipotese e forte e pode falhar (falacia ecologica). Reportado com esse aviso.
  3. E4 (pre-registrado): a secao e controle de si mesma. Variacao da fracao de X entre 1T e 2T na secao,
     contra a fracao tardia do 2T. Se os tardios votassem diferente do resto, as secoes com muitos tardios
     deslocariam-se de modo diferente das demais. Reportado por decil de fracao tardia e por regressao.

Entradas: {DEMO}/{UF}_secoes.csv (log, por secao: votos do dia e votos de 17h em diante; demonstra.py)
          pipeline/resultados/{t}t/votos/{UF}.csv (boletim, por secao e candidato; extrai_votos.py)
Saida:    pipeline/resultados/tardios.json  +  pipeline/resultados/tardios_secoes.csv"""
import csv, json, os, glob, collections, math, datetime
P = os.path.expanduser("~/Claude/Projetos/eleição"); R = f"{P}/pipeline/resultados"
DEMO = {"1": "/Volumes/SSD1TB/acervo-tse/auditoria/demo", "2": "/Volumes/SSD1TB/acervo-tse/auditoria/demo2t"}
UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()

def carrega(t):
    """{(uf,mun,zona,secao): {N, L17, L19, v13, v22, comp}}"""
    S = {}; ufs_log = []
    for uf in UFS:
        f = f"{DEMO[t]}/{uf}_secoes.csv"
        if not os.path.exists(f): continue
        ufs_log.append(uf)
        for r in csv.DictReader(open(f, encoding="utf-8")):
            try:
                k = (uf, int(r["municipio"]), int(r["zona"]), int(r["secao"]))
                S[k] = {"N": int(r["votos"] or 0), "L17": int(r["votos_17h_em_diante"] or 0), "L19": int(r.get("apos_19h") or 0)}
            except Exception: continue
    for uf in UFS:
        f = f"{R}/{t}t/votos/{uf}.csv"
        if not os.path.exists(f): continue
        for r in csv.DictReader(open(f, encoding="utf-8")):
            k = (uf, int(r["municipio"]), int(r["zona"]), int(r["secao"]))
            s = S.get(k)
            if s is None: continue
            s.setdefault("comp", int(r["comparecimento"] or 0))
            if r["numero"] in ("13", "22"): s["v" + r["numero"]] = s.get("v" + r["numero"], 0) + int(r["votos"] or 0)
    S = {k: s for k, s in S.items() if "v13" in s and "v22" in s and s["N"] > 0}
    return S, ufs_log

def limites(S, cand, janela):
    """Duncan-Davis: soma dos limites por secao. Usa N do log como total da secao (mesma fonte de L)."""
    lo = hi = L = 0; n = 0
    for s in S.values():
        l = s[janela]
        if l <= 0: continue
        v = s[cand]; N = s["N"]
        lo += max(0, l - (N - v)); hi += min(l, v); L += l; n += 1
    return {"secoes_com_tardios": n, "votos_tardios": L, "minimo": lo, "maximo": hi,
            "fracao_min": round(lo / L, 4) if L else None, "fracao_max": round(hi / L, 4) if L else None}

def goodman(S, cand, janela):
    """fracao de cand ~ a + b*fracao_tardia, ponderada por N. Retorna a, b, a+b, r."""
    sw = sx = sy = sxx = sxy = syy = 0.0
    for s in S.values():
        N = s["N"]; w = N; x = s[janela] / N; y = s[cand] / N
        sw += w; sx += w * x; sy += w * y; sxx += w * x * x; sxy += w * x * y; syy += w * y * y
    if sw == 0: return None
    mx = sx / sw; my = sy / sw; vx = sxx / sw - mx * mx; vy = syy / sw - my * my; cov = sxy / sw - mx * my
    if vx <= 0: return None
    b = cov / vx; a = my - b * mx; r = cov / math.sqrt(vx * vy) if vy > 0 else None
    return {"a_fracao_entre_nao_tardios": round(a, 4), "b_inclinacao": round(b, 4), "a_mais_b_fracao_entre_tardios": round(a + b, 4),
            "correlacao": round(r, 4) if r is not None else None, "media_fracao_tardia": round(mx, 4)}

def decis(S, cand, janela, chave_y):
    """tabela por faixa de fracao tardia: n secoes, votos, fracao tardia media, y medio (ponderado)"""
    faixas = [(0, 0), (0, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.35), (0.35, 0.5), (0.5, 1.01)]
    out = []
    for lo, hi in faixas:
        n = w = sy = sl = 0
        for s in S.values():
            x = s[janela] / s["N"]
            if (lo == hi == 0 and s[janela] == 0) or (hi > 0 and lo < x <= hi) or (lo == 0 and hi > 0 and 0 < x <= hi):
                if lo == hi == 0 and s[janela] != 0: continue
                if hi > 0 and not (lo < x <= hi): continue
                n += 1; w += s["N"]; sy += chave_y(s) * s["N"]; sl += s[janela]
        out.append({"faixa": "0" if lo == hi == 0 else f"{lo:.0%}–{hi:.0%}" if hi <= 1 else f">{lo:.0%}", "secoes": n, "votos": w,
                    "votos_tardios": sl, "y_medio": round(sy / w, 4) if w else None})
    return out

def main():
    out = {"gerado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "turnos": {}}
    S1, u1 = carrega("1"); S2, u2 = carrega("2")
    for t, S, ufs in (("1", S1, u1), ("2", S2, u2)):
        tot = sum(s["N"] for s in S.values()); l17 = sum(s["L17"] for s in S.values()); l19 = sum(s["L19"] for s in S.values())
        v13 = sum(s["v13"] for s in S.values()); v22 = sum(s["v22"] for s in S.values())
        bloco = {"ufs_com_log": ufs, "secoes": len(S), "votos_log": tot, "votos_17h_em_diante": l17, "pct_17h_em_diante": round(100 * l17 / tot, 3) if tot else None,
                 "votos_apos_19h": l19, "fracao_13_geral": round(v13 / tot, 4), "fracao_22_geral": round(v22 / tot, 4),
                 "limites_duncan_davis": {}, "goodman": {}, "faixas": {}}
        for jan in ("L17", "L19"):
            if sum(s[jan] for s in S.values()) == 0: continue
            bloco["limites_duncan_davis"][jan] = {c: limites(S, "v" + c, jan) for c in ("13", "22")}
            bloco["goodman"][jan] = {c: goodman(S, "v" + c, jan) for c in ("13", "22")}
            bloco["faixas"][jan] = {c: decis(S, "v" + c, jan, lambda s, c=c: s["v" + c] / s["N"]) for c in ("13", "22")}
        por_uf = collections.defaultdict(lambda: {"N": 0, "L17": 0, "L19": 0, "lo13": 0, "hi13": 0})
        for k, s in S.items():
            u = por_uf[k[0]]; u["N"] += s["N"]; u["L17"] += s["L17"]; u["L19"] += s["L19"]
            if s["L17"]: u["lo13"] += max(0, s["L17"] - (s["N"] - s["v13"])); u["hi13"] += min(s["L17"], s["v13"])
        bloco["por_uf"] = {u: {"votos": d["N"], "tardios_17h": d["L17"], "pct_tardios": round(100 * d["L17"] / d["N"], 2) if d["N"] else None,
                               "apos_19h": d["L19"], "fracao_13_tardios_min": round(d["lo13"] / d["L17"], 3) if d["L17"] else None,
                               "fracao_13_tardios_max": round(d["hi13"] / d["L17"], 3) if d["L17"] else None} for u, d in sorted(por_uf.items())}
        out["turnos"][t] = bloco
    # ---------- E4: secao contra si mesma ----------
    comuns = [k for k in S2 if k in S1 and S1[k]["N"] >= 30 and S2[k]["N"] >= 30]
    E = {}
    if comuns:
        pares = []
        for k in comuns:
            a, b = S1[k], S2[k]
            pares.append({"k": k, "N2": b["N"], "x": b["L17"] / b["N"], "x1": a["L17"] / a["N"],
                          "d13": b["v13"] / b["N"] - a["v13"] / a["N"], "d22": b["v22"] / b["N"] - a["v22"] / a["N"]})
        def reg(xs, ys, ws):
            sw = sum(ws); mx = sum(w * x for w, x in zip(ws, xs)) / sw; my = sum(w * y for w, y in zip(ws, ys)) / sw
            vx = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs)) / sw; cov = sum(w * (x - mx) * (y - my) for w, x, y in zip(ws, xs, ys)) / sw
            vy = sum(w * (y - my) ** 2 for w, y in zip(ws, ys)) / sw
            b = cov / vx if vx > 0 else None
            return {"inclinacao": round(b, 4) if b is not None else None, "intercepto": round(my - b * mx, 4) if b is not None else None,
                    "correlacao": round(cov / math.sqrt(vx * vy), 4) if vx > 0 and vy > 0 else None, "media_x": round(mx, 4), "media_y": round(my, 4)}
        ws = [p["N2"] for p in pares]; xs = [p["x"] for p in pares]
        E["secoes_comuns"] = len(pares)
        E["regressao_delta13_vs_tardios2T"] = reg(xs, [p["d13"] for p in pares], ws)
        E["regressao_delta22_vs_tardios2T"] = reg(xs, [p["d22"] for p in pares], ws)
        # controle: a mesma relacao usando os tardios do 1T (quando nao havia prorrogacao)
        E["controle_regressao_delta13_vs_tardios1T"] = reg([p["x1"] for p in pares], [p["d13"] for p in pares], ws)
        faixas = [(-1, 0), (0, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.35), (0.35, 0.5), (0.5, 1.01)]
        tab = []
        for lo, hi in faixas:
            sel = [p for p in pares if (p["x"] == 0 if lo < 0 else lo < p["x"] <= hi)]
            w = sum(p["N2"] for p in sel)
            tab.append({"faixa_tardios_2T": "0" if lo < 0 else f"{lo:.0%}–{hi:.0%}" if hi <= 1 else f">{lo:.0%}", "secoes": len(sel), "votos_2T": w,
                        "delta13_medio_pp": round(100 * sum(p["d13"] * p["N2"] for p in sel) / w, 3) if w else None,
                        "delta22_medio_pp": round(100 * sum(p["d22"] * p["N2"] for p in sel) / w, 3) if w else None})
        E["por_faixa"] = tab
        with open(f"{R}/tardios_secoes.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["uf", "municipio", "zona", "secao", "votos_1t", "tardios17h_1t", "votos_2t", "tardios17h_2t", "apos19h_2t", "v13_1t", "v22_1t", "v13_2t", "v22_2t"])
            for k in comuns:
                a, b = S1[k], S2[k]; w.writerow([*k, a["N"], a["L17"], b["N"], b["L17"], b["L19"], a["v13"], a["v22"], b["v13"], b["v22"]])
    out["E4_secao_contra_si_mesma"] = E
    out["aviso"] = ("Nenhum arquivo do TSE liga hora a candidato. Os limites de Duncan-Davis sao o unico resultado sem hipotese; "
                    "Goodman e E4 sao inferencia ecologica (correlacao de secao nao demonstra comportamento individual).")
    json.dump(out, open(f"{R}/tardios.json", "w"), ensure_ascii=False, indent=1)
    for t, b in out["turnos"].items():
        print(f"{t}T: {b['secoes']} seções ({len(b['ufs_com_log'])} UFs), {b['votos_log']:,} votos, {b['votos_17h_em_diante']:,} de 17h em diante ({b['pct_17h_em_diante']}%), após 19h {b['votos_apos_19h']:,}")
        for jan, d in b["limites_duncan_davis"].items():
            print(f"   {jan} limites 13: {d['13']['fracao_min']}–{d['13']['fracao_max']} | 22: {d['22']['fracao_min']}–{d['22']['fracao_max']} | goodman 13 a+b={b['goodman'][jan]['13']['a_mais_b_fracao_entre_tardios']} 22 a+b={b['goodman'][jan]['22']['a_mais_b_fracao_entre_tardios']}")
    if E: print("E4:", E["secoes_comuns"], "seções comuns;", E["regressao_delta13_vs_tardios2T"], "| controle 1T:", E["controle_regressao_delta13_vs_tardios1T"])
if __name__ == "__main__": main()
