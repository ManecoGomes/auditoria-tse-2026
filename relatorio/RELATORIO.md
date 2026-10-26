# Relatório de Auditoria Independente de Horários — Eleições Gerais 2026

**Objeto:** verificação de registros de horário nos dados públicos do Tribunal Superior Eleitoral,
com o fim de identificar eventual votação fora do horário legal.

**Data de emissão:** 25 de outubro de 2026
**Solicitante / responsável:** Luis Manuel Jordão Elias Gomes (Maneco Gomes) — OAB/RJ 245.463
**Execução técnica:** processamento automatizado sobre dados abertos do TSE; scripts íntegros no Anexo B
**Status deste documento:** **PARCIAL** — ver §8

---

## 1. Sumário executivo

Foram auditados **todos os 499.206 boletins de urna do 1º turno** das Eleições Gerais de 2026,
correspondentes a **125.275.835 votantes** em 158.745.007 eleitores aptos, abrangendo as 27 unidades
da Federação e as seções do exterior (ZZ).

A integridade de todos os 28 arquivos foi confirmada por **SHA-512 contra o hash publicado pelo
próprio TSE**.

### Resultado das verificações de consistência

| # | Verificação | Ocorrências | Interpretação |
|---|---|--:|---|
| V1 | Comparecimento maior que eleitores aptos | **0** | Nenhuma seção registrou mais votos do que eleitores habilitados a votar nela |
| V2 | Encerramento anterior à abertura | **0** | Nenhuma inversão cronológica |
| V3 | Boletim de Urna emitido antes do encerramento | **0** | Nenhum BU emitido fora de ordem |
| V4 | Seção com mais de um registro de urna | **0** | Nenhuma duplicidade de urna por seção |
| V5 | Abertura após 8h30 (horário de Brasília) | 960 | 0,19% das seções; abertura tardia é ocorrência operacional ordinária |
| V6 | Encerramento após 19h (horário de Brasília) | 8.324 | 1,67% das seções — **ver §5.2, é o dado de referência** |

**Conclusão do 1º turno: nenhum indício de votação fora do horário legal foi encontrado.**
As quatro verificações capazes de caracterizar voto fabricado ou registro fora de sequência (V1 a V4)
retornaram zero ocorrências em 125,3 milhões de votos.

**O 2º turno, realizado em 25/10/2026, ainda não pode ser auditado** — o TSE não publicou os arquivos
correspondentes até a emissão deste relatório (§8).

---

## 2. Contexto

Em 25 de outubro de 2026, às 17h01, o Ministro Cristiano Zanin, do Supremo Tribunal Federal, determinou
a prorrogação do encerramento da votação do 2º turno até as 19h em todo o território nacional. O pedido
foi formulado pela campanha de Luiz Inácio Lula da Silva, sob alegação de falhas no transporte público;
a campanha de Flávio Bolsonaro havia pleiteado prorrogação de duas horas em municípios de Minas Gerais e
do Rio Grande do Sul atingidos por chuvas. O Tribunal Superior Eleitoral paralisou a divulgação da
totalização em seguida.

Nas Eleições 2026 o horário ordinário de votação foi das **8h às 17h pelo horário oficial de Brasília**,
unificado em todo o país, inclusive nas unidades da Federação com fuso distinto.

Esta auditoria foi encomendada para verificar, sobre dados primários e por método reproduzível, se há
registro de votação fora do horário legal.

---

## 3. Origem dos dados e cadeia de custódia

Todos os dados provêm do Portal de Dados Abertos do TSE, de acesso público e irrestrito.

| Conjunto | Identificador (CKAN) | Uso nesta auditoria |
|---|---|---|
| Boletim de Urna | `resultados-2026-boletim-de-urna` | §5 — horários de abertura, encerramento, emissão e recebimento do BU |
| Arquivos transmitidos para totalização | `resultados-2026-arquivos-transmitidos-para-totalizacao` | §6 — logs de urna, com carimbo de tempo por voto |

