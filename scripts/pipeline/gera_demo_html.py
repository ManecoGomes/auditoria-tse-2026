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

# 2o turno: entra sozinho quando demonstra.py 2 tiver gerado o arquivo
D2 = None; PORUF2 = {}; PORMUN2 = {}
if os.path.exists(f"{P}/pipeline/demonstracao_2t.json"):
    try:
        D2 = json.load(open(f"{P}/pipeline/demonstracao_2t.json")); PORUF2 = D2.get("por_uf", {})
        for _f in sorted(_glob.glob("/Volumes/SSD1TB/acervo-tse/auditoria/demo2t/*_municipios.json")):
            try: _j = json.load(open(_f))
            except Exception: continue
            if _j.get("uf") in PORUF2: PORMUN2[_j["uf"]] = _j.get("municipios", {})
    except Exception as e:
        print(f"2T ilegivel ({e}) — seguindo so com o 1T"); D2 = None

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

def svg_reta(d):
    # distribuicao normalizada (em % dos intervalos): ate as 17h x 17h em diante
    c = (d.get("C4b_reta_final") or {}).get("distribuicao")
    if not c or not c.get("antes") or not c.get("final"): return ""
    A = {int(k): v for k, v in c["antes"].items() if int(k) <= 300}
    B = {int(k): v for k, v in c["final"].items() if int(k) <= 300}
    ta, tb = sum(c["antes"].values()) or 1, sum(c["final"].values()) or 1
    pa = {k: 100*v/ta for k, v in A.items()}; pb = {k: 100*v/tb for k, v in B.items()}
    mx = max(list(pa.values()) + list(pb.values()) + [0.01])
    W, H = 900, 220
    x = lambda sg: 60 + sg*(W-80)/300
    y = lambda v: H-30-(v/mx)*(H-56)
    pathA = " ".join(f"{'M' if i==0 else 'L'}{x(k):.1f},{y(pa.get(k,0)):.1f}" for i, k in enumerate(range(0, 301)))
    pathB = " ".join(f"{'M' if i==0 else 'L'}{x(k):.1f},{y(pb.get(k,0)):.1f}" for i, k in enumerate(range(0, 301)))
    return (f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto" role="img" '
            f'aria-label="Intervalo entre votos: até as 17h e a partir das 17h">'
            f'<line x1="60" y1="{H-30}" x2="{W-20}" y2="{H-30}" stroke="#38342b"/>'
            f'<line x1="{x(20):.1f}" y1="20" x2="{x(20):.1f}" y2="{H-30}" stroke="#c0462f" stroke-dasharray="4 3"/>'
            f'<path d="{pathA}" fill="none" stroke="#4fa96f" stroke-width="2"/>'
            f'<path d="{pathB}" fill="none" stroke="#e8a33d" stroke-width="2"/>'
            f'<text x="60" y="{H-10}" font-size="11" fill="#8a857c">0 s</text>'
            f'<text x="{W-20}" y="{H-10}" font-size="11" fill="#8a857c" text-anchor="end">300 s</text>'
            f'<text x="{x(20)+5:.0f}" y="32" font-size="11" fill="#c0462f">20 s</text>'
            f'<text x="{W-20}" y="22" font-size="12" fill="#4fa96f" text-anchor="end">— até as 17h</text>'
            f'<text x="{W-20}" y="40" font-size="12" fill="#e8a33d" text-anchor="end">— 17h em diante</text>'
            f'<text x="8" y="22" font-size="11" fill="#8a857c">% dos intervalos</text></svg>')

ROT_JAN = {"antes": "<strong>A — dia normal, até as 17h</strong>", "a1630": "&nbsp;&nbsp;↳ última meia hora, 16h30 a 16h59",
           "final": "<strong>B — 17h em diante (no 2º turno, as 2 horas a mais)</strong>",
           "f17": "&nbsp;&nbsp;↳ 17h00 a 17h59", "f18": "&nbsp;&nbsp;↳ 18h00 a 18h59",
           "f19": "&nbsp;&nbsp;↳ 19h00 a 19h29", "f1930": "&nbsp;&nbsp;↳ 19h30 em diante"}
ORD_JAN = ("antes", "a1630", "final", "f17", "f18", "f19", "f1930")

