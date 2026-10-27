# 📋 Relatório: por que o TSE ainda não publicou o pacote do 2º turno de 2026 — e onde os dados já estão
Gerado em: 2026-10-27 (revisado após Phase Gate; aprovado na 2ª rodada) | Sub-tópicos: 3 | Fontes avaliadas: 16 | Fatos-chave verificados: 6/8

## Resumo Executivo
Não existe justificativa oficial do TSE para o pacote consolidado por UF do 2º turno (boletins `bweb_2t_*` e logs `bu_imgbu_logjez_rdv_vscmr_2026_2t_*`) não estar no portal de dados abertos em 27/10/2026 — porque não existe prazo normativo para ele. O calendário (Res. TSE 23.760/2026) obriga a divulgar boletins "à medida que forem recebidos" no dia da eleição e abre em 26/10 o pedido de logs e RDV pelas entidades fiscalizadoras, com 5 dias úteis para atendimento (Res. 23.673/2021, art. 49). Em 2022 e 2024 o pacote saiu 2 a 3 dias depois do turno (datas conferidas no próprio CKAN do TSE). O ponto decisivo, verificado por download direto: **os mesmos arquivos estão públicos, seção por seção, no Portal Resultados desde a noite de 25/10** (pleito 3221), e foi por esse caminho que a auditoria passou a coletar. Confiança: ALTA para os fatos normativos e de disponibilidade (verificados em fonte primária); MÉDIA para a cronologia minuto a minuto do dia 25 (fontes divergem em até 6 minutos).

## Sub-tópico 1 — O número oficial de votos após as 17h
- TSE (27/10, 15h21): **34.393** votos depois das 17h — 32.399 entre 17h e 18h, 1.981 entre 18h e 19h, 13 após 19h; 497.333 seções no universo; 24.268 abertas depois das 17h10; 6.766 encerradas após 19h; nas 24.268 abertas, 8.673 votos desde as 17h.
- g1 (26/10): 35.521 votos em 497.897 seções na primeira versão (replicada pelo Valor, mesmo grupo); o g1 corrigiu para **34.330**. O número de 34,3 mil foi reportado também por Folha de S.Paulo e Metrópoles (grupos distintos). A diferença de 63 votos entre 34.393 (TSE) e 34.330 (g1) é **inferência aritmética deste relatório**, não um dado publicado.
- O TSE não publicou base por seção, eventos de log contados, tratamento de fuso ou deduplicação; a notícia é um levantamento, não uma nota técnica.
- TRE-GO publicou número próprio (83 votos após 17h10), compatível com o recorte nacional.
Fatos verificados: 34.393 e sua decomposição — ≥2 fontes independentes (tse.jus.br; cnnbrasil.com.br; folha.uol.com.br); 34,3 mil como número corrigido — ≥2 (g1.globo.com; folha.uol.com.br; metropoles.com); diferença de 63 — inferência deste relatório, não publicada.
Fontes principais: TSE (CRAAP 94), Folha (82), g1 (82), CNN Brasil (78), Metrópoles (72), TRE-GO (88).
Nota de independência: g1, O Globo e Valor pertencem ao mesmo grupo editorial e contam como UMA fonte quando citados em par.