Endereço do catálogo:
`https://dadosabertos.tse.jus.br/api/3/action/package_show?id=<identificador>`

**Verificação de integridade.** O TSE publica, ao lado de cada arquivo, o respectivo resumo
criptográfico SHA-512. O procedimento de auditoria recalculou o SHA-512 de cada arquivo baixado e o
comparou com o publicado. **Os 28 arquivos conferiram.** Os hashes calculados constam da tabela do §5.4
e permitem a qualquer terceiro confirmar que os dados analisados são idênticos aos distribuídos pelo
Tribunal.

---

## 4. Metodologia

### 4.1 Fontes de horário

Dois conjuntos independentes do TSE registram tempo, com naturezas distintas:

**(a) Boletim de Urna (arquivo CSV).** Contém, por seção eleitoral, os campos `DT_ABERTURA`,
`DT_ENCERRAMENTO`, `DT_EMISSAO_BU` e `DT_BU_RECEBIDO`.

**(b) Log da urna eletrônica (arquivo `.jez`).** Registra cada evento da urna com data e hora, inclusive
`Voto confirmado para [Cargo]`, `Eleitor foi habilitado` e `O voto do eleitor foi computado`.
Tecnicamente, o `.jez` é um contêiner ZIP que encerra um arquivo-texto `logd.dat`.

### 4.2 Distinção essencial entre encerramento e último voto

`DT_ENCERRAMENTO` registra o **ato administrativo** do mesário que encerra a votação na seção — ato que
sucede o último voto e os procedimentos de fechamento, incluindo a impressão das vias do boletim.
**Não é a hora do último voto.** Uma seção pode encerrar às 19h30 tendo recebido seu último voto às
17h05.

A hora efetiva do último voto só se obtém no log da urna. Por essa razão a auditoria tem duas fases, e
qualquer conclusão sobre "voto fora de hora" apoiada apenas em `DT_ENCERRAMENTO` seria metodologicamente
incorreta.

### 4.3 Tratamento de fuso horário

O relógio da urna opera em **hora local**. Para comparação com o horário legal (Brasília, UTC−3), foi
somado a cada registro: **+2h** no Acre; **+1h** em Amazonas, Mato Grosso, Mato Grosso do Sul, Rondônia e
Roraima; **0h** nas demais unidades. Não há horário de verão no Brasil desde 2019. As seções do exterior
(ZZ) seguem fusos variados e foram excluídas da conversão, sendo reportadas à parte.

### 4.4 Verificações aplicadas (critérios objetivos)

As verificações V1 a V4 do §1 são de **impossibilidade lógica**: em operação regular não podem ocorrer.
Qualquer ocorrência exige explicação.

As verificações V5 e V6 são **estatísticas**: medem a cauda operacional. Não constituem irregularidade
por si sós — servem de linha de base para comparação.

Sobre os logs (§6) acrescentam-se:

- **V7 — voto registrado após a geração do arquivo de resultado (`bu.dat`).** A urna gera o BU no
  encerramento e **sela o próprio log**: a última linha do arquivo é o registro da geração do
  `log.jez`. Voto posterior a esse marco indicaria reabertura da urna após o encerramento.
- **V8 — voto registrado após as 19h.**
- **V9 — divergência entre habilitações e votos computados.**

---

## 5. Resultados — Boletins de Urna (1º turno)

### 5.1 Universo

| | |
|---|--:|
| Unidades da Federação auditadas | 28 de 28 |
| Seções eleitorais | 499.206 |
| Comparecimento | 125.275.835 |
| Eleitores aptos | 158.745.007 |
| Arquivos com SHA-512 conferido | 28 de 28 |

### 5.2 Distribuição do encerramento das seções (horário de Brasília)