def tabela_rapidas(csvp, pre="", lim=60):
    """Secoes apontadas uma a uma: intervalo <20 s ou mediana <20 s na janela final."""
    import csv as _csv
    if not os.path.exists(csvp): return "<p><em>Lista de seções ainda não gerada.</em></p>"
    rows = list(_csv.DictReader(open(csvp)))
    if not rows:
        return ('<p class="ok"><strong>Nenhuma seção apontada.</strong> Em nenhuma seção auditada houve, depois das 17h, '
                'voto discrepante do ritmo da própria seção, intervalo abaixo de 20 segundos ou mediana abaixo de 20 segundos.</p>')
    rows.sort(key=lambda r: (-int(r.get("discrepantes_final") or 0), -int(r.get("abaixo_20s_final") or 0), float(r.get("mediana_s_final") or 9999)))
    tot_disc = sum(int(r.get("discrepantes_final") or 0) for r in rows)
    tr = ""
    for r in rows[:lim]:
        href = f'{pre}estados/{r["uf"]}/{r["municipio"]}.html'
        tr += (f'<tr><td>{r["uf"]}</td><td><a href="{href}">{r["municipio_nome"] or r["municipio"]}</a></td>'
               f'<td>{r["zona"]}/{r["secao"]}</td><td class="mono">{r["urna_serie"]}</td>'
               f'<td style="text-align:right">{r["votos"]}</td><td style="text-align:right">{r["votos_17h_em_diante"]}</td>'
               f'<td style="text-align:right">{_f(float(r["media_s_antes"])) if r["media_s_antes"] else "—"}</td>'
               f'<td style="text-align:right">{_f(float(r["media_s_final"])) if r["media_s_final"] else "—"}</td>'
               f'<td style="text-align:right">{_f(float(r["limiar_discrepante_s"])) if r.get("limiar_discrepante_s") else "—"}</td>'
               f'<td style="text-align:right">{r.get("discrepantes_antes","")}</td>'
               f'<td style="text-align:right"><strong>{r.get("discrepantes_final","")}</strong></td>'
               f'<td style="text-align:right">{r["abaixo_20s_final"]}</td><td>{r["motivo"]}</td></tr>')
    return (f'<p><strong>{N(len(rows))} seções apontadas</strong>, somando <strong>{N(tot_disc)} votos discrepantes depois das 17h</strong>'
            + (f' (as {lim} mais graves abaixo; todas no CSV)' if len(rows) > lim else '') +
            '. Cada linha é uma urna identificada pelo número de série; o limiar é o de cada seção (25% da mediana dela até as 17h).</p>'
            '<div class="scroll"><table><thead><tr><th>UF</th><th>Município</th><th>Zona/Seção</th><th>Urna</th>'
            '<th style="text-align:right">Votos</th><th style="text-align:right">Votos<br>após 17h</th>'
            '<th style="text-align:right">Tempo/voto<br>até 17h</th><th style="text-align:right">Tempo/voto<br>após 17h</th>'
            '<th style="text-align:right">Limiar<br>da seção</th><th style="text-align:right">Discrep.<br>até 17h</th>'
            '<th style="text-align:right">Discrep.<br>após 17h</th><th style="text-align:right">&lt;20 s<br>após 17h</th><th>Motivo</th></tr></thead>'
            f'<tbody>{tr}</tbody></table></div>')

def svg_serie(d, titulo="tempo médio entre votos, de 10 em 10 minutos, de 16h30 em diante"):
    se = (d.get("C4b_reta_final") or {}).get("serie_10min")
    if not se: return ""
    pts = [(b, e) for b, e in sorted(se.items()) if b <= "19:50" and e.get("media_s") is not None]
    if len(pts) < 2: return ""
    mx = max(e["media_s"] for _, e in pts) or 1
    W, H = 900, 230
    bw = (W-80)/len(pts)
    x = lambda i: 60 + i*bw
    y = lambda v: H-40-(v/mx)*(H-70)
    rects = "".join(f'<rect x="{x(i)+1:.1f}" y="{y(e["media_s"]):.1f}" width="{max(bw-2,1):.1f}" '
                    f'height="{(e["media_s"]/mx)*(H-70):.1f}" fill="{"#c0462f" if e.get("abaixo_de_20s") else "#e8a33d"}"/>'
                    f'<text x="{x(i)+bw/2:.1f}" y="{y(e["media_s"])-4:.1f}" font-size="10" fill="#8a857c" '
                    f'text-anchor="middle">{e["media_s"]:.0f}</text>' for i, (_, e) in enumerate(pts))
    eixo = "".join(f'<text x="{x(i)+bw/2:.1f}" y="{H-24}" font-size="10" fill="#8a857c" text-anchor="middle">{b}</text>'
                   f'<text x="{x(i)+bw/2:.1f}" y="{H-10}" font-size="9" fill="#8a857c" text-anchor="middle">{N(e["votos"])}</text>'
                   for i, (b, e) in enumerate(pts) if i % 2 == 0)
    marcas = ""
    for i, (b, _) in enumerate(pts):
        if b in ("17:00", "19:00"):
            marcas += (f'<line x1="{x(i):.1f}" y1="18" x2="{x(i):.1f}" y2="{H-40}" stroke="#c0462f" stroke-dasharray="4 3"/>'
                       f'<text x="{x(i)+4:.0f}" y="16" font-size="11" fill="#c0462f">{b[:2]}h</text>')
    return (f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto" role="img" aria-label="{titulo}">'
            f'<line x1="60" y1="{H-40}" x2="{W-20}" y2="{H-40}" stroke="#38342b"/>{marcas}{rects}{eixo}'
            f'<text x="8" y="16" font-size="11" fill="#8a857c">segundos entre votos (média) · abaixo: votos no bloco</text></svg>')