## Sub-tópico 2 — Cronologia da prorrogação e da paralisação
| Hora (Brasília, 25/10) | Fato | Fontes |
|---|---|---|
| 13h22 | Coligação de Lula pede ao TSE prorrogação (transporte, BA) | DGABC; UOL/Estadão |
| 15h27 | Campanha de Flávio pede prorrogação por chuvas (SP, PR, SC) | DGABC (fonte única, Tier C — horário não confirmado) |
| 16h12 | Presidente do TSE pede informações aos TREs em 30 min, sem decidir | UOL/Estadão |
| 16h29 | STF acionado; Zanin sorteado relator | Exame; 163notícias |
| 16h57–17h03 | Zanin prorroga até 19h; divergência de minuto entre fontes | STF (notícia 18h28); UOL; Conjur |
| 17h49 | Ofício-Circular GAB-PRES 354/2026: só seções "que ainda estiverem abertas" ficam até 19h | PDF do ofício (Poder360); Plural |
| 18h34–18h44 | Comunicados do TRE-SP (18h34) e TRE-RJ (18h35): seções cientificadas, votos já encerrados totalizados integralmente; nota oficial do TSE (18h44): BUs, totalização e divulgação retomados após 19h | tre-sp.jus.br; tre-rj.jus.br; tse.jus.br (três órgãos distintos) |
| 26/10 00h18 | Balanço oficial: Lula 64.256.232 (51,79%) × Flávio 59.826.041 (48,21%); TSE fala em "acúmulo de arquivos à espera de processamento" | tse.jus.br |
| 26/10 noite | PL reconhece o resultado; campanha fala em AIJE, não anulação | g1; Valor; O Globo |
Fatos verificados: restrição a urnas não fechadas — ≥2 (tre-sp.jus.br, tre-rj.jus.br, noticias.stf.jus.br); ofício 354 às 17h49 — ≥2 (static.poder360.com.br, plural.jor.br); suspensão até 19h — ≥2 órgãos oficiais (TSE, TRE-SP, TRE-RJ); "17h06 com 0,25% apurado" — **fonte única de fato** (Valor e O Globo são o mesmo grupo), sem documento oficial.
Fontes principais: STF notícias (92), TSE (94), TRE-SP (90), Ofício PDF (95), g1 (82), Valor (80).

## Sub-tópico 3 — Prazo do pacote e o caminho alternativo
- Portal CKAN do TSE, conferido diretamente em 27/10: 2022 (2T em 30/10) — boletins criados em 01/11, logs em 02/11; 2024 (2T em 27/10) — logs em 29/10, boletins em 30/10. Os recursos do 2T entram nos mesmos datasets do 1T, com `_2t_` no nome.
- Nenhum comunicado do TSE com data para o pacote de 2026 foi localizado; nenhum pedido partidário identificado por protocolo.
- Portal Resultados, documentação técnica do TSE: pleitos 3220 (1T) e 3221 (2T); por seção, `aux.json` com hash, data/hora de recebimento e status, e os quatro arquivos (bu.dat, log.jez, rdv.dat, vota.vsc); disponibilização "de acordo com a sincronização da CDN"; 404 em série pode bloquear o IP.
- Verificação reproduzível (27/10/2026, 17h40–18h10 BRT, de IP residencial, UA "Mozilla/5.0 auditoria-tse-2026"):
  - índice de seções: `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/config/ac/ac-p003221-cs.json` (HTTP 200, 146.065 bytes, `dg/hg` 25/10/2026 23:22:31, 2.411 seções);
  - seção 10, zona 9, Rio Branco: `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados/ac/01007/0009/0010/p003221-ac-m01007-z0009-s0010-aux.json` (HTTP 200; `st` "Totalizada"; `hashes[0].dr/hr` 25/10/2026 19:31:12; quatro arquivos listados);
  - log: `.../0010/72466d73314c4f7546324c764568444c51644d6a68343469354734313547764f39514830396b686635676b3d/o03221ac0100700090010-log.jez` (HTTP 200, 130.734 bytes; ZIP com `logd.dat`, 7.219 linhas).
  - Replicação em escala: até 18h10 de 27/10 foram coletadas **20.708 seções totalizadas** de AC, AP, RO, RR, SE e TO (registro por seção, com hash e `dr/hr`, em `registro_secoes_UF.json` no repositório). Os recebimentos vão de 25/10 17h05 a 25/10 21h17 — ou seja, os arquivos estavam no Portal na própria noite da eleição.
  - **Log cumulativo**: confirmado nas 1.519 seções de RR, não num caso isolado — sem filtro por data o total de votos de RR no 2T saía em 635.641 (1T: 332.575; 2T com filtro: 308.239) e 1.494 seções apareciam com "voto após o lacre" do 1T. Qualquer análise desses logs precisa filtrar pela data do pleito. (332.575 + 308.239 = 640.814 ≠ 635.641: a parcela "1º turno" dentro do log do 2º turno é a da urna usada no 2º turno, que nem sempre foi a mesma do 1º — trocas por contingência —, por isso não reproduz o total oficial do 1º; não é contradição.)
