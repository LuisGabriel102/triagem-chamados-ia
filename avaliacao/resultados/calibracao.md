# Calibração dos limiares de "nada encontrado"

Rodada em 13/11/2026 11:19 UTC.
Perguntas: 20 (`avaliacao/perguntas_calibracao.jsonl`), 14 com resposta na base e 6 sem. São outras perguntas, não as da avaliação.

Regra: para cada pergunta, pega a nota do artigo mais parecido. O limiar escolhido é o que deixa passar o maior número de perguntas com resposta e barra o maior número das sem resposta, pesando os dois grupos igualmente. No empate, fica o do meio.

> Ressalva: As perguntas foram escritas junto com a base, pela mesma pessoa que escreveu os artigos. Com perguntas de lojistas de verdade, o resultado tende a ser pior. Com tão poucas perguntas, o limiar é uma primeira estimativa.

| Critério | Limiar | Com resposta que passam | Sem resposta barradas |
|---|---|---|---|
| Nota do BM25 (busca por palavras) | 6.2882 | 10/14 | 6/6 |
| Similaridade (busca por sentido) | não rodou (falta a GEMINI_API_KEY ou o GOOGLE_CLOUD_PROJECT no .env) | — | — |

## Nota de cada pergunta

| Pergunta | Tem resposta | Nota do BM25 | Similaridade |
|---|---|---|---|
| c01 | sim | 8.3222 | — |
| c02 | sim | 3.0123 | — |
| c03 | sim | 6.7586 | — |
| c04 | sim | 8.415 | — |
| c05 | sim | 10.0186 | — |
| c06 | sim | 9.966 | — |
| c07 | sim | 3.0958 | — |
| c08 | sim | 11.6954 | — |
| c09 | sim | 6.4585 | — |
| c10 | sim | 6.3475 | — |
| c11 | sim | 4.8269 | — |
| c12 | sim | 4.1376 | — |
| c13 | sim | 10.1251 | — |
| c14 | sim | 9.3869 | — |
| c15 | não | 6.229 | — |
| c16 | não | 2.7486 | — |
| c17 | não | 2.5803 | — |
| c18 | não | 2.6135 | — |
| c19 | não | 0 | — |
| c20 | não | 4.0135 | — |
