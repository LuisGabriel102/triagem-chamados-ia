# Avaliação: modo `ia`

Rodada em 13/11/2026 12:24 UTC, com o modelo `claude-haiku-5-5` (Claude, da Anthropic).
Conjunto: 40 chamados escritos para teste, com gabarito (`avaliacao/chamados_teste.jsonl`).
Preço usado no custo: US$ 0.1 por milhão de tokens de entrada e US$ 0.5 por milhão de saída.

| Medida | Resultado |
|---|---|
| Acerto de categoria | 40/40 (100%) |
| Acerto de prioridade | 37/40 (92%) |
| Acerto de sentimento | 39/40 (98%) |
| Acerto de número do pedido | 40/40 (100%) |
| Os 4 campos certos no mesmo chamado | 36/40 (90%) |
| Urgentes reconhecidos como urgentes | 7/7 (100%) |
| Urgentes liberados sem olhar humano | 0 |
| Enviados para revisão humana | 14/40 (35%) |
| Liberados sem revisão com categoria e prioridade certas | 23/26 (88%) |
| Dados pessoais que sobraram no texto enviado à IA | 0 de 9 |
| Quedas para o plano B | 0 |
| Custo total | US$ 0.0095 |
| Custo médio por chamado | US$ 0.000239 |
| Tempo médio por chamado | 2292 ms |

## Onde errou

| Chamado | Campo | Gabarito | Resultado |
|---|---|---|---|
| s01 | sentimento | neutro | negativo |
| c01 | prioridade | media | baixa |
| c06 | prioridade | baixa | media |
| r01 | prioridade | alta | media |
