# Atendimento com IA

Hoje a triagem decide para onde vai a mensagem. A versão nova responde sozinha o que der,
mostrando de onde tirou a resposta, e chama uma pessoa quando precisa. O tema é o lojista
com maquininha de cartão, numa empresa **inventada**: a Tapiri Pagamentos
(`base/EMPRESA.md`). Os prazos, as taxas, os preços, os lojistas e as vendas são fictícios.

## As 5 etapas

| Etapa | O que entra | Estado |
|---|---|---|
| 1. Base de conhecimento e busca | 30 artigos, busca por palavras (BM25), busca por sentido (embeddings do Gemini), fusão, limiar de "nada encontrado", avaliação da busca | **Pronta e medida** com o Google de verdade. |
| 2. O agente | Responde com a fonte, consulta dados inventados e chama uma pessoa; rota `POST /atendimento` | **Pronta.** |
| 3. A avaliação completa | 4 consertos da fumaça; 60 perguntas novas e independentes; a escolha da busca; o agente inteiro com um juiz | **Pronta.** Duas rodadas (a 2ª depois de consertar um defeito achado na 1ª). |
| 3B. Resolvido sem pessoa, com segurança | A triagem só para a fila e a urgência; conferência frase a frase; mensagem fixa de urgência; o número "resolvido sem uma pessoa E certo"; um conjunto de prova novo | **Pronta e medida.** A prova rodou 3 vezes e as 60 uma vez, com IA de verdade. Resolvido sem uma pessoa E certo: 10/24 na prova (mediana), 19/35 nas 60 (etapa 3: 12/35). |
| 4. A página e a publicação | Conversa no celular e no computador; pgvector no banco | Não começou. Lembrete: o Dockerfile de hoje copia só `app/`; `base/` e `dados/` vão precisar entrar na imagem. Até lá, a API sobe sem o atendimento e a rota responde 503. |
| 5. Opcional | O Gemini no Vertex AI comparado com o Claude | Não começou |

Nada desta frente foi publicado. O trabalho está na branch `atendimento`, só no computador.

## Resultado em uma tabela (pronta para o README)

Avaliação completa de 13/11/2026, rodada 2 (`avaliacao/resultados/agente_rodada2.md`), com
IA de verdade. Entre parênteses, a rodada 1.

| Atendimento com IA (60 perguntas novas) | Resultado |
|---|---|
| Resolvido sem uma pessoa, nas que deviam | 13/35 (rodada 1: 14/35) |
| Resposta certa, pelo juiz | 26/44 (28/44) |
| Chamou uma pessoa nas urgentes e nas tentativas de enganar | 10/10 (10/10) |
| "Não sei" certo nas sem resposta | 10/11 (11/11) |
| Sem resposta em que inventou | 1 (0) |
| Respostas com instrução que citam artigo | 42/42 (42/42) |
| Dados pessoais enviados à IA e aos embeddings | 0 de 8 (0 de 8) |
| Custo médio por mensagem | US$ 0,00055 (US$ 0,00061) |
| Tempo médio por mensagem | 5,3 s (4,4 s) |

> **Ressalva:** as perguntas foram escritas por um agente separado (Claude), que só viu o
> `base/EMPRESA.md` e não viu os artigos. O gabarito foi montado depois, por quem escreveu a
> base e o agente (também o Claude). A resposta certa é julgada por um modelo (Claude Sonnet
> 5.5), não por uma pessoa; conferi o juiz em 10 casos e concordo em 9.

**O que limita o "resolvido sem uma pessoa":** a triagem. Em 17 das 21 vezes em que a rodada 1
chamou uma pessoa sem precisar, um dos motivos foi a triagem, que dá confiança de 0,6 ou 0,7
nas mensagens de lojista (o limite é 0,75); em 12 delas, foi o único motivo. A regra da etapa 2
manda chamar uma pessoa quando a triagem marca revisão, e ela não foi mudada.

## Etapa 1: como a busca funciona

1. **Mascaramento primeiro (LGPD).** A pergunta passa pelo `app/mascaramento.py` antes de
   qualquer coisa. Só o texto mascarado vira vetor.
2. **Busca por palavras** (`app/busca_palavras.py`). BM25 em Python puro: minúsculas, sem
   acento, sem palavras vazias, com uma redução simples de plural.
