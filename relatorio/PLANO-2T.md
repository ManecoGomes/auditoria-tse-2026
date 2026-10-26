# Plano de análise do 2º turno — publicado antes dos dados

*Luis Manuel Jordão Elias Gomes (Maneco Gomes) — OAB/RJ 245.463*
*Publicado em 26 de outubro de 2026*

---

## Por que este documento existe

Os arquivos do 2º turno das Eleições Gerais de 2026 ainda não foram publicados pelo Tribunal
Superior Eleitoral. Este documento descreve, **antes de esses dados existirem para mim**, exatamente
o que será medido, como, e o que cada medida pode ou não demonstrar.

A razão é simples. A crítica mais destrutiva que se pode fazer a uma análise de dados é que o
analista escolheu o critério depois de ver o resultado. Quem procura o suficiente encontra algum
número estranho em qualquer conjunto de 100 milhões de registros — e, tendo escolhido o teste depois,
pode apresentá-lo como descoberta.

Publicar o plano antes elimina essa possibilidade. Tudo que está aqui será executado e reportado,
**inclusive os testes que não acusarem nada**. Nenhum teste será acrescentado depois sem que fique
identificado como posterior.

Este documento tem sua data ancorada na blockchain do Bitcoin, junto com o restante do acervo.

---

## Contexto

Em 25 de outubro de 2026, às 17h01, o Ministro Cristiano Zanin determinou a prorrogação da votação
do 2º turno até as 19h em todo o país, quando as urnas já encerravam. O TSE paralisou a divulgação
da totalização.

O 1º turno já foi auditado integralmente — 499.206 seções, 125.275.835 votantes, 28 unidades da
Federação, integridade conferida por SHA-512. Aquele turno serve de **grupo de controle**: nele a
regra era a ordinária, o prazo era 17h, e não houve contestação relevante.

---

## Os três arquivos, e o que cada um permite

Antes dos testes, é preciso entender a arquitetura dos dados — ela determina o que é possível.

**Boletim de Urna.** Totais por candidato em cada seção, mais quatro horários: abertura,
encerramento, emissão e recebimento. Dá o resultado, não a sequência.

**Log da urna.** Cada evento com data e hora, voto a voto. Registra `Voto confirmado para
[Presidente]` — o **cargo**, nunca o candidato. Dá a sequência, não o resultado.

**Registro Digital do Voto (RDV).** Os votos propriamente ditos, **ordenados**, com apenas dois
carimbos de tempo no arquivo inteiro (geração da mídia e encerramento). Dá o conteúdo, com a ordem
temporal deliberadamente destruída.

Essa separação é o mecanismo que garante o sigilo do voto. Se hora e candidato pudessem ser
cruzados, bastaria saber quando alguém votou para descobrir em quem.

**Consequência direta, e ela precisa estar dita desde o início:** não é possível, com nenhum dado
que o TSE publique — nem com acesso integral à urna — determinar em quem votaram os eleitores de
um intervalo de tempo específico. Totalizar "os votos após as 17h por candidato" é impossível por
construção. Qualquer análise que afirme isso está errada ou mentindo.

---

## O que será medido

### Bloco A — Integridade e procedência

**A1.** Conferência do SHA-512 de cada arquivo contra o resumo publicado pelo TSE. Arquivo que não
conferir não é auditado: é reportado como divergente.
*Observação já registrada: o TSE publica hash apenas para os boletins. Para os logs não há hash
oficial — nesses, a referência é o hash que calculamos no download e carimbamos em blockchain.*

**A2.** Triangulação entre os três arquivos. Boletim, RDV e log são artefatos independentes gerados
pela mesma urna. O número de votos para Presidente deve coincidir nos três. Divergência indica
problema no equipamento, no arquivo ou no processo.

**A3.** Soma dos boletins de seção contra o total oficial divulgado pela totalização.

### Bloco B — Horários, contra a régua do 1º turno

**B1.** Distribuição do horário de encerramento das seções, em faixas a partir do prazo legal
(19h no 2º turno, 17h no 1º), confrontada com a distribuição do 1º turno. Reporta-se a razão entre
os turnos.

**B2.** Horário de abertura. Aberturas tardias.

**B3.** Curva de recebimento dos boletins pela totalização.

**B4.** Horário do último voto de cada seção — que é diferente do horário de encerramento, este um
ato administrativo do mesário.

### Bloco C — Comportamento das urnas, do log

**C1.** Voto registrado **após o lacre do boletim**. A urna sela o próprio log ao encerrar: a última
linha é o registro da geração do log. Voto posterior a esse marco indica reabertura.

**C2.** Voto registrado **após as 19h** — fora do prazo mesmo sob a regra prorrogada.
*Voto entre 17h e 19h é lícito: era o prazo vigente. Volume nessa faixa não é irregularidade.*

