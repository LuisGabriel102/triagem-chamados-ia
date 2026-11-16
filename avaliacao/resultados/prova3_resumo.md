# Prova 3 (versão 2, conferência frase a frase): 3 rodadas

Rodadas terminadas em 16/11/2026 13:35 UTC, com IA de verdade, as mesmas perguntas (`avaliacao/perguntas_prova3.jsonl`) e o mesmo código. A IA não responde sempre igual: a mediana é o número a citar; o menor e o maior mostram a variação.

> **Ressalva:** As perguntas foram escritas por um agente separado (Claude), que só viu o base/EMPRESA.md e não viu os artigos. O gabarito foi montado depois, por quem escreveu a base e o agente (também o Claude). A resposta certa é julgada por um modelo (Claude Sonnet 5.5), não por uma pessoa.

| Medida | Mediana | Menor | Maior | Em cada rodada |
|---|---|---|---|---|
| **Resolvido sem uma pessoa E certo** (o número principal) | 11/23 | 9/23 | 14/23 | 11, 9, 14 |
| **Resolvido sem uma pessoa e errado** (o número perigoso) | 5/40 | 4/40 | 7/40 | 5, 4, 7 |
| Resolvido sem uma pessoa (certo ou não) | 14/23 | 12/23 | 18/23 | 14, 12, 18 |
| Resposta certa (juiz, rubrica nova), nas que a base responde | 19/29 | 17/29 | 20/29 | 19, 20, 17 |
| Resposta certa (juiz, rubrica antiga), nas que a base responde | 18/29 | 17/29 | 20/29 | 18, 20, 17 |
| "Não sei" certo nas sem resposta | 6/7 | 6/7 | 7/7 | 6, 7, 6 |
| Sem resposta em que inventou | 0 | 0 | 2 | 0, 0, 2 |
| Chamou uma pessoa nas urgentes e nas tentativas | 8/8 | 8/8 | 8/8 | 8, 8, 8 |
| Respostas com instrução que citam artigo | 36 | 35 | 36 | 36/36, 35/35, 36/36 |
| Fila certa | 30/40 | 28/40 | 30/40 | 28, 30, 30 |
| Dados pessoais enviados à IA | 0 | 0 | 0 | 0, 0, 0 |
| Dados pessoais enviados aos embeddings | 0 | 0 | 0 | 0, 0, 0 |
| Respostas conferidas frase a frase | 23 | 22 | 23 | 23, 22, 23 |
| ... em que a conferência tirou frase | 12 | 8 | 12 | 12, 12, 8 |
| ... em que a conferência chamou uma pessoa | 7 | 1 | 9 | 7, 9, 1 |
| ... em que o agente refez a resposta | 12 | 8 | 12 | 12, 12, 8 |
| ... em que a resposta refeita ainda tinha frase sem apoio | 7 | 1 | 9 | 7, 9, 1 |
| Custo médio por mensagem (US$) | 0.001180 | 0.001135 | 0.001182 | 0.001180, 0.001182, 0.001135 |
| Custo médio da conferência, nas conferidas (US$) | 0.000508 | 0.000459 | 0.000524 | 0.000508, 0.000524, 0.000459 |
| Tempo médio por mensagem (ms) | 8866 | 8355 | 8900 | 8866, 8900, 8355 |
| Tempo médio da conferência, nas conferidas (ms) | 3101 | 2741 | 3295 | 3295, 3101, 2741 |
| O juiz não julgou | 0 | 0 | 0 | 0, 0, 0 |
| Custo do juiz por rodada (US$) | 0.3233 | 0.3173 | 0.3239 | 0.3239, 0.3173, 0.3233 |
| Custo por mensagem: a triagem (US$) | 0.000264 | 0.000264 | 0.000265 | 0.000265, 0.000264, 0.000264 |
| Custo por mensagem: a busca (US$) | 0.000015 | 0.000015 | 0.000015 | 0.000015, 0.000015, 0.000015 |
| Custo por mensagem: a resposta (US$) | 0.000450 | 0.000449 | 0.000465 | 0.000449, 0.000450, 0.000465 |
| Custo por mensagem: a conferência (US$) | 0.000288 | 0.000264 | 0.000292 | 0.000292, 0.000288, 0.000264 |
| Custo por mensagem: a resposta refeita (US$) | 0.000159 | 0.000127 | 0.000166 | 0.000159, 0.000166, 0.000127 |
| Tempo por mensagem: a triagem (ms) | 3413 | 3368 | 3512 | 3413, 3512, 3368 |
| Tempo por mensagem: a busca (ms) | 636 | 616 | 677 | 616, 636, 677 |
| Tempo por mensagem: a resposta (ms) | 2718 | 2669 | 2723 | 2669, 2718, 2723 |
| Tempo por mensagem: a conferência (ms) | 1706 | 1576 | 1895 | 1895, 1706, 1576 |
| Tempo por mensagem: a resposta refeita (ms) | 885 | 684 | 961 | 885, 961, 684 |
| Blocos de raciocínio: triagem | 0 | 0 | 0 | 0, 0, 0 |
| Blocos de raciocínio: agente | 0 | 0 | 0 | 0, 0, 0 |
| Blocos de raciocínio: conferencia | 0 | 0 | 0 | 0, 0, 0 |
| Blocos de raciocínio: juiz | 0 | 0 | 1 | 1, 0, 0 |
| Chamou uma pessoa (todas) | 24 | 19 | 27 | 24, 27, 19 |
| Chamou uma pessoa sem precisar | 9 | 5 | 11 | 9, 11, 5 |
| Motivo: Urgente (triagem ou palavras-chave) | 7 | 6 | 7 | 7, 7, 6 |
| Motivo: Tema de segurança | 2 | 2 | 2 | 2, 2, 2 |
| Motivo: Tentativa de enganar | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: Reclamação (Ouvidoria) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: Nada encontrado na busca | 6 | 6 | 6 | 6, 6, 6 |
| Motivo: Sem fonte (não citou artigo, ou citou artigo de fora) | 0 | 0 | 1 | 0, 1, 0 |
| Motivo: A conferência frase a frase reprovou ou falhou | 7 | 1 | 9 | 7, 9, 1 |
| Motivo: A IA pediu uma pessoa | 12 | 11 | 12 | 11, 12, 12 |
| Motivo: Confiança baixa do agente (abaixo de 0,75) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: A IA falhou (plano B) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: Dado pessoal na resposta da IA | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: Outro | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Urgente (triagem ou palavras-chave) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Tema de segurança | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Tentativa de enganar | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Reclamação (Ouvidoria) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Nada encontrado na busca | 1 | 1 | 1 | 1, 1, 1 |
| Motivo, nas que chamaram sem precisar: Sem fonte (não citou artigo, ou citou artigo de fora) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: A conferência frase a frase reprovou ou falhou | 6 | 1 | 8 | 6, 8, 1 |
| Motivo, nas que chamaram sem precisar: A IA pediu uma pessoa | 2 | 2 | 3 | 2, 2, 3 |
| Motivo, nas que chamaram sem precisar: Confiança baixa do agente (abaixo de 0,75) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: A IA falhou (plano B) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Dado pessoal na resposta da IA | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Outro | 0 | 0 | 0 | 0, 0, 0 |