3. **Busca por sentido** (`app/busca_sentido.py`). Embeddings do Gemini (`gemini-embedding-2`,
   768 dimensões), com a tarefa escrita no próprio texto, como a documentação do Google manda:
   `task: search result | query: {texto}` na pergunta e `title: {título} | text: {texto}` no
   artigo. Os vetores dos artigos ficam em `base/indice.json`; o cosseno roda na memória; a
   interface `IndiceVetores` está pronta para o pgvector.
4. **Fusão** (`app/busca.py`, busca híbrida). Os dois rankings se juntam pela posição (RRF,
   k = 60). O artigo cuja nota passou do limiar sempre vai entre os 3 entregues (conserto 4).
5. **Limiar.** Abaixo dele, "nada encontrado". Com a busca por sentido, vale a similaridade;
   sem ela, a nota do BM25. Os limiares ficam em `base/limiares.json` (versionado, com a data e
   o conjunto de calibração); `LIMIAR_BM25` e `LIMIAR_SIMILARIDADE` no ambiente só sobrescrevem.

| Limiar | Valor | Com resposta que passam | Sem resposta barradas |
|---|---|---|---|
| Nota do BM25 | 6,2882 | 10/14 | 6/6 |
| Similaridade (gemini-embedding-2, 768) | 0,7108 | 13/14 | 6/6 |

Os dois saem de 20 perguntas de calibração (`avaliacao/perguntas_calibracao.jsonl`), nunca
das perguntas de avaliação.

## Etapa 2: o agente

### O fluxo de cada mensagem (`app/atendimento.py`)

1. **Mascara a mensagem.** Daqui em diante, só o texto mascarado circula.
2. **Triagem e busca ao mesmo tempo.** A triagem do atendimento usa a descrição da Tapiri
   (`base/EMPRESA.md`); a de `/chamados` continua com o negócio padrão. A busca é a **por
   sentido** (escolhida na etapa 3); se o Google cair, segue por palavras.
3. **Quem responde:** tentativa de mandar na IA ou de pedir dado de outra loja recebe uma
   resposta fixa, sem IA; "nada encontrado" recebe "não sei"; senão, o **Claude Haiku 5.5**
   responde pela ferramenta `responder_lojista`, em modo estrito, depois de no máximo 3
   consultas aos dados do lojista. O texto fixo vai para o cache; nenhuma chamada usa
   temperature; nada de modo de raciocínio.
4. **As datas vêm prontas** (`app/datas.py`): as ferramentas devolvem as datas com o dia da
   semana ("segunda, 16/11/2026") e um "quando" já calculado; os dias úteis são contados em
   Python, pelas regras do plano. A mensagem leva a data de hoje e os prazos a partir de hoje,
   fora do texto que vai para o cache. A IA não faz conta de data.
5. **A conferência:** artigo citado que não veio da busca não vale (plano B); **sem fonte, sem
   conselho**: resposta que não cita artigo da busca vira a mensagem fixa de espera, mesmo
   quando a IA chama uma pessoa; a resposta passa de novo pelo mascaramento (os e-mails da
   própria empresa ficam); se a IA pede uma pessoa ou tem confiança abaixo de 0,75, vai para
   uma pessoa.
6. **Segurança:** nos temas de roubo, golpe, link falso e senha, o primeiro passo do artigo
   vai sempre na resposta, mesmo quando chama uma pessoa ou quando a IA falha. Só vale quando
   a pergunta é mesmo do tema (cada artigo de segurança tem suas palavras de gatilho).
7. **O plano B:** se a IA falhar, a resposta é o trecho do artigo achado, com "Uma pessoa da
   nossa equipe vai confirmar". O atendimento nunca para.

Na etapa 2, ia para uma pessoa quando a triagem marcava revisão humana (urgente, confiança
baixa, "outros"), a busca dava "nada encontrado", era reclamação (fila da Ouvidoria), alguém
tentava enganar a IA, ou a IA pedia uma pessoa, falhava, citava artigo de fora, não citava artigo
ou tinha confiança baixa. **A etapa 3B mudou essa regra** (veja abaixo).

### As ferramentas e a rota

- `consultar_recebimentos` e `status_maquininha` (`app/ferramentas.py`, dados inventados em
  `dados/lojistas.json`): sem parâmetro; o lojista vem da sessão. A IA não recebe documento,
  conta, e-mail nem telefone. Três lojistas: `loja-001` (vendas para cair), `loja-002`
  (maquininha bloqueada) e `loja-003` (valor retido por contestação).