| Faixa | Seções | % | Votantes | % |
|---|--:|--:|--:|--:|
| até 17h00 | 370 | 0,07% | 85.818 | 0,07% |
| 17h00 – 17h05 | 261.456 | 52,51% | 61.493.909 | 49,22% |
| 17h05 – 17h30 | 149.388 | 30,00% | 38.443.575 | 30,77% |
| 17h30 – 18h00 | 43.775 | 8,79% | 12.392.750 | 9,92% |
| 18h00 – 19h00 | 34.582 | 6,95% | 10.061.978 | 8,05% |
| **após 19h00** | **8.324** | **1,67%** | **2.455.480** | **1,97%** |

**Leitura.** No 1º turno, cujo prazo legal de encerramento era 17h, **8.324 seções encerraram
administrativamente após as 19h**, envolvendo 2,46 milhões de eleitores. Isso é cauda operacional
ordinária: fila remanescente (o eleitor presente às 17h tem direito de votar, art. 153 do Código
Eleitoral), procedimentos de fechamento e impressão de vias do boletim.

Este número é a **linha de base**. Qualquer afirmação futura de que "milhares de seções encerraram
tarde no 2º turno" só adquire sentido quando confrontada com este patamar.

### 5.3 Recebimento dos boletins pela totalização (horário de Brasília)

| Hora | Seções | Votos | Acumulado |
|---|--:|--:|--:|
| 17h | 75.058 | 18.100.193 | 14,45% |
| 18h | 228.486 | 56.199.391 | 59,31% |
| 19h | 126.393 | 32.676.356 | 85,39% |
| 20h | 60.721 | 16.122.287 | 98,26% |
| 21h | 7.327 | 1.878.543 | 99,76% |
| 22h | 1.080 | 264.752 | 99,97% |
| 23h | 126 | 30.629 | 100,00% |

**Leitura — ponto que costuma gerar confusão.** **100% dos votos entram na contagem depois das 17h**,
porque antes das 17h a apuração não começou. O que dispara às 17h é a *transmissão* dos boletins, não a
*votação*. O crescimento abrupto do placar no início da noite é consequência necessária do desenho do
sistema e **não constitui, por si, indício de irregularidade**.

### 5.4 Resultado por unidade da Federação

Tabela completa, com hashes, em `tabela_uf.md` (acompanha este relatório).

---

## 6. Resultados — Logs de urna (1º turno)

**Fase em execução na data de emissão.** Resultados parciais disponíveis; o quadro completo das 28
unidades integrará a revisão deste documento.

Exemplo do que a verificação produz, unidade do Acre (2.270 seções, 487.379 votos para Presidente):

| Verificação | Resultado |
|---|--:|
| V7 — voto após geração do BU (reabertura de urna) | **0** |
| V8 — seções com voto após 19h | 10 |
| V9 — habilitações (488.191) × votos computados (487.806) | diferença de 385 |

A diferença de V9 corresponde a eleitores habilitados que não concluíram o voto — ocorrência ordinária
(desistência, falha de procedimento), e **não** a votos excedentes: o número de votos é *menor* que o de
habilitações, nunca maior.

---

## 7. Limitações — o que estes dados não permitem afirmar

Esta seção é parte integrante do relatório e sua omissão descaracteriza as conclusões.

**7.1 Os dados do TSE não identificam o eleitor.** O log registra `Eleitor foi habilitado` sem qualquer
elemento de identificação. O voto e a identidade do votante são desacoplados por projeto, em
decorrência do sigilo do voto (art. 14 da Constituição). **Não existe, em boletim de urna ou em log de
urna, campo que permita afirmar que determinada pessoa votou, nem que votou mais de uma vez.**

Em consequência, a hipótese de que um mesário tenha votado indevidamente durante a prorrogação **não é
testável com esta base**. Isso não é limitação do método empregado: é característica da fonte. Sustentar
tal alegação exigiria prova de outra natureza — caderno de votação, imagem, testemunho, representação
perante a Justiça Eleitoral com pedido de diligência.

O que *é* verificável no agregado, e foi verificado: se uma seção registrou mais votos do que eleitores
aptos (V1), se há descompasso entre habilitações e votos (V9), e se houve voto após o encerramento (V7).