**C3.** Curva de votação minuto a minuto, nacional e por unidade da Federação. O que se examina é o
**formato**: fluxo contínuo e declinante é compatível com fila real; degraus, saltos e rajadas
concentradas não são. No 1º turno a cauda decaiu suavemente (em Roraima: 290 votos às 16h59, 135 às
17h05, 59 às 17h15, 8 às 18h00).

**C4.** Intervalo entre votos consecutivos na mesma seção. Sequências implausivelmente rápidas —
abaixo do tempo físico necessário para um eleitor se identificar, entrar na cabine e votar em todos
os cargos — são sinal de registro não-humano.

**C5.** Ciclos de ligar e desligar da urna, e eventos de energia, no período da prorrogação.

**C6.** Habilitações comparadas a votos computados. O número de votos deve ser menor ou igual ao de
habilitações, nunca maior.

**C7.** Eventos de habilitação manual e falha biométrica, comparados às taxas do 1º turno.

### Bloco D — Impossibilidades lógicas

Situações que não podem ocorrer em operação regular. No 1º turno todas deram zero em 125 milhões
de votos.

**D1.** Comparecimento maior que o número de eleitores aptos na seção.
**D2.** Encerramento registrado antes da abertura.
**D3.** Boletim emitido antes do encerramento da votação.
**D4.** Seção com mais de um registro de urna.

### Bloco E — Comparação entre turnos, seção a seção

Aqui cada seção é controle de si mesma, o que remove boa parte das diferenças estruturais entre
regiões.

**E1.** Comparecimento da seção no 2º turno contra o 1º.
**E2.** Horário de encerramento da seção no 2º turno contra o 1º.
**E3.** Volume de votação após as 17h, por seção.

**E4 — o teste que responde à pergunta mais difícil, dentro do que é possível.**
Não se pode saber em quem votaram os eleitores de depois das 17h. Mas pode-se medir se as seções
com muita votação tardia deslocaram-se, entre o 1º e o 2º turno, de modo diferente das seções que
encerraram no horário.

Concretamente: para cada seção calcula-se a variação do percentual de cada candidato entre os
turnos, e verifica-se se essa variação tem relação com o volume de votos registrados após as 17h.

**Limitação que acompanha obrigatoriamente qualquer resultado deste teste:** trata-se de inferência
ecológica. Correlação no nível da seção **não demonstra** comportamento individual — é a falácia
ecológica, e ela derruba conclusões apressadas com frequência. Seções com fila longa tendem a ser
urbanas e populosas, e isso por si só já se associa a padrões de voto. Usar a seção como controle de
si mesma reduz muito esse viés, mas não o elimina.

O que este teste pode legitimamente afirmar: *"seções com votação tardia deslocaram-se X pontos a
mais ou a menos que as demais, comparadas a si mesmas no 1º turno"*. O que ele **não** pode afirmar:
em quem votou quem quer que seja.

### Bloco F — Geografia e agrupamento

**F1.** Distribuição geográfica da votação tardia, por município e zona eleitoral.
**F2.** Verificação de concentração anômala — se o fenômeno se espalha conforme a densidade
populacional e o porte das seções, ou se aparece agrupado de forma que a operação não explique.
**F3.** Seções que encerraram às 17h mesmo com a prorrogação em vigor, e sua distribuição.

### Bloco G — Dispersão operacional

**G1.** A ordem de prorrogação não chegou a 499 mil seções ao mesmo tempo. A dispersão dos horários
de encerramento é esperada e é, ela própria, um dado. Mede-se a heterogeneidade e verifica-se se o
padrão é compatível com a difusão de uma ordem administrativa.

---

## Como os resultados serão reportados

Todo teste acima será executado e publicado, **com o resultado que der**. Inclusive — e
especialmente — os que não acusarem nada.

Para cada teste será reportado: o número obtido, o número correspondente do 1º turno quando houver,
e a interpretação possível, separando o que o dado demonstra do que apenas sugere.

Achado que exija explicação não será apresentado como prova de fraude. Será apresentado como o que
é: um número que destoa do padrão e que precisa ser explicado — podendo a explicação ser
operacional, técnica ou irregular.

Os programas que executam cada teste são publicados junto. Qualquer pessoa pode refazer.

---

## O que não será feito

Não serão acrescentados testes depois de ver os dados sem que fiquem expressamente identificados
como posteriores a este plano e, portanto, de menor força probatória.

Não será afirmado nada sobre a escolha de eleitores individuais, porque os dados não permitem.

Não será afirmado que houve fraude a partir de número que admita explicação operacional ordinária.

---

## Compromisso

Se os testes não encontrarem nada, isso será publicado com a mesma ênfase com que seria publicado o
contrário. Foi assim no 1º turno, cujo resultado — nenhum indício de votação fora do horário legal —
está publicado desde 26 de outubro.

Uma auditoria que só divulga o que confirma a hipótese de quem a encomendou não é auditoria.

---

**Acompanhe:** auditoria-tse-2026.com.br
**Reproduza:** github.com/ManecoGomes/auditoria-tse-2026
