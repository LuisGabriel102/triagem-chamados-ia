# Avaliação da busca na base de conhecimento

Rodada em 13/11/2026 11:48 UTC. Base: 30 artigos (`base/artigos/`). Perguntas: 48 (`avaliacao/perguntas_busca.jsonl`), 40 com o artigo certo no gabarito e 8 sem resposta na base.

> **Ressalva:** As perguntas foram escritas junto com a base, pela mesma pessoa que escreveu os artigos. Com perguntas de lojistas de verdade, o resultado tende a ser pior.

- Busca por sentido: pela chave do Google AI Studio, modelo gemini-embedding-2, 768 dimensões.
- Limiar do BM25: 6.2882 (base/limiares.json, calibrado em 2026-11-13).
- Limiar da similaridade: 0.7108 (base/limiares.json (gemini-embedding-2, 768 dimensões), calibrado em 2026-11-13).

| Medida | Por palavras | Por sentido | Híbrida |
|---|---|---|---|
| **Respondidas e certas** (acima do limiar e com o artigo certo entre os 3) | 23/40 (57%) | 37/40 (92%) | 34/40 (85%) |
| Acerto no 1º lugar | 24/40 (60%) | 40/40 (100%) | 33/40 (82%) |
| Acerto entre os 3 primeiros | 32/40 (80%) | 40/40 (100%) | 36/40 (90%) |
| Sem resposta que ficaram em "nada encontrado" | 7/8 (88%) | 8/8 (100%) | 8/8 (100%) |
| Com resposta que viraram "nada encontrado" por engano | 17/40 (42%) | 3/40 (8%) | 3/40 (8%) |
| Dados pessoais enviados para os embeddings | não se aplica (nada vai para o Google) | 0 de 8 | 0 de 8 |
| Perguntas que caíram para a busca por palavras | 0 | 0 | 0 |

Conferência que não depende do Google: dados pessoais que sobraram no texto mascarado, que é o texto que vai para os embeddings: 0 de 8.

Como ler: "respondidas e certas" é a medida que importa para o agente: a busca passou do limiar e entregou o artigo certo entre os 3 que ele vai ler. O acerto no 1º lugar e entre os 3 primeiros olha a ordem dos artigos antes do limiar, só nas perguntas com resposta. As duas linhas de "nada encontrado" mostram o efeito do limiar: barrar as sem resposta é o certo; barrar uma com resposta faz o agente chamar uma pessoa sem precisar.

## Onde errou: por palavras

| Pergunta | Gabarito | 1º lugar | Nota | Nada encontrado |
|---|---|---|---|---|
| b03 | dinheiro-nao-caiu | dinheiro-nao-caiu | 4.6983 | sim |
| b04 | conta-de-recebimento | taxas-e-mudanca-de-plano | 4.9662 | sim |
| b05 | antecipacao | antecipacao | 3.9215 | sim |
| b06 | antecipacao | parcelado | 8.6128 | não |
| b07 | extrato-e-taxas | antecipacao | 4.5306 | sim |
| b08 | maquininha-nao-liga | aproximacao | 4.1456 | sim |
| b10 | bobina | — | 0 | sim |
| b14 | maquininha-perdida-ou-roubada | maquininha-nao-liga | 4.8162 | sim |
| b15 | maquininha-perdida-ou-roubada | recebimentos-e-prazos | 2.9776 | sim |
| b17 | troca-e-garantia | cancelar-uma-venda | 1.9449 | sim |
| b18 | cancelar-uma-venda | extrato-e-taxas | 3.5106 | sim |
| b19 | cancelar-uma-venda | contestacao | 5.4278 | sim |
| b20 | estorno | desistir-da-compra | 4.5167 | sim |
| b23 | contestacao | contestacao | 4.5328 | sim |
| b26 | pix-na-maquininha | pix-na-maquininha | 5.5245 | sim |
| b27 | pix-na-maquininha | estorno | 9.9769 | não |
| b29 | maquininha-a-mais | maquininha-nao-liga | 5.3355 | sim |
| b33 | alterar-dados | acesso-ao-app | 9.1146 | não |
| b35 | desistir-da-compra | pix-na-maquininha | 4.3416 | sim |
| b36 | venda-recusada | venda-recusada | 5.012 | sim |
| b38 | ouvidoria | horarios-e-canais | 8.1624 | não |
| b44 | (sem resposta) | contestacao | 7.9912 | não |

## Onde errou: por sentido

| Pergunta | Gabarito | 1º lugar | Nota | Nada encontrado |
|---|---|---|---|---|
| b10 | bobina | bobina | 0.7098 | sim |
| b13 | conexao | conexao | 0.6934 | sim |
| b17 | troca-e-garantia | troca-e-garantia | 0.7104 | sim |

## Onde errou: híbrida

| Pergunta | Gabarito | 1º lugar | Nota | Nada encontrado |
|---|---|---|---|---|
| b10 | bobina | bobina | 0.7098 | sim |
| b13 | conexao | conexao | 0.6934 | sim |
| b14 | maquininha-perdida-ou-roubada | maquininha-nao-liga | 0.8114 | não |
| b15 | maquininha-perdida-ou-roubada | recebimentos-e-prazos | 0.7972 | não |
| b17 | troca-e-garantia | cancelar-uma-venda | 0.7104 | sim |
| b18 | cancelar-uma-venda | extrato-e-taxas | 0.7887 | não |
| b19 | cancelar-uma-venda | contestacao | 0.7895 | não |
| b33 | alterar-dados | acesso-ao-app | 0.7739 | não |
| b35 | desistir-da-compra | cancelar-uma-venda | 0.8416 | não |