- Fonte externa que usa o mesmo caminho: projeto `urnas-tardias` (GitHub, apolinario) documenta a mesma estrutura de URL do pleito 3221 e coletou os logs do 2T a partir de 25/10; o levantamento do g1 (26/10) também foi feito a partir dos logs por seção, o que confirma a disponibilidade antes do pacote.
Fatos verificados: datas de 2022/2024 — fonte primária única (CKAN; timestamps `created` dos recursos, conferíveis por qualquer pessoa via API `package_show`); códigos de pleito — ≥2 (tse.jus.br informações técnicas; github urnas-tardias); disponibilidade por seção do 2T antes do pacote — verificação reproduzível acima + 2 fontes externas (urnas-tardias; levantamento do g1 em 26/10); log cumulativo — verificado em 1.519 seções.
Fontes principais: dadosabertos.tse.jus.br (96), tse.jus.br/informacoes-tecnicas (92), github.com/apolinario/urnas-tardias (62 — projeto comunitário sem processo editorial; usado só para estrutura de URL e códigos, ambos conferidos diretamente).

## Comparativo Final
| Critério | Pacote consolidado (dados abertos) | Arquivos por seção (Portal Resultados) |
|---|---|---|
| Prazo | nenhum normativo; 2–3 dias na prática | imediato após totalização da seção |
| Cobertura | só seções "Totalizado" | todas as seções listadas no cs.json |
| Integridade | ZIP sem hash do TSE (logs); bweb com SHA-512 | hash por seção no aux.json |
| Custo de coleta | 1 arquivo por UF (até 19 GB) | ~5 requisições por seção, ~500 mil seções |

## Recomendação
Não esperar o pacote: coletar por seção (feito, em curso) e conferir membro a membro quando o pacote sair. Confiança: ALTA.

## Contradições Identificadas
- Minuto da decisão de Zanin: 16h57 (UOL) × 17h01 (Conjur) × 17h03 (divulgação). Sem certidão única.
- Horário em que o STF foi acionado: 15h46 × 16h22.
- Votos após 17h: 34.393 (TSE) × 34.330 (g1 corrigido) × 35.521 (g1 inicial). A diferença de 63 é cálculo deste relatório.
- "17h06 / 0,25%": só imprensa, e de um único grupo editorial.

## Status dos Fatos-Chave
| Fato | Fontes | Verificado? |
|---|---|---|
| Não há prazo normativo para o pacote; 2–3 dias em 2022/2024 | Res. 23.760/2026 + CKAN | ✅ confirmado |
| 34.393 votos após 17h, com decomposição | TSE + CNN Brasil + Folha | ✅ confirmado |
| Prorrogação restrita a seções abertas (Ofício 354, 17h49) | PDF (Poder360) + Plural + TRE-SP | ✅ confirmado |
| Suspensão da totalização até 19h | TSE + TRE-SP + TRE-RJ (órgãos distintos) | ✅ confirmado |
| Resultado oficial e margem de 4.430.191 | TSE + Folha | ✅ confirmado |
| Arquivos do 2T públicos por seção desde 25/10 | verificação reproduzível (URLs e horários acima, 20.708 seções) + urnas-tardias + levantamento do g1 | ✅ confirmado |
| Log da urna é cumulativo (contém os dois turnos) | 1.519 seções de RR, reproduzível pelo CSV publicado | ✅ confirmado (verificação própria em escala) |
| Totalização parada às 17h06 com 0,25% | Valor/O Globo (mesmo grupo) | ⚠️ fonte única, sem documento oficial |
| Pedido de Flávio às 15h27 | DGABC | ⚠️ fonte única |

## Fontes Avaliadas (CRAAP)
**Tier A (80-100):** dadosabertos.tse.jus.br (96) · Ofício-Circular 354/2026, PDF (95) · tse.jus.br notícias 25–27/10 (94) · tse.jus.br informações técnicas (92) · noticias.stf.jus.br (92) · tre-sp.jus.br (90) · tre-rj.jus.br (90) · tre-go.jus.br (88) · Folha de S.Paulo (82) · g1 (82) · Valor (80)
**Tier B (60-79):** CNN Brasil (78) · O Globo (78) · Conjur (74) · Metrópoles (72) · github.com/apolinario/urnas-tardias (62)
**Tier C/D (<60):** DGABC (58, fonte única em dois horários) · 163notícias (45, reconstrução jornalística)
**Regra aplicada:** g1, O Globo e Valor (Grupo Globo) contam como uma única fonte quando citados em par; o mesmo vale para UOL e Folha (Grupo Folha/UOL).