- `POST /atendimento`, com a chave `X-API-Key`. Recebe
  `{"mensagem": ..., "canal": "chat", "sessao": {"lojista_id": "loja-001"}}` e devolve a
  resposta, as fontes, a fila, se precisa de uma pessoa e por quê, o custo e o tempo (com o
  detalhe de triagem, busca e resposta). Grava só o texto mascarado.

## Etapa 3: os consertos e a avaliação completa

### Os 4 consertos da fumaça (um commit e um teste para cada)

1. **A triagem com o negócio configurável.** A descrição do negócio virou parâmetro. O padrão
   é o antigo, com o prompt idêntico ao de antes (um teste guarda a impressão digital); o
   atendimento usa a descrição da Tapiri. A avaliação dos 40 chamados, de novo com o padrão:

   | Medida | 04/11 | 13/11 |
   |---|---|---|
   | Categoria | 40/40 | 40/40 |
   | Prioridade | 38/40 | 37/40 |
   | Sentimento | 38/40 | 39/40 |
   | Os 4 campos certos | 36/40 | 36/40 |
   | Urgentes reconhecidos | 7/7 | 7/7 |
   | Revisão humana | 13/40 | 14/40 |
   | Liberados sem revisão e certos | 25/27 (93%) | 23/26 (88%) |

   Variação pequena; a única queda é nos liberados sem revisão e certos. Nada foi ajustado.
   Resultado: `avaliacao/resultados/reavaliacao_2026-11-13/`.
2. **As datas no código** (b01): veja o passo 4 do fluxo.
3. **Sem fonte, sem conselho** (b14 sugeria o Pix sem citar artigo): veja o passo 5.
4. **A maquininha roubada** (b14). **A causa foi a busca, não a IA:** a busca por sentido pôs o
   artigo certo em 1º (similaridade 0,81), mas na híbrida o BM25, que não liga "roubaram" a
   "roubada", o empurrou para fora dos 3 entregues. A busca decidia que achou por causa desse
   artigo e não o entregava. Agora ele sempre vai junto. E o primeiro passo de segurança entrou.

A fumaça das 10 perguntas, de novo depois dos consertos (`avaliacao/resultados/fumaca_atendimento.md`):
b01 acerta as datas, b14 abre com o bloqueio, b19 ensina a cancelar, b38 mostra o e-mail da
ouvidoria; 9 das 10 foram para uma pessoa, quase sempre pela triagem.

### As perguntas novas (`avaliacao/perguntas_agente.jsonl`)

Um agente separado escreveu 60 perguntas, sem ver os artigos: recebeu só o `base/EMPRESA.md`.
São 40 que a base deve responder, 10 que não responde, 5 tentativas de enganar e 5 urgentes,
8 delas com dado pessoal de teste. O gabarito veio depois, sem mudar as perguntas: os artigos
aceitos, se deve chamar uma pessoa e por quê, a fila, o lojista da sessão e o fato esperado nas
que usam dados. Uma pergunta que a base não cobre virou "sem resposta" (a a59). No total: 44 com
artigo, 11 sem resposta, 5 tentativas; 35 devem ser resolvidas sem uma pessoa.

### A escolha da busca (regra escrita antes)

Fica a que tiver mais "respondidas e certas" nas perguntas novas; no empate, a híbrida
(`avaliacao/resultados/busca_agente.md`):

| | Por sentido | Híbrida |
|---|---|---|
| Respondidas e certas | **39/44** | 37/44 |
| Artigo certo entre os 3 primeiros | 44/44 | 41/44 |
| Sem resposta (e tentativas) em "nada encontrado" | 12/16 | 12/16 |

**O agente passou a buscar por sentido.** O plano B por palavras continua para quando o Google cai.

### O agente inteiro (`avaliacao/avaliar_agente.py`)

Relógio fixo: sexta, 13/11/2026, 10h. O juiz é o Claude Sonnet 5.5, mais forte que o Haiku 5.5
que responde, sem temperature e com saída estruturada, com uma rubrica escrita antes de rodar:
correta, completa, fiel à fonte, sem inventar. As mensagens fixas ("não sei", espera, segurança)
não passam pelo juiz. Não há troca automática de modelo no juiz: trocar de juiz no meio de uma
avaliação misturaria critérios.

