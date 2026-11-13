# Prova 2 (etapa 3C, versão 2): 3 rodadas

Rodadas terminadas em 13/11/2026 16:04 UTC, com IA de verdade, as mesmas perguntas (`avaliacao/perguntas_prova2.jsonl`) e o mesmo código. A IA não responde sempre igual: a mediana é o número a citar; o menor e o maior mostram a variação.

> **Ressalva:** As perguntas foram escritas por um agente separado (Claude), que só viu o base/EMPRESA.md e não viu os artigos. O gabarito foi montado depois, por quem escreveu a base e o agente (também o Claude). A resposta certa é julgada por um modelo (Claude Sonnet 5.5), não por uma pessoa.

| Medida | Mediana | Menor | Maior | Em cada rodada |
|---|---|---|---|---|
| **Resolvido sem uma pessoa E certo** (o número principal) | 11/21 | 11/21 | 11/21 | 11, 11, 11 |
| **Resolvido sem uma pessoa e errado** (o número perigoso) | 2/40 | 1/40 | 2/40 | 2, 2, 1 |
| Resolvido sem uma pessoa (certo ou não) | 12/21 | 11/21 | 13/21 | 13, 12, 11 |
| Resposta certa (juiz, rubrica nova), nas que a base responde | 17/28 | 15/28 | 19/28 | 17, 15, 19 |
| Resposta certa (juiz, rubrica antiga), nas que a base responde | 17/28 | 13/28 | 17/28 | 17, 13, 17 |
| "Não sei" certo nas sem resposta | 8/8 | 8/8 | 8/8 | 8, 8, 8 |
| Sem resposta em que inventou | 0 | 0 | 0 | 0, 0, 0 |
| Chamou uma pessoa nas urgentes e nas tentativas | 8/8 | 8/8 | 8/8 | 8, 8, 8 |
| Respostas com instrução que citam artigo | 27/27 | 27/27 | 27/27 | 27, 27, 27 |
| Fila certa | 32/40 | 31/40 | 35/40 | 32, 35, 31 |
| Dados pessoais enviados à IA | 0 | 0 | 0 | 0, 0, 0 |
| Dados pessoais enviados aos embeddings | 0 | 0 | 0 | 0, 0, 0 |
| Respostas conferidas frase a frase | 16 | 16 | 16 | 16, 16, 16 |
| ... em que a conferência tirou frase | 5 | 5 | 7 | 7, 5, 5 |
| ... em que a conferência chamou uma pessoa | 2 | 1 | 4 | 1, 2, 4 |
| ... em que o agente refez a resposta | 5 | 5 | 7 | 7, 5, 5 |
| ... em que a resposta refeita ainda tinha frase sem apoio | 2 | 1 | 4 | 1, 2, 4 |
| Custo médio por mensagem (US$) | 0.000908 | 0.000886 | 0.000923 | 0.000923, 0.000886, 0.000908 |
| Custo médio da conferência, nas conferidas (US$) | 0.000437 | 0.000415 | 0.000448 | 0.000437, 0.000415, 0.000448 |
| Tempo médio por mensagem (ms) | 6254 | 6087 | 6369 | 6254, 6087, 6369 |
| Tempo médio da conferência, nas conferidas (ms) | 2518 | 2314 | 2527 | 2527, 2314, 2518 |
| O juiz não julgou | 0 | 0 | 0 | 0, 0, 0 |
| Custo do juiz por rodada (US$) | 0.2540 | 0.2539 | 0.2550 | 0.2550, 0.2540, 0.2539 |
| Custo por mensagem: a triagem (US$) | 0.000254 | 0.000253 | 0.000254 | 0.000254, 0.000253, 0.000254 |
| Custo por mensagem: a busca (US$) | 0.000007 | 0.000007 | 0.000007 | 0.000007, 0.000007, 0.000007 |
| Custo por mensagem: a resposta (US$) | 0.000375 | 0.000374 | 0.000382 | 0.000375, 0.000374, 0.000382 |
| Custo por mensagem: a conferência (US$) | 0.000175 | 0.000166 | 0.000179 | 0.000175, 0.000166, 0.000179 |
| Custo por mensagem: a resposta refeita (US$) | 0.000086 | 0.000085 | 0.000112 | 0.000112, 0.000086, 0.000085 |
| Tempo por mensagem: a triagem (ms) | 2686 | 2651 | 2748 | 2651, 2686, 2748 |
| Tempo por mensagem: a busca (ms) | 723 | 684 | 726 | 684, 726, 723 |
| Tempo por mensagem: a resposta (ms) | 2074 | 2036 | 2179 | 2074, 2036, 2179 |
| Tempo por mensagem: a conferência (ms) | 1007 | 925 | 1011 | 1011, 925, 1007 |
| Tempo por mensagem: a resposta refeita (ms) | 436 | 431 | 515 | 515, 436, 431 |
| Blocos de raciocínio: triagem | 0 | 0 | 0 | 0, 0, 0 |
| Blocos de raciocínio: agente | 0 | 0 | 0 | 0, 0, 0 |
| Blocos de raciocínio: conferencia | 0 | 0 | 0 | 0, 0, 0 |
| Blocos de raciocínio: juiz | 0 | 0 | 0 | 0, 0, 0 |
| Chamou uma pessoa (todas) | 27 | 27 | 28 | 27, 27, 28 |
| Chamou uma pessoa sem precisar | 9 | 8 | 10 | 8, 9, 10 |
| Motivo: Urgente (triagem ou palavras-chave) | 8 | 8 | 8 | 8, 8, 8 |
| Motivo: Tema de segurança | 2 | 2 | 2 | 2, 2, 2 |
| Motivo: Tentativa de enganar | 3 | 3 | 3 | 3, 3, 3 |
| Motivo: Reclamação (Ouvidoria) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: Nada encontrado na busca | 10 | 10 | 10 | 10, 10, 10 |
| Motivo: Sem fonte (não citou artigo, ou citou artigo de fora) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: A conferência frase a frase reprovou ou falhou | 2 | 2 | 4 | 2, 2, 4 |
| Motivo: A IA pediu uma pessoa | 10 | 9 | 10 | 10, 10, 9 |
| Motivo: Confiança baixa do agente (abaixo de 0,75) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: A IA falhou (plano B) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: Dado pessoal na resposta da IA | 0 | 0 | 0 | 0, 0, 0 |
| Motivo: Outro | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Urgente (triagem ou palavras-chave) | 2 | 2 | 2 | 2, 2, 2 |
| Motivo, nas que chamaram sem precisar: Tema de segurança | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Tentativa de enganar | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Reclamação (Ouvidoria) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Nada encontrado na busca | 2 | 2 | 2 | 2, 2, 2 |
| Motivo, nas que chamaram sem precisar: Sem fonte (não citou artigo, ou citou artigo de fora) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: A conferência frase a frase reprovou ou falhou | 2 | 2 | 4 | 2, 2, 4 |
| Motivo, nas que chamaram sem precisar: A IA pediu uma pessoa | 3 | 3 | 4 | 3, 4, 3 |
| Motivo, nas que chamaram sem precisar: Confiança baixa do agente (abaixo de 0,75) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: A IA falhou (plano B) | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Dado pessoal na resposta da IA | 0 | 0 | 0 | 0, 0, 0 |
| Motivo, nas que chamaram sem precisar: Outro | 0 | 0 | 0 | 0, 0, 0 |
