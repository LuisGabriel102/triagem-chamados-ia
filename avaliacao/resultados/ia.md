# Avaliação: modo `ia`

Rodada em 04/11/2026 18:21 UTC, com o modelo `claude-haiku-5-5`.
Conjunto: 40 chamados escritos para teste, com gabarito (`avaliacao/chamados_teste.jsonl`).

| Medida | Resultado |
|---|---|
| Acerto de categoria | 40/40 (100%) |
| Acerto de prioridade | 38/40 (95%) |
| Acerto de sentimento | 38/40 (95%) |
| Acerto de número do pedido | 40/40 (100%) |
| Os 4 campos certos no mesmo chamado | 36/40 (90%) |
| Urgentes reconhecidos como urgentes | 7/7 (100%) |
| Urgentes liberados sem olhar humano | 0 |
| Enviados para revisão humana | 13/40 (32%) |
| Liberados sem revisão com categoria e prioridade certas | 25/27 (93%) |
| Dados pessoais que sobraram no texto enviado à IA | 0 de 9 |
| Quedas para o plano B | 0 |
| Custo total | US$ 0.0096 |
| Custo médio por chamado | US$ 0.000241 |
| Tempo médio por chamado | 2620 ms |

## Onde errou

| Chamado | Campo | Gabarito | Resultado |
|---|---|---|---|
| s01 | sentimento | neutro | negativo |
| c01 | prioridade | media | baixa |
| x03 | sentimento | negativo | neutro |
| r01 | prioridade | alta | media |