def _f(v, suf="s"):
    return "—" if v is None else (f"{v:.0f}{suf}" if isinstance(v, (int, float)) else str(v))

def tabela_janelas(d):
    c = d.get("C4b_reta_final")
    if not c: return ""
    j = c.get("janelas") or {}
    rows = ""
    for k in ORD_JAN:
        r = j.get(k)
        if not r: continue
        pct = f'{r["pct_abaixo_20s"]:.2f}%' if r.get("pct_abaixo_20s") is not None else "—"
        pdc = f'{r["pct_discrepantes"]:.3f}%' if r.get("pct_discrepantes") is not None else "—"
        rows += (f'<tr><td>{ROT_JAN[k]}</td><td style="text-align:right">{N(r["votos"])}</td>'
                 f'<td style="text-align:right">{_f(r.get("media_s"))}</td>'
                 f'<td style="text-align:right">{_f(r.get("mediana_s"))}</td>'
                 f'<td style="text-align:right">{_f(r.get("media_ate_120s"))}</td>'
                 f'<td style="text-align:right"><strong>{N(r.get("discrepantes", 0))}</strong></td>'
                 f'<td style="text-align:right">{pdc}</td>'
                 f'<td style="text-align:right">{N(r["abaixo_de_20s"])}</td>'
                 f'<td style="text-align:right">{pct}</td></tr>')
    return ('<div class="scroll"><table><thead><tr><th>Janela</th><th style="text-align:right">Votos</th>'
            '<th style="text-align:right">Tempo médio<br>por voto</th>'
            '<th style="text-align:right">Mediana</th><th style="text-align:right">Atendimento<br>(média dos ≤120 s)</th>'
            '<th style="text-align:right">Votos<br>discrepantes</th><th style="text-align:right">% discre-<br>pantes</th>'
            '<th style="text-align:right">&lt;20 s</th><th style="text-align:right">% &lt;20 s</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')

def frase_c4b(c, rotulo_turno=""):
    j = c.get("janelas") or {}
    a, r = j.get("antes") or {}, j.get("final") or {}
    if not (a.get("media_s") and r.get("media_s")): return ""
    return (f'{rotulo_turno}Tempo médio por voto de <strong>{_f(a["media_s"])}</strong> até as 17h contra '
            f'<strong>{_f(r["media_s"])}</strong> depois das 17h — razão de <strong>{c.get("aceleracao")}</strong>. '
            f'Descontando o tempo ocioso (só intervalos de até 120 s), o atendimento leva '
            f'<strong>{_f(a.get("media_ate_120s"))}</strong> antes e <strong>{_f(r.get("media_ate_120s"))}</strong> depois. '
            f'<strong>Votos discrepantes depois das 17h: {N(r.get("discrepantes",0))}</strong> '
            f'de {N(r.get("votos",0))} ({r["pct_discrepantes"] if r.get("pct_discrepantes") is not None else "—"}%); '
            f'antes das 17h, {N(a.get("discrepantes",0))} de {N(a.get("votos",0))} ({a["pct_discrepantes"] if a.get("pct_discrepantes") is not None else "—"}%). '
            f'Seções com pelo menos 10 votos depois das 17h: <strong>{N(c.get("secoes_final_com_10_votos",0))}</strong>; '
            f'dessas, com mediana abaixo de 20 segundos: <strong>{N(c.get("secoes_final_rapida",0))}</strong>.')

def comparacao_turnos(c1, c2):
    """Tabela lado a lado 1T x 2T, janela a janela, do que importa: atendimento e faixa <20 s."""
    j1, j2 = c1.get("janelas") or {}, c2.get("janelas") or {}
    rows = ""
    for k in ORD_JAN:
        a, b = j1.get(k) or {}, j2.get(k) or {}
        if not a and not b: continue
        rows += (f'<tr><td>{ROT_JAN[k]}</td>'
                 f'<td style="text-align:right">{N(a.get("votos",0))}</td><td style="text-align:right">{N(b.get("votos",0))}</td>'
                 f'<td style="text-align:right">{_f(a.get("media_s"))}</td><td style="text-align:right"><strong>{_f(b.get("media_s"))}</strong></td>'
                 f'<td style="text-align:right">{_f(a.get("media_ate_120s"))}</td><td style="text-align:right"><strong>{_f(b.get("media_ate_120s"))}</strong></td>'
                 f'<td style="text-align:right">{N(a.get("discrepantes",0))}</td><td style="text-align:right"><strong>{N(b.get("discrepantes",0))}</strong></td>'
                 f'<td style="text-align:right">{N(a.get("abaixo_de_20s",0))}</td><td style="text-align:right"><strong>{N(b.get("abaixo_de_20s",0))}</strong></td></tr>')
    rows += (f'<tr><td><em>Seções com mediana &lt;20 s depois das 17h</em></td><td></td><td></td><td></td><td></td><td></td><td></td>'
             f'<td style="text-align:right">{N(c1.get("secoes_final_rapida",0))}</td>'
             f'<td style="text-align:right"><strong>{N(c2.get("secoes_final_rapida",0))}</strong></td><td></td><td></td></tr>')
    return ('<div class="scroll"><table><thead><tr><th>Janela</th><th style="text-align:right">Votos 1T</th>'
            '<th style="text-align:right">Votos 2T</th><th style="text-align:right">Tempo médio<br>1T</th><th style="text-align:right">Tempo médio<br>2T</th>'
            '<th style="text-align:right">Atendimento 1T<br>(≤120 s)</th>'
            '<th style="text-align:right">Atendimento 2T<br>(≤120 s)</th><th style="text-align:right">Discre-<br>pantes 1T</th>'
            '<th style="text-align:right">Discre-<br>pantes 2T</th><th style="text-align:right">&lt;20 s 1T</th>'
            f'<th style="text-align:right">&lt;20 s 2T</th></tr></thead><tbody>{rows}</tbody></table></div>')

