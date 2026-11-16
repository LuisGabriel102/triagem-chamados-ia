# Conjunto de prova (etapa 3B): 3 rodadas

Rodadas terminadas em 13/11/2026 14:32 UTC, com IA de verdade, as mesmas perguntas (`avaliacao/perguntas_prova.jsonl`) e o mesmo código. A IA não responde sempre igual: a mediana é o número a citar; o menor e o maior mostram a variação.

> **Ressalva:** As perguntas foram escritas por um agente separado (Claude), que só viu o base/EMPRESA.md e não viu os artigos. O gabarito foi montado depois, por quem escreveu a base e o agente (também o Claude). A resposta certa é julgada por um modelo (Claude Sonnet 5.5), não por uma pessoa.

| Medida | Mediana | Menor | Maior | Em cada rodada |
|---|---|---|---|---|
| **Resolvido sem uma pessoa E certo** (o número principal) | 10/24 | 9/24 | 11/24 | 11, 9, 10 |
| **Resolvido sem uma pessoa e errado** (o número perigoso) | 3/40 | 2/40 | 4/40 | 2, 4, 3 |
| Resolvido sem uma pessoa (certo ou não) | 13/24 | 13/24 | 13/24 | 13, 13, 13 |
| Resposta certa (juiz), nas que a base responde | 14/29 | 13/29 | 14/29 | 14, 13, 14 |
| "Não sei" certo nas sem resposta | 7/7 | 7/7 | 7/7 | 7, 7, 7 |
| Sem resposta em que inventou | 0 | 0 | 0 | 0, 0, 0 |
| Chamou uma pessoa nas urgentes e nas tentativas | 8/8 | 8/8 | 8/8 | 8, 8, 8 |
| Respostas com instrução que citam artigo | 31 | 30 | 31 | 31/31, 31/31, 30/30 |
| Fila certa | 34/40 | 33/40 | 34/40 | 34, 33, 34 |
| Dados pessoais enviados à IA | 0 | 0 | 0 | 0, 0, 0 |
| Dados pessoais enviados aos embeddings | 0 | 0 | 0 | 0, 0, 0 |
| Respostas conferidas frase a frase | 13 | 13 | 13 | 13, 13, 13 |
| ... em que a conferência tirou frase | 4 | 2 | 4 | 4, 2, 4 |
| ... em que sobrou pouco e chamou uma pessoa | 0 | 0 | 0 | 0, 0, 0 |
| Custo médio por mensagem (US$) | 0.000755 | 0.000750 | 0.000791 | 0.000791, 0.000750, 0.000755 |
| Custo médio da conferência, nas conferidas (US$) | 0.000264 | 0.000256 | 0.000286 | 0.000286, 0.000256, 0.000264 |
| Tempo médio por mensagem (ms) | 5289 | 5275 | 5300 | 5275, 5289, 5300 |
| Tempo médio da conferência, nas conferidas (ms) | 1686 | 1606 | 1710 | 1710, 1606, 1686 |
| O juiz não julgou | 0 | 0 | 0 | 0, 0, 0 |
| Custo do juiz por rodada (US$) | 0.2164 | 0.2121 | 0.2257 | 0.2257, 0.2164, 0.2121 |
| Custo por mensagem: a triagem (US$) | 0.000254 | 0.000254 | 0.000260 | 0.000260, 0.000254, 0.000254 |
| Custo por mensagem: a busca (US$) | 0.000008 | 0.000008 | 0.000008 | 0.000008, 0.000008, 0.000008 |
| Custo por mensagem: a resposta (US$) | 0.000407 | 0.000405 | 0.000430 | 0.000430, 0.000405, 0.000407 |
| Custo por mensagem: a conferência (US$) | 0.000086 | 0.000083 | 0.000093 | 0.000093, 0.000083, 0.000086 |
| Tempo por mensagem: a triagem (ms) | 2477 | 2456 | 2494 | 2456, 2477, 2494 |
| Tempo por mensagem: a busca (ms) | 555 | 552 | 570 | 552, 555, 570 |
| Tempo por mensagem: a resposta (ms) | 2260 | 2256 | 2287 | 2260, 2287, 2256 |
| Tempo por mensagem: a conferência (ms) | 548 | 522 | 556 | 556, 522, 548 |
| Blocos de raciocínio: triagem | 0 | 0 | 0 | 0, 0, 0 |
| Blocos de raciocínio: agente | 0 | 0 | 0 | 0, 0, 0 |
| Blocos de raciocínio: conferencia | 0 | 0 | 0 | 0, 0, 0 |
| Blocos de raciocínio: juiz | 0 | 0 | 0 | 0, 0, 0 |
| Chamou uma pessoa (todas) | 27 | 27 | 27 | 27, 27, 27 |
| Chamou uma pessoa sem precisar | 11 | 11 | 11 | 11, 11, 11 |
| Motivo: Urgente (triagem ou palavras-chave) | 9 | 9 | 10 | 9, 10, 9 |
| Motivo: Tema de segurança | 1 | 1 | 1 | 1, 1, 1 |
| Motivo: Tentativa de enganar | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: Reclamação (Ouvidoria) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: Nada encontrado na busca | 10 | 10 | 10 | 10, 10, 10 |
| Motivo: Sem fonte (não citou artigo, ou citou artigo de fora) | 1 | 0 | 2 | 0, 1, 2 |
| Motivo: A conferência frase a frase reprovou ou falhou | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: A IA pediu uma pessoa | 13 | 11 | 13 | 11, 13, 13 |
| Motivo: Confiança baixa do agente (abaixo de 0,75) | 9 | 8 | 9 | 9, 8, 9 |
| Motivo: A IA falhou (plano B) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: Dado pessoal na resposta da IA | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: Outro | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Urgente (triagem ou palavras-chave) | 2 | 2 | 3 | 2, 3, 2 |
| Motivo, nas que chamaram sem precisar: Tema de segurança | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Tentativa de enganar | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Reclamação (Ouvidoria) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Nada encontrado na busca | 2 | 2 | 2 | 2, 2, 2 |
| Motivo, nas que chamaram sem precisar: Sem fonte (não citou artigo, ou citou artigo de fora) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: A conferência frase a frase reprovou ou falhou | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: A IA pediu uma pessoa | 6 | 5 | 6 | 5, 6, 6 |
| Motivo, nas que chamaram sem precisar: Confiança baixa do agente (abaixo de 0,75) | 6 | 5 | 6 | 6, 5, 6 |
| Motivo, nas que chamaram sem precisar: A IA falhou (plano B) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Dado pessoal na resposta da IA | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Outro | 0 | 0 | 0 | 0, 0, 0 |
