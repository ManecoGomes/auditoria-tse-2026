# Auditoria do 2º turno — Eleições Gerais 2026

*Gerado automaticamente em 29/10/2026 15:33 (America/Sao_Paulo)*
*Luis Manuel Jordão Elias Gomes (Maneco Gomes) — OAB/RJ 245.463*

Prazo legal de encerramento no 2º turno: **19h** (horário de Brasília), por decisão do
Ministro Cristiano Zanin de 25/10/2026, que prorrogou a votação a partir das 17h01.

## 1. Universo auditado

- Unidades da Federação: 28
- Seções eleitorais: 499.205
- Comparecimento: 128.236.074
- Eleitores aptos: 158.744.977
- Seções com log analisado: 278.116
- Votos para Presidente nos logs: 70.727.343

## 2. Verificações de impossibilidade lógica

- Comparecimento maior que eleitores aptos: **0**  (1º turno: 0)
- Encerramento anterior à abertura: **0**  (1º turno: 0)
- Boletim emitido antes do encerramento: **0**  (1º turno: 0)

## 3. Encerramento das seções, contra a régua do 1º turno

- até o prazo legal: 491.545 seções (98.72%), 125.993.372 votantes
- até +5 min: 5.576 seções (1.12%), 1.627.844 votantes
- até +30 min: 751 seções (0.15%), 227.714 votantes
- até +1 h: 16 seções (0.00%), 3.733 votantes
- até +2 h: 8 seções (0.00%), 1.872 votantes
- mais de +2 h: 1 seções (0.00%), 96 votantes

No 1º turno, 8.324 seções (1.67%) encerraram mais de 2h após o prazo legal.
No 2º turno: **1 seções (0.00%)**.
Razão entre os turnos: **0.00×**.

Razão próxima de 1 indica comportamento equivalente ao do turno não contestado.
Razão muito acima de 1 indica desvio que exige explicação.

## 4. Verificações específicas do 2º turno

- Seções com voto registrado **após o lacre do boletim** (reabertura de urna): **0**
- Seções com voto registrado **após as 19h** (fora do prazo mesmo sob a regra nova): **3**
- Seções com divergência entre habilitações e votos computados: **30.511**
- Habilitações: 139.570.799 · Votos computados: 139.533.552 (diferença 37.247)

Voto registrado entre 17h e 19h no 2º turno é **lícito** — era o prazo vigente por
força da decisão judicial. Volume nessa faixa não constitui, por si, irregularidade.

## 5. Limitações

Os dados do TSE não identificam o eleitor. O log registra a habilitação sem qualquer
elemento de identificação — voto e identidade são desacoplados por força do sigilo do
voto (art. 14 da Constituição). Não é possível, com esta base, afirmar que determinada
pessoa votou, nem que votou mais de uma vez.

## 6. Reprodução

Programas, dados e manifesto criptográfico em github.com/ManecoGomes/auditoria-tse-2026.
O método foi publicado em 26/10/2026, antes da divulgação destes dados, e sua data está
ancorada na blockchain do Bitcoin (bloco 973245).