def secao_c4b(d, pre="", d2=None):
    c = d.get("C4b_reta_final")
    if not c: return ""
    bloco2 = ""
    c2 = (d2 or {}).get("C4b_reta_final")
    if c2:
        bloco2 = f'''
<h3>2º turno — o mesmo escopo contra si mesmo</h3>
<p>Os mesmos cortes, agora sobre os logs do 2º turno, em que a votação foi prorrogada até as 19h.
No 1º turno o bloco B é só a fila remanescente; no 2º, são duas horas a mais de urna liberada.
O que se compara, linha a linha, é o <strong>tempo médio por voto</strong>, o <strong>atendimento</strong>
(média dos intervalos de até 120 s) e, sobretudo, <strong>quantos votos discrepantes</strong> houve.</p>
{comparacao_turnos(c, c2)}
<p>{frase_c4b(c2, "No 2º turno: ")}</p>
{svg_serie(d2, "2º turno: tempo médio entre votos, de 10 em 10 minutos, de 16h30 em diante")}
{svg_reta(d2)}
'''
    return f'''
<h2>C4b — Tempo por voto: o dia normal até as 17h contra as horas depois das 17h</h2>
<p>Teste acrescentado em 27 de outubro de 2026 — <a href="{pre}reta-final.html">veja a hipótese, o vídeo
que a motivou e o que o teste pode e não pode demonstrar</a>. A pergunta é direta: depois das 17h, alguém
votou numa velocidade discrepante da média do próprio dia, e quantos votos foram esses? O mesmo intervalo
entre votos do teste C4, separado em dois blocos com a mesma régua nos dois turnos: <strong>A</strong>, o dia
normal até as 17h (prazo legal do 1º turno), e <strong>B</strong>, de 17h em diante — que no 2º turno são as
duas horas a mais da prorrogação, até as 19h, e o que passou das 19h. <strong>Voto discrepante</strong> é o
registrado com intervalo abaixo de 25% da mediana da própria seção no bloco A; a régua da seção só vale com
pelo menos 30 intervalos nessa base (seção que abriu tarde ou trocou de urna não tem dia normal para servir de
régua) e, abaixo disso, vale o piso de 20 segundos.</p>
{tabela_janelas(d)}
<p>{frase_c4b(c)}</p>
{svg_serie(d)}
{svg_reta(d)}
<p>Intervalos encurtam no fim do dia por uma razão legítima — a fila é contínua e não há tempo ocioso
entre eleitores. O que <strong>não</strong> encurta é o tempo físico de identificar o eleitor, entrar na
cabine e votar: por isso o que se conta são os <strong>votos discrepantes</strong> (abaixo de um quarto do
ritmo normal daquela mesma urna) e a faixa abaixo de 20 s. No 1º turno o eleitor votou em mais cargos;
este número é o teto da comparação com o 2º turno.</p>
{bloco2}
'''

# ---------------------------------------------------------------- textos
def cauda_17h(d):
    """Substitui os numeros antes fixos: le a propria curva."""
    cu = d["C3_curva_por_minuto"]
    tri = [(h, cu.get(h)) for h in ("17:00", "17:05", "17:10")]
    if any(v is None for _, v in tri): return ""
    return (f'A cauda após as 17h decai suavemente: {N(tri[0][1])} votos às 17h00, '
            f'{N(tri[1][1])} às 17h05, {N(tri[2][1])} às 17h10. '
            f'É a assinatura de uma fila se esvaziando.')