| Medida | Rodada 1 | Rodada 2 | O certo |
|---|---|---|---|
| **Resolvido sem uma pessoa** (o número principal) | **14/35** | **13/35** | o mais alto possível |
| ... e com a resposta certa | 12/35 | 12/35 | |
| Resposta certa (juiz), nas que a base responde | 28/44 | 26/44 | |
| "Não sei" certo nas sem resposta | 11/11 | 10/11 | 100% |
| Sem resposta em que inventou | 0 | 1 | 0 |
| Chamou uma pessoa nas urgentes e nas tentativas | 10/10 | 10/10 | 100% |
| Respostas com instrução que citam artigo | 42/42 | 42/42 | 100% |
| Fila certa | 49/60 | 48/60 | |
| Dados pessoais enviados à IA / aos embeddings | 0 / 0 de 8 | 0 / 0 de 8 | 0 |
| Custo por mensagem: média / pior | US$ 0,000606 / 0,001423 | US$ 0,000549 / 0,000983 | |
| Tempo por mensagem: média / pior | 4,4 s / 6,8 s | 5,3 s / 11,6 s | |
| Custo do juiz (fora do custo por mensagem) | US$ 0,27 | US$ 0,27 | |

**O defeito achado na rodada 1 (a25):** o lojista perguntou se a maquininha estava bloqueada
(ele mesmo a bloqueou) e a resposta abria com "Bloqueie a maquininha agora". O primeiro passo
de segurança disparava porque o artigo citado era de segurança, não porque a pergunta fosse de
roubo. Conserto: palavras de gatilho por tema. Na rodada 2, a a25 não abre mais assim.

**A diferença entre as rodadas é variação da IA:** 7 vereditos e 5 decisões de chamar uma pessoa
mudaram em perguntas que o conserto não toca. A invenção da rodada 2 (a59) mostra um limite da
conferência: ela exige que a resposta cite um artigo da busca, mas não confere cada frase contra
o artigo.

**A conferência do juiz:** 10 casos sorteados antes de ver os vereditos (semente 13). Concordo
com o juiz em 9; no outro (a21), ele foi mais rígido que eu.

**Onde mais erra:** cinco perguntas que a base responde ficam abaixo do limiar da busca e viram
"não sei" (a09, a11, a28, a47, a56); a IA às vezes deixa de fora o passo principal (a03, a08) ou
afirma algo que não está no artigo (a06, a24, a50).

### Propostas da etapa 3

As três primeiras viraram a etapa 3B. A quarta continua aberta.

1. A triagem e o "chamar uma pessoa" (feito na 3B).
2. Conferir frase por frase (feito na 3B).
3. Uma resposta fixa melhor para urgência sem artigo (feito na 3B).
4. Pôr `python -m avaliacao.avaliar_busca` no CI (aberta).

## Etapa 3B: subir o "resolvido sem pessoa" sem perder a segurança

### O método

1. As 60 perguntas da etapa 3 viraram o conjunto de **desenvolvimento**. Antes de qualquer
   conserto, os erros do juiz nas duas rodadas foram classificados por tipo
   (`avaliacao/resultados/erros_do_juiz_etapa3.md`). Rodada 2: incompleta 6, errada 3, inventou
   5, artigo errado 0, não respondeu 6. O conserto foi só o que é geral (prompt, regra).
2. Um conjunto de **prova** novo (`avaliacao/perguntas_prova.jsonl`): 40 perguntas escritas por
   outro agente, que só recebeu o texto do `base/EMPRESA.md`. São 25 que a base responde, 7 que
   não responde, 4 tentativas e 4 urgentes, e 6 trazem dado pessoal de teste. As perguntas só
   foram abertas depois de o código estar congelado (commit `b829bc1`). O gabarito veio depois,
   sem mudar as perguntas: 24 devem sair sem uma pessoa. Alguns assuntos se repetem entre os
   dois conjuntos (empréstimo, maquininha roubada, senha esquecida), porque os dois agentes
   partiram do mesmo `EMPRESA.md`; as perguntas são outras.
3. A prova não decide nada. Ela roda só no fim, 3 vezes, com a mediana, o menor e o maior. As 60
   de desenvolvimento rodam uma vez no fim, para comparar com a etapa 3.

### O que mudou

