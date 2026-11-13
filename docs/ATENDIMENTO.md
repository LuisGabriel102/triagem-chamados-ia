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

Vai para uma pessoa quando a triagem marca revisão humana (urgente, confiança baixa, "outros"),
a busca dá "nada encontrado", é reclamação (fila da Ouvidoria), alguém tenta enganar a IA, ou a
IA pede uma pessoa, falha, cita artigo de fora, não cita artigo ou tem confiança baixa.

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

### Propostas (não aplicadas)

1. **A triagem e o "chamar uma pessoa".** Ou recalibrar a confiança da triagem para o lojista,
   ou deixar a decisão de chamar uma pessoa com o agente e usar a triagem só para a fila e a
   urgência. É o que mais pesa no número principal.
2. **Conferir frase por frase** (por exemplo, um segundo modelo que marca afirmação sem fonte),
   para pegar casos como a a59.
3. **Uma resposta fixa melhor para urgência sem artigo** (a28 recebeu só "não sei"): avisar do
   atendimento 24 horas.
4. Pôr `python -m avaliacao.avaliar_busca` no CI.

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
```

## As chaves

`GEMINI_API_KEY` (Google AI Studio, chave "triagem-atendimento-busca") e `ANTHROPIC_API_KEY`
ficam no `.env`, que nunca vai para o Git. **Atenção ao plano gratuito do Google:** nos termos
dele, o que é enviado pode ser usado para melhorar os produtos e lido por pessoas. Aqui só vão
artigos inventados e perguntas já mascaradas. Com dados de clientes de verdade, use o plano pago
ou o Vertex AI.