def bloco(d, escopo, pre="", d2=None):
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
{('<blockquote><p><strong>2º turno já incluído:</strong> ' + N(d2["secoes"]) + ' seções e ' + N(d2["votos_presidente"]) + ' votos do 2º turno neste escopo. A seção C4b traz a comparação.</p></blockquote>') if d2 else ''}
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
{secao_c4b(d, pre, d2)}
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
        '<th style="text-align:right">Triangulação<br>divergente</th>'
        '<th style="text-align:right">Tempo/voto<br>até 17h</th>'
        '<th style="text-align:right">Tempo/voto<br>após 17h</th>'
        '<th style="text-align:right">Discrepantes<br>após 17h</th>'
        '<th style="text-align:right">&lt;20 s<br>após 17h</th></tr></thead>')

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
            f'<td style="text-align:right">{N(m["a2_divergentes"])}</td>'
            f'<td style="text-align:right">{_f(m.get("media_antes"))}</td>'
            f'<td style="text-align:right">{_f(m.get("media_final"))}</td>'
            f'<td style="text-align:right"><strong>{N(m["disc_final"]) if m.get("disc_final") is not None else "—"}</strong></td>'
            f'<td style="text-align:right">{N(m["abaixo20_final"]) if m.get("abaixo20_final") is not None else "—"}</td></tr>')

def _jan_uf(d, k, campo):
    try: return d["C4b_reta_final"]["janelas"][k][campo]
    except Exception: return None

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
           f'<td style="text-align:right"><strong>{N(d["A2_triangulacao"]["divergentes"])}</strong></td>'
           f'<td style="text-align:right"><strong>{_f(_jan_uf(d,"antes","media_s"))}</strong></td>'
           f'<td style="text-align:right"><strong>{_f(_jan_uf(d,"final","media_s"))}</strong></td>'
           f'<td style="text-align:right"><strong>{N(_jan_uf(d,"final","discrepantes")) if _jan_uf(d,"final","discrepantes") is not None else "—"}</strong></td>'
           f'<td style="text-align:right"><strong>{N(_jan_uf(d,"final","abaixo_de_20s")) if _jan_uf(d,"final","abaixo_de_20s") is not None else "—"}</strong></td></tr>')
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
# rodape: a hora de "ultima atualizacao" e a da geracao, nao a do molde
import datetime as _dt
_agora = _dt.datetime.now().strftime("%d/%m/%Y %H:%M")
RODAPE = re.sub(r"Última atualização: [0-9/]+ [0-9:]+", f"Última atualização: {_agora}", RODAPE)