1. **A triagem decide só a fila e a urgência.** A confiança dela e o "outros" não chamam mais
   uma pessoa no atendimento. A rota `POST /chamados` e a demonstração continuam iguais (um teste
   confere).
2. **Quando chama uma pessoa agora:** a triagem marcou urgente (pela IA ou pelas palavras-chave);
   é reclamação para a Ouvidoria; é tema de segurança (roubo, golpe, link falso, alguém pedindo
   senha ou código) ou tentativa de enganar; a busca deu "nada encontrado"; não há fonte; a IA
   pede uma pessoa (inclusive com confiança abaixo de 0,75) ou falha; ou a conferência frase a
   frase reprova.
3. **A conferência frase a frase** (`app/conferencia.py`), só nas respostas que sairiam sem uma
   pessoa. A resposta é cortada em frases em Python, e uma chamada curta ao Claude Haiku 5.5
   (ferramenta estrita, sem temperature, raciocínio desligado) marca cada frase como apoiada ou
   não pelos artigos citados, pelos dados das consultas e pela data e pelos prazos já calculados.
   Frase sem apoio sai. Se sobrar menos da metade das palavras, chama uma pessoa. Se a conferência
   falhar, também chama uma pessoa. O custo e o tempo a mais aparecem no resultado, no banco e na
   rota.
4. **A mensagem fixa de urgência**, escrita uma vez: diz que o caso é urgente, que uma pessoa já
   foi chamada, a fila e os horários do artigo `horarios-e-canais` (que entra como fonte). Vale
   para a urgência e para o tema de segurança; nos temas de segurança, o primeiro passo do artigo
   vem antes. Numa urgência, nunca só "não sei".
5. **Os gatilhos de segurança ficaram mais estreitos.** Com o tema de segurança chamando uma
   pessoa, "senha", "código" e "sms" sozinhos transformariam "esqueci a senha" em urgência. Agora
   o artigo de senha dispara com "ligou", "pediram", "pedindo", "golpe" e parecidos.
6. **O prompt do agente**, com regras gerais tiradas dos tipos de erro: começar pelo passo
   principal e pelo fato pedido (o limite foi de umas 80 para umas 120 palavras); não escolher a
   venda mais parecida quando a do lojista não está nos dados; seguir os dados quando a mensagem
   os contradiz; não prometer ação da equipe; marcar `precisa_pessoa` só quando o caso já bate com
   o bloco "Quando chamar uma pessoa".
7. **O número principal mudou de nome:** "resolvido sem uma pessoa E certo" (pelo juiz), entre as
   que deviam sair sem pessoa. Ao lado, sempre, "resolvido sem uma pessoa e errado", entre todas:
   saiu sem pessoa e o juiz reprovou, ou o gabarito mandava chamar uma pessoa.

O que não foi consertado: o limiar da busca (a09, a11, a47, a56 ficam abaixo dele; mudá-lo
olhando as 60 seria ajustar ao conjunto) e a queda da API da Anthropic (a39 a a43 na rodada 2).

### Os números

Rodadas de 13/11/2026, com IA de verdade, relógio fixo em sexta, 13/11/2026, 10h. Arquivos:
`avaliacao/resultados/prova_resumo.md` (e `prova_1` a `prova_3`) e
`avaliacao/resultados/desenvolvimento_3b.md`.

**A prova** (40 perguntas nunca usadas para decidir nada; 3 rodadas; mediana, menor e maior):

| Medida | Mediana | Menor | Maior |
|---|---|---|---|
| **Resolvido sem uma pessoa E certo** (entre as 24 que deviam sair sem pessoa) | **10/24** | 9 | 11 |
| **Resolvido sem uma pessoa e errado** (entre as 40) | **3/40** | 2 | 4 |
| Resolvido sem uma pessoa, certo ou não | 13/24 | 13 | 13 |
| Resposta certa (juiz), nas que a base responde | 14/29 | 13 | 14 |
| "Não sei" certo nas sem resposta | 7/7 | 7 | 7 |
| Sem resposta em que inventou | 0 | 0 | 0 |
| Chamou uma pessoa nas urgentes e nas tentativas | 8/8 | 8 | 8 |
| Respostas com instrução que citam artigo | todas (31/31, 31/31, 30/30) | | |
| Fila certa | 34/40 | 33 | 34 |
| Dados pessoais enviados à IA e aos embeddings | 0 de 6 | 0 | 0 |
| Custo médio por mensagem | US$ 0,00075 | 0,00075 | 0,00079 |
| Tempo médio por mensagem | 5,3 s | 5,3 s | 5,3 s |

