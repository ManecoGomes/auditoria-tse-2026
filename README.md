# Auditoria de horários — Eleições Gerais 2026

Verificação independente dos registros de horário nos dados públicos do Tribunal Superior
Eleitoral, com o fim de identificar eventual votação fora do horário legal.

**Resultado do 1º turno: nenhum indício de votação fora do horário legal.**
Universo auditado: 499.206 seções, 125.275.835 votantes, 28/28 unidades da Federação.
Integridade de todos os arquivos conferida por SHA-512 contra o hash publicado pelo próprio TSE.

| Verificação | Ocorrências |
|---|--:|
| Comparecimento maior que eleitores aptos | 0 |
| Encerramento anterior à abertura | 0 |
| Boletim emitido antes do encerramento | 0 |
| Seção com mais de um registro de urna | 0 |
| Abertura após 8h30 | 960 |
| Encerramento após 19h | 8.324 |

O 2º turno (25/10/2026), com votação prorrogada até as 19h por decisão do Min. Cristiano Zanin,
**ainda não pode ser auditado** — o TSE não publicou os arquivos correspondentes.

## Conteúdo

```
relatorio/   RELATORIO.md, PDF e tabela por UF
scripts/     os dois programas usados, sem dependências externas
dados/       resultado por UF em JSON + registro dos arquivos preservados
site/        site estático publicado
manifesto.json[.ots]   SHA-512 de tudo, carimbado em blockchain
```

## Reproduzir

```bash
# 1. baixar da fonte e conferir integridade
UF=RR; BASE=https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb
curl -LO $BASE/bweb_1t_${UF}_051020261403.zip
curl -L  $BASE/bweb_1t_${UF}_051020261403.zip.sha512
shasum -a 512 bweb_1t_${UF}_051020261403.zip     # deve coincidir

# 2. rodar as verificações
python3 scripts/audita_bu.py
python3 scripts/audita_logs.py
```

## Verificar que esta pesquisa não foi alterada

```bash
pip install opentimestamps-client
ots verify manifesto.json.ots -f manifesto.json
```

O carimbo ancora o resumo criptográfico na blockchain do Bitcoin: comprova a data de existência
do conteúdo sem exigir confiança nos autores, no provedor de hospedagem ou em qualquer empresa.

## Limitações

Os dados do TSE **não identificam o eleitor**. O log registra a habilitação sem qualquer elemento
de identificação — voto e identidade são desacoplados por força do sigilo do voto (art. 14 da
Constituição). Não é possível, com esta base, afirmar que determinada pessoa votou, nem que votou
mais de uma vez. A seção 7 do relatório trata disso em detalhe.

## Licença

Dados públicos do TSE. Código e análise em domínio público (CC0). Reprodução, verificação e
contestação são bem-vindas — uma auditoria que não aceita ser auditada não serve para nada.