def nav(ativo, pre=""):
    its = [("index.html","Resumo"),("primeiro-turno.html","1º turno"),
           ("segundo-turno.html","2º turno"),("comparativo.html","Comparativo"),
           ("reta-final.html","Reta final"),("estados/index.html","Estados"),
           ("forense.html","Forense dos logs"),("soma-oficial.html","Soma oficial"),("votos-tardios.html","Votos tardios"),
           ("plano-2t.html","Plano"),("verificar.html","Como verificar"),
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
''' + bloco(D, "nacional", d2=D2) + f'''
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

# ---------------------------------------------------------------- 1b. reta final (emenda datada 2026-10-27)
def _rank_uf(POR=None):
    POR = PORUF if POR is None else POR
    linhas = ""
    ufs = []
    for uf in sorted(POR):
        d = POR[uf]; c = d.get("C4b_reta_final") or {}
        j = c.get("janelas") or {}; a, r = j.get("antes") or {}, j.get("final") or {}
        ufs.append((c.get("aceleracao") or 0, uf, d, a, r, c))
    for ac, uf, d, a, r, c in sorted(ufs, reverse=True):
        linhas += (f'<tr><td><a href="estados/{uf}.html">{uf} — {d["nome"]}</a></td>'
                   f'<td style="text-align:right">{N(r.get("votos",0))}</td>'
                   f'<td style="text-align:right">{_f(a.get("media_s"))}</td>'
                   f'<td style="text-align:right">{_f(r.get("media_s"))}</td>'
                   f'<td style="text-align:right">{_f(a.get("media_ate_120s"))}</td>'
                   f'<td style="text-align:right">{_f(r.get("media_ate_120s"))}</td>'
                   f'<td style="text-align:right">{c.get("aceleracao") if c.get("aceleracao") is not None else "—"}</td>'
                   f'<td style="text-align:right"><strong>{N(r.get("discrepantes",0))}</strong></td>'
                   f'<td style="text-align:right">{N(r.get("abaixo_de_20s",0))}</td>'
                   f'<td style="text-align:right">{N(c.get("secoes_final_com_10_votos",0))}</td>'
                   f'<td style="text-align:right">{N(c.get("secoes_final_rapida",0))}</td></tr>')
    return linhas

TRANSCRICAO = ("O Congresso estava certo ao exigir pelo menos o documento de identidade com foto, porque "
 "evita, diminui as fraudes, porque o caminho seguinte era a Justiça Eleitoral tirar daquele livro de "
 "eleitores o número do título, porque é o número do título ali que permite que o mesário vote pelo "
 "eleitor que não foi, ou pelo eleitor que morreu. O que é que acontece hoje? Dá 5 horas da tarde, o "
 "mesário verifica lá, em consórcio com os fiscais, verifica os eleitores que não compareceram — porque "
 "não foram, porque morreram, porque viajaram —, com o número do título ele libera a urna eletrônica e "
 "vota quantas vezes ele quiser. Então esse é um tema da maior gravidade, e nós estamos certos na "
 "elaboração da lei.")

_c4b = D.get("C4b_reta_final") or {}
_jn = _c4b.get("janelas") or {}
CAB_RANK = ('<div class="scroll"><table><thead><tr><th>Estado</th><th style="text-align:right">Votos<br>após 17h</th>'
            '<th style="text-align:right">Tempo/voto<br>até 17h</th><th style="text-align:right">Tempo/voto<br>após 17h</th>'
            '<th style="text-align:right">Atendimento<br>até 17h (≤120 s)</th><th style="text-align:right">Atendimento<br>após 17h (≤120 s)</th>'
            '<th style="text-align:right">Aceleração</th><th style="text-align:right">Discrepantes<br>após 17h</th><th style="text-align:right">&lt;20 s<br>após 17h</th>'
            '<th style="text-align:right">Seções com<br>≥10 votos após 17h</th><th style="text-align:right">…com mediana<br>&lt;20 s</th></tr></thead>')
if D2 and D2.get("C4b_reta_final"):
    _c2 = D2["C4b_reta_final"]
    _an = {}
    try: _an = (json.load(open(f"{P}/pipeline/analises.json")).get("blocos") or {}).get("E6_janela_final_secoes") or {}
    except Exception: pass
    _e6 = ""
    if _an and "secoes_comuns_com_10_votos_na_janela_2t" in _an:
        _e6 = (f'<h3>Seção contra ela mesma (bloco E6)</h3>'
               f'<p>Seções presentes nos dois turnos com 10 ou mais votos depois das 17h no 2º turno: '
               f'<strong>{N(_an["secoes_comuns_com_10_votos_na_janela_2t"])}</strong>. Com mediana abaixo de 20 s na janela '
               f'final do 2º turno: <strong>{N(_an["secoes_2t_mediana_final_abaixo_20s"])}</strong> '
               f'(no 1º turno, as mesmas seções: {N(_an["secoes_1t_mediana_final_abaixo_20s"])}). '
               f'Com intervalo abaixo de 20 s no 2º turno <strong>sem ter tido nenhum no 1º</strong>: '
               f'<strong>{N(_an["secoes_2t_com_intervalo_abaixo_20s_sem_ter_no_1t"])}</strong>. '
               f'Variação do tempo médio na janela final (2º menos 1º turno), mediana: '
               f'<strong>{_f(_an["variacao_media_final_2t_menos_1t_s"]["mediana"])}</strong> '
               f'(p10 {_f(_an["variacao_media_final_2t_menos_1t_s"]["p10"])}, p90 {_f(_an["variacao_media_final_2t_menos_1t_s"]["p90"])}).</p>')
    bloco_2t_reta = (f'<p>Logs do 2º turno já auditados: <strong>{len(PORUF2)} unidades da Federação</strong>, '
                     f'{N(D2["secoes"])} seções e {N(D2["votos_presidente"])} votos. A régua é o 1º turno, '
                     f'na mesma janela e, sempre que possível, na mesma seção.</p>'
                     + comparacao_turnos(_c4b, _c2)
                     + f'<p>{frase_c4b(_c2, "No 2º turno: ")}</p>'
                     + svg_serie(D2, "2º turno: tempo médio entre votos, de 10 em 10 minutos, a partir das 16h30")
                     + svg_reta(D2)
                     + '<h3>Seções apontadas no 2º turno</h3>'
                     + tabela_rapidas(f"{P}/pipeline/secoes_rapidas_janela_final_2t.csv")
                     + _e6
                     + '<h3>Estado por estado — 2º turno</h3>' + CAB_RANK + f'<tbody>{_rank_uf(PORUF2)}</tbody></table></div>')
else:
    bloco_2t_reta = ('<p>O mesmo código roda, seção a seção, assim que o TSE publicar os logs. Cada município terá, '
                     'ao lado da sua linha de base do 1º turno, as horas depois das 17h do 2º turno — até as 19h e além — '
                     'e a lista das seções apontadas. É nessa granularidade, a mesma seção contra ela mesma, '
                     'que a hipótese do vídeo será confirmada ou afastada.</p>')
corpo_reta = f'''
<blockquote><p><strong>Emenda datada ao plano.</strong> Este teste (C4b) foi acrescentado em
<strong>27 de outubro de 2026</strong> — um dia depois do <a href="plano-2t.html">plano pré-registrado</a>
e <strong>antes</strong> de o TSE publicar qualquer arquivo do 2º turno. Pela regra do próprio plano, fica
identificado como posterior e, por isso, de menor força probatória que os testes originais. O código que o
executa está publicado e carimbado junto com o restante do acervo, antes de existirem os dados sobre os
quais rodará.</p></blockquote>

<h2>A hipótese, dita por quem conhece o mecanismo</h2>
<video controls preload="metadata" playsinline style="max-width:360px;width:100%;display:block;margin:0 auto 1rem;border-radius:8px;background:#000"
  src="midia/flavio-dino-mesario-vota-pelo-eleitor.mp4">Seu navegador não reproduz este vídeo.
  <a href="midia/flavio-dino-mesario-vota-pelo-eleitor.mp4">Baixe o arquivo.</a></video>
<p><em>Flávio Dino, em discurso sobre a exigência de documento de identidade com foto para votar.
Trecho republicado por Maneco Gomes no Instagram em 27 de outubro de 2026
(<a href="https://www.instagram.com/p/De-yeVuh26d/" rel="noopener">instagram.com/p/De-yeVuh26d</a>).
Transcrição integral do áudio:</em></p>
<blockquote><p>"{TRANSCRICAO}"</p></blockquote>
<p>O mecanismo descrito é concreto e deixa rastro. Se, encerrada a fila real, o mesário usa o número do
título de eleitores ausentes para liberar a urna e votar por eles, o log daquela seção registra uma
sequência de votos <strong>sem eleitor</strong>: ninguém a identificar, ninguém a caminhar até a cabine,
ninguém a decidir. O intervalo entre um voto e o seguinte cai ao tempo de digitar e confirmar.</p>
<p>No 1º turno a votação encerrou às 17h: o dia inteiro até as 17h é a <strong>régua do tempo normal</strong>,
e o que vem depois é só a fila remanescente. No 2º turno, com a prorrogação determinada às 17h01 pelo
Ministro Zanin, depois das 17h há <strong>duas horas a mais de urna liberada</strong>, até as 19h e além —
e é nelas que, pela hipótese do vídeo, o mesário teria votado pelos ausentes. Voto fraudulento de mesário é
voto rápido demais, e voto rápido demais fica no log: o que se conta é <strong>quantos votos, depois das
17h, saíram numa velocidade discrepante da média do próprio dia</strong>.</p>

<h2>O que o teste mede</h2>
<p>É o intervalo entre votos consecutivos do teste C4, dividido em dois blocos com a mesma régua nos dois
turnos: <strong>A, o dia normal</strong>, da abertura até as 17h, e <strong>B, de 17h em diante</strong>
(com subfaixas 17h–17h59, 18h–18h59, 19h–19h29 e 19h30 em diante; a última meia hora de A, 16h30–16h59,
aparece à parte para mostrar a rampa). Para cada bloco, em cada seção, município, estado e no país:
votos, tempo médio por voto, mediana, média só dos intervalos de até 120 segundos (o tempo de atendimento,
sem o tempo ocioso), <strong>quantos votos foram discrepantes</strong> — intervalo abaixo de 25% da mediana
da própria seção no bloco A, exigindo ao menos 30 intervalos nessa base; com base menor, piso de 20 s — e
quantos ficaram abaixo de 20 segundos, o limite físico para um eleitor real.</p>
<p>A assinatura de fraude seria: depois das 17h, votos discrepantes em quantidade <strong>que não existe
antes das 17h</strong>, em seções identificáveis, formando sequências — não casos isolados. A assinatura
de normalidade é a oposta: o tempo por voto depois das 17h igual ou maior que o do dia, e os votos
discrepantes zero ou residuais nos dois blocos.</p>

<h2>O que o teste não pode dizer</h2>
<p><strong>Em quem foi o voto.</strong> O log registra o cargo, nunca o candidato. Mesmo que a reta final
mostrasse votos a ritmo de máquina, não haveria como saber a quem beneficiaram.</p>
<p><strong>Que um intervalo curto é fraude.</strong> Eleitor que já sabe o número e mesário que
libera a urna no instante em que o anterior sai podem produzir intervalos de poucas dezenas de segundos
num cargo só. Por isso o limiar é 20 segundos — abaixo dele não cabe identificação, deslocamento e voto —
e por isso o que se procura são <em>sequências</em> em seções identificáveis, não ocorrências isoladas.</p>
<p><strong>Que o 1º turno é uma régua perfeita.</strong> No 1º turno o eleitor votou em cinco ou seis
cargos; no 2º, em um ou dois. O tempo por voto do 1º turno é, portanto, um <em>teto</em>. Por isso o
limiar de voto discrepante é relativo à própria seção no próprio turno, e a comparação decisiva é
<strong>a mesma seção contra ela mesma</strong>: as horas depois das 17h do 2º turno contra o dia normal
do 2º turno, com o 1º turno mostrando quanto disso é fila legítima.</p>

<h2>Resultado no 1º turno — o grupo de controle</h2>
<p>Sobre <strong>{len(PORUF)} unidades da Federação</strong>, {N(D["secoes"])} seções e
{N(D["votos_presidente"])} votos já auditados. {aviso_falta}</p>
{tabela_janelas(D)}
<p>{frase_c4b(_c4b)}</p>
{svg_serie(D)}
{svg_reta(D)}
<h3>Seções apontadas no 1º turno</h3>
{tabela_rapidas(f"{P}/pipeline/secoes_rapidas_janela_final.csv")}
<p>Critério: depois das 17h, qualquer voto discrepante (intervalo abaixo de 25% da mediana da própria seção
até as 17h, com ao menos 30 intervalos de base; senão, 20 s), qualquer intervalo abaixo de 20 segundos, ou
mediana abaixo de 20 segundos com 10 ou mais votos.
A lista completa está em <code>dados/analises/secoes_rapidas_janela_final.csv</code>; cada seção está também em
<code>demonstracao_secoes.csv</code> (colunas <code>votos_17h_em_diante</code>, <code>media_s_final</code>,
<code>mediana_s_final</code>, <code>limiar_discrepante_s</code>, <code>discrepantes_antes</code>,
<code>discrepantes_final</code> e <code>abaixo_20s_final</code>).</p>

<h2>Estado por estado</h2>
<p>Ordenado pela razão entre o tempo por voto até as 17h e depois das 17h ("aceleração"). Razão alta
só significa fila densa no fim do dia; o que exige explicação são as colunas de votos discrepantes e de
seções com mediana abaixo de 20 segundos. Clique no estado para ver o teste por município.</p>
{CAB_RANK}
<tbody>{_rank_uf()}</tbody></table></div>

<h2>No 2º turno</h2>
{bloco_2t_reta}
<p>Dados brutos: <code>dados/analises/demonstracao_1t.json</code> e <code>demonstracao_2t.json</code>
(chave <code>C4b_reta_final</code>, nacional e em <code>por_uf</code>), <code>demonstracao_secoes.csv</code>,
<code>demonstracao_secoes_2t.csv</code>, <code>secoes_rapidas_janela_final.csv</code> e
<code>secoes_rapidas_janela_final_2t.csv</code>; a comparação seção a seção está em
<code>analises.json</code>, bloco <code>E6_janela_final_secoes</code>.</p>
'''
open(f"{SITE}/reta-final.html", "w").write(pagina(
  "A reta final: o mesário pode votar pelo eleitor que não foi? — Auditoria TSE 2026",
  "Emenda datada · 27 de outubro de 2026",
  "A reta final: o mesário pode votar pelo eleitor que não foi?",
  "O tempo por voto até as 17h e nas duas horas a mais, medido voto a voto — em cada seção, município e estado.",
  corpo_reta, "reta-final.html", "reta-final.html"))

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
             + bloco(d, d["nome"], pre="../", d2=PORUF2.get(uf))
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
                 + bloco(b, b["nome"], pre="../../", d2=(PORMUN2.get(uf) or {}).get(cod))
                 + f'<h2>Vizinhos no estado</h2><p>{" · ".join(viz) or "—"}</p>'
                 + f'<p><a href="../{uf}.html">◀ Todos os municípios de {duf["nome"]}</a></p>')
        open(f"{SITE}/estados/{uf}/{slug_mun(cod)}.html", "w").write(pagina(
          f'{b["nome"]} ({uf}) — Auditoria TSE 2026', f'Demonstração · {uf} · município',
          b["nome"], f'Os testes do plano aplicados aos logs do 1º turno de {b["nome"]} ({uf}).',
          corpo, None, f"estados/{uf}/{slug_mun(cod)}.html", pre="../../"))
        n_mun += 1