**As 60 de desenvolvimento**, uma rodada, ao lado da etapa 3 (o "sem pessoa e errado" da etapa
3 foi recalculado com a mesma regra, a partir dos arquivos salvos):

| Medida | Etapa 3, rodada 1 | Etapa 3, rodada 2 | Etapa 3B |
|---|---|---|---|
| **Resolvido sem uma pessoa E certo** | 12/35 | 12/35 | **19/35** |
| **Resolvido sem uma pessoa e errado** | 2/60 | 1/60 | **2/60** |
| Resolvido sem uma pessoa, certo ou não | 14/35 | 13/35 | 21/35 |
| Resposta certa (juiz) | 28/44 | 26/44 | 26/44 |
| "Não sei" certo nas sem resposta | 11/11 | 10/11 | 11/11 |
| Sem resposta em que inventou | 0 | 1 | 1 |
| Chamou uma pessoa nas urgentes e nas tentativas | 10/10 | 10/10 | 10/10 |
| Respostas com instrução que citam artigo | 42/42 | 42/42 | 46/46 |
| Fila certa | 49/60 | 48/60 | 48/60 |
| Dados pessoais enviados | 0 | 0 | 0 |
| Custo médio por mensagem | US$ 0,00061 | US$ 0,00055 | US$ 0,00070 |
| Tempo médio por mensagem | 4,4 s | 5,3 s | 5,0 s |

**O tempo e o custo de cada parte** (prova, mediana, por mensagem; a triagem e a busca rodam ao
mesmo tempo):

| Parte | Custo | Tempo |
|---|---|---|
| Triagem | US$ 0,00025 | 2,5 s |
| Busca (embeddings) | US$ 0,000008 | 0,6 s |
| Resposta (agente) | US$ 0,00041 | 2,3 s |
| Conferência frase a frase | US$ 0,00009 por mensagem; US$ 0,00026 por resposta conferida | 0,5 s por mensagem; 1,7 s por resposta conferida |

A conferência rodou em 13 respostas por rodada da prova (21 nas 60). Tirou frase em 2 a 4 delas
(4 nas 60) e nunca chegou a chamar uma pessoa por sobrar pouco.

**O raciocínio:** 0 blocos de raciocínio em todas as partes (triagem, agente, conferência e
juiz), nas 4 rodadas.

**Por que chamou uma pessoa na prova** (mediana; uma mensagem pode ter mais de um motivo). Chamou
em 27 das 40 mensagens; 11 delas sem precisar.

| Motivo | Aparece | Nas que chamaram sem precisar |
|---|---|---|
| A IA pediu uma pessoa | 13 | 6 |
| Nada encontrado na busca | 10 | 2 |
| Urgente (triagem ou palavras-chave) | 9 | 2 |
| Confiança baixa do agente | 9 | 6 |
| Sem fonte | 1 | 0 |
| Tema de segurança | 1 | 0 |

A confiança baixa do agente foi o único motivo em 3 a 4 mensagens por rodada. Ela empata com "a
IA pediu" como causa das idas sem precisar. Não foi mexida: o código está congelado, e qualquer
mudança é decidida nas 60.

**O custo das rodadas:** cerca de US$ 1,09 (o atendimento, US$ 0,13; o juiz, US$ 0,95).

### O que as rodadas mostraram (para decidir nas 60, nunca na prova)

1. **A conferência tira frase certa.** Na prova, ela tirou nas 3 rodadas a frase "como você é
   MEI, o cadastro é com CNPJ" (p18), que está no artigo citado; a resposta saiu sem pessoa e
   errada. Nas 60, tirou "a Mini aceita aproximação" (a42), também no artigo. Esse é o principal
   motivo de "sem pessoa e errado" que veio da 3B.
2. **A mensagem de urgência aparece onde o caso não é urgente.** Quem marca a urgência é a
   triagem. Nas 60, a mensagem saiu em 12 respostas, 6 delas em perguntas comuns (a03, a09, a11,
   a16, a21, a25); na prova, em p12 e p28 (e p09 numa rodada). O lojista lê "Seu caso é urgente"
   num problema de leitura de cartão.
