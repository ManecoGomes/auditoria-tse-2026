# O que foi feito, e o que será feito com o 2º turno

*Luis Manuel Jordão Elias Gomes (Maneco Gomes) — OAB/RJ 245.463*
*26 de outubro de 2026*

---

## O problema que me levou a isso

No domingo, 25 de outubro, às 17h01, o Ministro Cristiano Zanin determinou a prorrogação da votação
do 2º turno até as 19h em todo o país. As urnas já estavam encerrando. O TSE paralisou a divulgação
da totalização.

Naquela noite a pergunta que circulava era simples: houve votação fora de hora?

E a resposta honesta era que **ninguém tinha como saber** — não porque os dados não existam, mas
porque faltava algo mais básico: um ponto de comparação. Se eu dissesse amanhã que "oito mil seções
encerraram depois das 19h no 2º turno", esse número seria alarmante ou trivial? Sem saber quantas
encerraram depois das 19h num turno em que nada foi contestado, não há como responder. O número
sozinho não informa nada.

Foi por isso que comecei pelo 1º turno.

---

## O que eu fiz

Baixei e verifiquei **todos os boletins de urna do 1º turno** das Eleições Gerais de 2026:

- 499.206 seções eleitorais
- 125.275.835 votantes
- 158.745.007 eleitores aptos
- 28 de 28 unidades da Federação

O boletim de urna de cada seção registra quatro horários: quando a urna foi aberta, quando a votação
foi encerrada, quando o boletim foi emitido e quando foi recebido pela totalização. São esses
carimbos de tempo que permitem verificar se algo aconteceu fora da ordem.

**Antes de analisar, conferi a procedência.** O TSE publica, ao lado de cada arquivo, um resumo
criptográfico SHA-512 — uma espécie de impressão digital. Recalculei a impressão digital de cada
arquivo baixado e comparei com a publicada pelo Tribunal. Os 28 conferiram. Isso significa que os
arquivos analisados são bit a bit os distribuídos pelo TSE, sem alteração no caminho.

Depois apliquei seis verificações. Quatro delas são de **impossibilidade lógica** — situações que
simplesmente não podem ocorrer em operação regular. Todas deram zero:

- Seção com mais votos do que eleitores aptos a votar nela: **0**
- Encerramento registrado antes da abertura: **0**
- Boletim emitido antes do encerramento da votação: **0**
- Seção com mais de um registro de urna: **0**

E duas de medição, que não acusam irregularidade mas estabelecem o padrão:

- Seções que abriram depois das 8h30: **960**
- Seções que encerraram depois das 19h: **8.324**

---

## O que isso estabeleceu

Aquele último número é o mais importante deste trabalho inteiro.

**No 1º turno, com prazo legal de encerramento às 17h, 8.324 seções encerraram depois das 19h** —
1,67% do total, envolvendo 2,46 milhões de eleitores.

Isso não é irregularidade. É como a eleição funciona: quem está na fila às 17h tem direito de votar
(art. 153 do Código Eleitoral), e depois do último voto ainda vêm o procedimento de fechamento da
urna e a impressão das vias do boletim. Uma seção pode encerrar às 19h30 tendo recebido seu último
voto às 17h05.

A distinção é essencial e vale repetir: **o horário de encerramento é um ato administrativo do
mesário, não a hora do último voto.** Quem informa a hora exata do último voto é outro arquivo — o
log da urna, que registra cada evento com data e hora.

Portanto: existe agora uma régua. Quando alguém afirmar qualquer coisa sobre encerramentos tardios
no 2º turno, há contra o que comparar.

---

## Uma confusão que os dados desfazem

Vale registrar, porque reaparece a cada eleição.

**100% dos votos entram na contagem depois das 17h.** Não porque alguém vote depois — mas porque
antes das 17h a apuração sequer começou. O que dispara às 17h é a *transmissão* dos boletins, não a
*votação*. No 1º turno, 59% dos votos entraram na totalização entre 18h e 19h.

Ver o placar saltar no início da noite é ver o sistema funcionar como foi desenhado. Não é indício
de nada.

---

## O que será feito com o 2º turno

O TSE ainda não publicou os arquivos do 2º turno. No 1º turno os boletins saíram dois dias após o
pleito e os logs de urna, três. Projeta-se publicação entre 27 e 29 de outubro.

Quando saírem, as **mesmas seis verificações** rodam, com os **mesmos programas**, e o resultado é
confrontado com a régua acima. Mas o 2º turno tem particularidades que exigem exames adicionais,
justamente por causa da prorrogação.

### 1. Votos registrados depois das 19h

A liminar moveu o prazo de 17h para 19h. Voto registrado **depois das 19h** estaria fora do prazo
mesmo sob a regra nova. É a verificação mais direta.