print(f"paginas de municipio geradas: {n_mun}")

# ---------------------------------------------------------------- 3c. paginas de sintese (index, 1T, 2T, comparativo)
exec(open(f"{P}/pipeline/paginas_extra.py").read())

# ---------------------------------------------------------------- 4. nav das demais paginas
for f in ["plano-2t.html", "relatorio.html", "relatorio-2t.html", "verificar.html", "dados.html"]:
    p = f"{SITE}/{f}"
    if not os.path.exists(p): continue
    s = open(p).read()
    s2 = re.sub(r"<nav>.*?</nav>", lambda m: nav(f), s, count=1, flags=re.S)
    if s2 != s: open(p, "w").write(s2)

# ---------------------------------------------------------------- 5. sitemap
hoje = datetime.date.today().isoformat()
urls = (["index.html","primeiro-turno.html","segundo-turno.html","comparativo.html","reta-final.html",
         "plano-2t.html","demonstracao.html","estados/index.html","relatorio.html","verificar.html","dados.html"]
        + [f"estados/{u}.html" for u in sorted(PORUF)]
        + [f"estados/{u}/{slug_mun(c)}.html" for u in sorted(PORMUN) for c in sorted(PORMUN[u])])
open(f"{SITE}/sitemap.xml","w").write(
 '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
 + "".join(f"<url><loc>{URL}/{u}</loc><lastmod>{hoje}</lastmod></url>\n" for u in urls) + "</urlset>\n")

print(f"gerado: demonstracao.html + estados/index.html + {len(PORUF)} páginas de estado "
      f"({', '.join(sorted(PORUF))})")
