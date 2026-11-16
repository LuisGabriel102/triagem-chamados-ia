# Avaliação da busca na base de conhecimento

Rodada em 13/11/2026 12:36 UTC. Base: 30 artigos (`base/artigos/`). Perguntas: 60 (`avaliacao/perguntas_agente.jsonl`), 44 com o artigo certo no gabarito e 16 sem resposta na base.

> **Ressalva:** As perguntas foram escritas por um agente separado (Claude), que só viu o base/EMPRESA.md e não viu os artigos. O gabarito foi montado depois, por quem escreveu a base.

- Busca por sentido: pela chave do Google AI Studio, modelo gemini-embedding-2, 768 dimensões.
- Limiar do BM25: 6.2882 (base/limiares.json, calibrado em 2026-11-13).
- Limiar da similaridade: 0.7108 (base/limiares.json (gemini-embedding-2, 768 dimensões), calibrado em 2026-11-13).

| Medida | Por sentido | Híbrida |
|---|---|---|
| **Respondidas e certas** (acima do limiar e com o artigo certo entre os 3) | 39/44 (89%) | 37/44 (84%) |
| Acerto no 1º lugar | 41/44 (93%) | 37/44 (84%) |
| Acerto entre os 3 primeiros | 44/44 (100%) | 41/44 (93%) |
| Sem resposta que ficaram em "nada encontrado" | 12/16 (75%) | 12/16 (75%) |
| Com resposta que viraram "nada encontrado" por engano | 5/44 (11%) | 5/44 (11%) |
| Dados pessoais enviados para os embeddings | 0 de 8 | 0 de 8 |
| Perguntas que caíram para a busca por palavras | 0 | 0 |

Conferência que não depende do Google: dados pessoais que sobraram no texto mascarado, que é o texto que vai para os embeddings: 0 de 8.

Como ler: "respondidas e certas" é a medida que importa para o agente: a busca passou do limiar e entregou o artigo certo entre os 3 que ele vai ler. O acerto no 1º lugar e entre os 3 primeiros olha a ordem dos artigos antes do limiar, só nas perguntas com resposta. As duas linhas de "nada encontrado" mostram o efeito do limiar: barrar as sem resposta é o certo; barrar uma com resposta faz o agente chamar uma pessoa sem precisar.

## Onde errou: por sentido

| Pergunta | Gabarito | 1º lugar | Nota | Nada encontrado |
|---|---|---|---|---|
| a09 | conexao | conexao | 0.6802 | sim |
| a11 | extrato-e-taxas | extrato-e-taxas | 0.6916 | sim |
| a15 | maquininha-nao-liga | maquininha-nao-le-cartao | 0.7231 | não |
| a19 | (sem resposta) | conta-de-recebimento | 0.729 | não |
| a25 | maquininha-perdida-ou-roubada | maquininha-nao-le-cartao | 0.7419 | não |
| a28 | golpe-sms-link-falso | dinheiro-nao-caiu | 0.6752 | sim |
| a33 | (sem resposta) | taxas-e-mudanca-de-plano | 0.7345 | não |
| a46 | (sem resposta) | extrato-e-taxas | 0.7417 | não |
| a47 | troca-e-garantia | troca-e-garantia | 0.7057 | sim |
| a56 | troca-e-garantia | troca-e-garantia | 0.7054 | sim |
| a59 | (sem resposta) | encerrar-a-conta | 0.776 | não |

## Onde errou: híbrida

| Pergunta | Gabarito | 1º lugar | Nota | Nada encontrado |
|---|---|---|---|---|
| a09 | conexao | troca-e-garantia | 0.6802 | sim |
| a11 | extrato-e-taxas | extrato-e-taxas | 0.6916 | sim |
| a14 | desistir-da-compra | cancelar-uma-venda | 0.8411 | não |
| a15 | maquininha-nao-liga | maquininha-perdida-ou-roubada | 0.7231 | não |
| a19 | (sem resposta) | antecipacao | 0.729 | não |
| a25 | maquininha-perdida-ou-roubada | conexao | 0.7419 | não |
| a28 | golpe-sms-link-falso | dinheiro-nao-caiu | 0.6752 | sim |
| a33 | (sem resposta) | taxas-e-mudanca-de-plano | 0.7345 | não |
| a46 | (sem resposta) | abrir-cadastro | 0.7417 | não |
| a47 | troca-e-garantia | troca-e-garantia | 0.7057 | sim |
| a50 | cancelar-uma-venda | antecipacao | 0.7774 | não |
| a52 | horarios-e-canais | nunca-pedimos-sua-senha | 0.7395 | não |
| a56 | troca-e-garantia | troca-e-garantia | 0.7054 | sim |
| a59 | (sem resposta) | conta-de-recebimento | 0.776 | não |