**7.2 Votos entre 17h e 19h no 2º turno serão lícitos.** Em razão da decisão referida no §2, voto
registrado nessa janela no 2º turno estará dentro do prazo então vigente. Volume de votos nesse intervalo
não constitui, por si só, irregularidade.

**7.3 O relógio da urna é interno.** A auditoria confere a coerência interna dos registros, não a
sincronia absoluta do relógio de cada equipamento com uma referência externa.

**7.4 Alcance.** A auditoria cobre os dados publicados pelo TSE. Não alcança o código-fonte da urna, o
processo de totalização, nem os procedimentos presenciais nas seções.

---

## 8. Estado do 2º turno

Consulta ao catálogo do TSE em 25/10/2026, 21h53:

```
resultados-2026-boletim-de-urna                        → arquivos do 2º turno: 0
resultados-2026-arquivos-transmitidos-para-totalizacao → arquivos do 2º turno: 0
```

No 1º turno, os boletins foram publicados em 06/10 (dois dias após o pleito) e os arquivos de urna em
07/10 (três dias). Projeta-se publicação do 2º turno **entre 27 e 29 de outubro de 2026**.

Monitoramento automatizado foi instalado e verifica o catálogo de hora em hora. Publicados os arquivos,
as mesmas verificações V1 a V9 serão aplicadas e confrontadas com a linha de base deste relatório.

---

## 9. Conclusão

No universo auditado — **a totalidade dos boletins de urna do 1º turno das Eleições Gerais de 2026,
499.206 seções e 125.275.835 votantes, com integridade criptográfica confirmada** — **não foi
identificado indício de votação fora do horário legal.** As quatro verificações de impossibilidade
lógica retornaram zero ocorrências.

Os encerramentos posteriores às 17h, inclusive os 8.324 posteriores às 19h, são compatíveis com
atendimento de fila remanescente e com os procedimentos de fechamento, e correspondem a ato
administrativo do mesário, não à hora do último voto.

A verificação do 2º turno fica pendente da publicação dos dados pelo Tribunal.

Este relatório não afirma a inexistência de irregularidades na eleição. Afirma, com base em método
reproduzível sobre dados íntegros, que **as irregularidades de horário procuradas não foram
encontradas nos dados examinados**.

---

## Anexo A — Reprodução

Qualquer pessoa pode reproduzir integralmente esta auditoria. Requisitos: Python 3, `curl`, ~90 GB de
disco livre para a fase de logs.

```bash
# 1. Listar os arquivos e seus hashes oficiais
curl -s "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026-boletim-de-urna" \
  | python3 -m json.tool | grep '"url"'

# 2. Baixar um arquivo e conferir a integridade
UF=RR
curl -LO "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_1t_${UF}_051020261403.zip"
curl -L  "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_1t_${UF}_051020261403.zip.sha512"
shasum -a 512 bweb_1t_${UF}_051020261403.zip      # deve coincidir

# 3. Rodar as verificações (scripts no Anexo B)
python3 audita_bu.py          # fase 1 — boletins de urna
python3 audita_logs.py        # fase 2 — logs de urna

# 4. Inspecionar um log de urna individualmente
unzip -j bu_imgbu_logjez_rdv_vscmr_2026_1t_RR.zip "*-log.jez" -d logs/
cd logs && unzip -o <arquivo>-log.jez       # produz logd.dat
iconv -f latin1 -t utf8 logd.dat | grep "Voto confirmado"
```

## Anexo B — Scripts

`scripts/audita_bu.py` — verificações V1 a V6 sobre boletins de urna, com conferência de SHA-512.
`scripts/audita_logs.py` — verificações V7 a V9 sobre logs de urna.

Ambos acompanham este relatório, sem dependências externas além da biblioteca padrão do Python.

## Anexo C — Tabela por unidade da Federação

`tabela_uf.md` — seções, comparecimento, aptos, resultado da conferência SHA-512, início do hash
calculado e contagem de cada verificação, por UF.

---

*Documento gerado por procedimento automatizado sobre dados públicos. Os números são conferíveis por
terceiros mediante os Anexos A e B.*