Atenção ao que isso **não** significa: voto registrado entre 17h e 19h no 2º turno é **lícito**.
Volume nessa faixa não é indício de nada — era o prazo vigente.

### 2. Urnas que encerraram e foram reabertas

Esta é a verificação mais relevante, e é possível por uma característica do equipamento: **a urna
lacra o próprio log ao encerrar.** A última linha do arquivo é o registro da geração do próprio log.

A decisão veio às 17h01, com urnas já em processo de encerramento. É razoável supor que parte delas
tenha encerrado antes de a ordem chegar. O que aconteceu com essas? Se alguma foi reaberta para
receber votos, o log mostra — porque haveria atividade após o lacre.

Vou procurar exatamente isso: voto registrado após a geração do arquivo de resultado.

### 3. O formato da curva de votação

No 1º turno, medindo voto a voto pelo log, a cauda após as 17h decai de forma suave e contínua —
assinatura de fila se esvaziando. Em Roraima, por exemplo: 288 votos às 17h00, 135 às 17h05, 59 às
17h15, 8 às 18h00, pingando até as 20h05.

No 2º turno a curva deve ter outro formato, porque houve duas horas legais a mais. O que se examina
não é o volume, e sim o **formato**: fluxo contínuo e declinante é compatível com votação real;
degraus, saltos ou rajadas concentradas não são.

### 4. Heterogeneidade entre seções

A notícia da prorrogação não chegou a 499 mil seções ao mesmo tempo. Parte encerrou às 17h, parte
seguiu até as 19h. Essa dispersão é esperada — e é, ela própria, um dado.

O que se examina é se o padrão faz sentido geográfico e operacional, ou se há concentração anômala
em municípios ou zonas específicas.

### 5. As quatro verificações de impossibilidade

Comparecimento acima do número de aptos, inversões cronológicas, boletins fora de sequência e
duplicidade de urna. No 1º turno deram zero em 125 milhões de votos. Se no 2º turno der diferente de
zero, isso exige explicação.

---

## O que não será possível afirmar

Esta seção importa tanto quanto as outras, e omiti-la descaracterizaria todo o resto.

**Os dados do TSE não identificam o eleitor.** O log registra que um eleitor foi habilitado, sem
qualquer elemento de identificação. Voto e identidade são desacoplados por desenho, em decorrência
do sigilo do voto (art. 14 da Constituição).

Em consequência: **não é possível, com esta base, afirmar que determinada pessoa votou, nem que
votou mais de uma vez.** Hipóteses desse tipo — por mais que circulem — não são testáveis com
boletim de urna nem com log. Sustentá-las exigiria prova de outra natureza: caderno de votação,
registro de imagem, representação à Justiça Eleitoral com pedido de diligência.

Isso não é limitação do método que empreguei. É característica da fonte, e eu preferiria que fosse
diferente. Mas relatar o que a fonte permite, e só isso, é o que separa auditoria de especulação.

Também não alcanço: o código-fonte da urna, o processo interno de totalização, e o que ocorreu
presencialmente nas seções.

---

## Por que tudo isso está publicado

Porque auditoria que pede confiança não é auditoria.

Estão públicos: o relatório integral, os dois programas usados, os dados resultantes de cada unidade
da Federação, e os arquivos originais do TSE conforme eu os baixei. Qualquer pessoa pode refazer o
caminho inteiro e conferir se os números batem. Se não baterem, o erro é meu e quero saber.

Mais do que isso: o conjunto tem um manifesto com a impressão digital de cada arquivo, e esse
manifesto está **ancorado na blockchain do Bitcoin** (bloco 973245). Isso prova a data em que o
conteúdo existia, de forma permanente e verificável por qualquer um — sem depender de mim, do
provedor de hospedagem ou de qualquer empresa. Nem eu posso alterar nada sem deixar rastro.

E registro o ponto que considero decisivo: **o método foi publicado antes de os dados do 2º turno
existirem.** Não é possível, depois, ajustar o critério para chegar a uma conclusão desejada. O
critério já está lá, com data carimbada.

---

## O resultado do 1º turno, dito com todas as letras

**Nenhum indício de votação fora do horário legal foi encontrado no 1º turno.**

Publico isso com a mesma ênfase com que publicaria o contrário. Se eu só divulgasse achados que
confirmam uma hipótese, isto não seria auditoria — seria propaganda com aparência técnica.

Este trabalho não afirma que a eleição transcorreu sem irregularidades. Afirma, por método
reproduzível sobre dados de integridade confirmada, que **as irregularidades de horário procuradas
não foram encontradas nos dados examinados**.

O 2º turno será tratado exatamente da mesma forma: as mesmas verificações, os mesmos programas, e o
resultado publicado qualquer que seja.

---

**Acompanhe:** auditoria-tse-2026.com.br
**Reproduza:** github.com/ManecoGomes/auditoria-tse-2026