3. **O juiz conta a mensagem fixa de urgência como invenção.** A rubrica exclui "uma pessoa vai
   continuar o atendimento", mas não conhece a mensagem nova; "a fila Suporte" e "uma pessoa já
   foi chamada" viram invenção. Nas 60, isso explica 10 das 14 marcas de "inventou". Não muda os
   dois números principais (essas respostas já saem com uma pessoa), mas puxa para baixo a
   "resposta certa". O juiz não foi mudado.
4. **A confiança baixa do agente** é o motivo de 6 das 11 idas sem precisar na prova (empatada
   com "a IA pediu").

### Mudanças feitas depois do congelamento (e por quê)

O código foi congelado no commit `b829bc1`, antes de abrir a prova. Depois disso, entraram duas
mudanças, as duas a pedido do Gabriel e antes de qualquer rodada com IA de verdade:

1. **O raciocínio escrito no código** (`815af46`), sem mudar o comportamento. A referência atual
   da API diz que o Claude Haiku 5.5 liga o raciocínio adaptativo, com esforço `medium`, quando o
   pedido não diz nada sobre `thinking`; e que, com a ferramenta forçada, ele pula o raciocínio e
   começa pela chamada da ferramenta. O agente e a triagem nunca disseram nada, então dependiam
   desse padrão. Agora o agente e a triagem do atendimento pedem, por escrito, raciocínio
   adaptativo com esforço `medium` (`RACIOCINIO_ATENDIMENTO`). A rota `/chamados` continua com o
   pedido de sempre. A conferência pede, por escrito, sem raciocínio e com esforço `medium`. O
   juiz pede, por escrito, raciocínio adaptativo e esforço `medium`, como na etapa 3 (o juiz não
   é produto e pode raciocinar).
2. **Mais medidas na avaliação** (`fcadef4`), só na medição: os motivos de chamar uma pessoa (com
   a confiança baixa do agente separada), o custo e o tempo de cada parte, e os blocos de
   raciocínio que voltam em cada parte.

**A trava mudou.** Era "nada de modo de raciocínio"; o objetivo era o tempo e o custo (e a conta
de data, que agora é do código). Agora é: o raciocínio é sempre explícito no código, e o relatório
mostra o tempo e o custo de cada parte. A conferência frase a frase continua sem raciocínio.

**Houve raciocínio na etapa 3?** Não dá para provar pelos arquivos: nenhum resultado guardou os
blocos da resposta da IA, e a contagem de tokens da API não separa o raciocínio. O indício é a
triagem: na reavaliação de 13/11, ela gastou de 290 a 414 tokens de saída por chamado (média 370),
o que combina com só o JSON da ferramenta. A partir da etapa 3B, a avaliação conta os blocos de
raciocínio de cada parte.

## Como rodar

```bash
pytest                                          # testes (nenhum chama a Anthropic nem o Google)
python scripts/indexar_base.py                  # gera base/indice.json
python -m avaliacao.avaliar_busca --calibrar    # grava os limiares em base/limiares.json
python -m avaliacao.avaliar_busca               # a busca nas 48 perguntas da etapa 1
python -m avaliacao.avaliar_busca --perguntas avaliacao/perguntas_agente.jsonl \
    --nome busca_agente --modos sentido hibrida # a busca nas 60 perguntas novas
python -m avaliacao.avaliar_agente              # o agente inteiro, com o juiz (custa ~US$ 0,30)
python scripts/fumaca_atendimento.py            # a fumaça de 10 perguntas
# Etapa 3B: a prova 3 vezes (mediana, menor e maior) e as 60 de desenvolvimento uma vez
python -m avaliacao.avaliar_agente --perguntas avaliacao/perguntas_prova.jsonl \
    --nome prova --titulo "Conjunto de prova (etapa 3B)" --repeticoes 3
python -m avaliacao.avaliar_agente --nome desenvolvimento_3b \
    --titulo "As 60 de desenvolvimento (etapa 3B)"
```

## As chaves

`GEMINI_API_KEY` (Google AI Studio, chave "triagem-atendimento-busca") e `ANTHROPIC_API_KEY`
ficam no `.env`, que nunca vai para o Git. **Atenção ao plano gratuito do Google:** nos termos
dele, o que é enviado pode ser usado para melhorar os produtos e lido por pessoas. Aqui só vão
artigos inventados e perguntas já mascaradas. Com dados de clientes de verdade, use o plano pago
ou o Vertex AI.
