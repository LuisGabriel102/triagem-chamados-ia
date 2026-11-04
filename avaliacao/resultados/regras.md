# Avaliação: modo `regras`

Rodada em 04/11/2026 17:24 UTC, sem IA, só com o plano B por regras.
Conjunto: 40 chamados escritos para teste, com gabarito (`avaliacao/chamados_teste.jsonl`).

| Medida | Resultado |
|---|---|
| Acerto de categoria | 36/40 (90%) |
| Acerto de prioridade | 29/40 (72%) |
| Acerto de sentimento | 34/40 (85%) |
| Acerto de número do pedido | 40/40 (100%) |
| Os 4 campos certos no mesmo chamado | 21/40 (52%) |
| Urgentes reconhecidos como urgentes | 6/7 (86%) |
| Urgentes liberados sem olhar humano | 0 |
| Enviados para revisão humana | 40/40 (100%) |
| Liberados sem revisão com categoria e prioridade certas | — |
| Dados pessoais que sobraram no texto enviado à IA | 0 de 9 |
| Quedas para o plano B | 40 |
| Custo total | US$ 0.0000 |
| Custo médio por chamado | US$ 0.000000 |
| Tempo médio por chamado | 0 ms |

## Onde errou

| Chamado | Campo | Gabarito | Resultado |
|---|---|---|---|
| f01 | prioridade | urgente | alta |
| f02 | prioridade | alta | media |
| f03 | prioridade | media | alta |
| f08 | categoria | financeiro | suporte_tecnico |
| s01 | prioridade | alta | media |
| s02 | sentimento | negativo | neutro |
| s05 | prioridade | alta | media |
| s06 | prioridade | media | urgente |
| s08 | sentimento | negativo | neutro |
| c03 | prioridade | baixa | alta |
| c06 | prioridade | baixa | media |
| x03 | sentimento | negativo | neutro |
| x06 | sentimento | positivo | neutro |
| r02 | prioridade | alta | baixa |
| r02 | sentimento | negativo | positivo |
| r03 | sentimento | negativo | neutro |
| r05 | categoria | reclamacao | suporte_tecnico |
| r05 | prioridade | media | alta |
| r06 | categoria | reclamacao | financeiro |
| r07 | categoria | reclamacao | outros |
| o03 | prioridade | baixa | urgente |
