# Atendimento com IA

Hoje a triagem decide para onde vai a mensagem. A versão nova responde sozinha o que der,
mostrando de onde tirou a resposta, e chama uma pessoa quando precisa. O tema é o lojista
com maquininha de cartão, numa empresa **inventada**: a Tapiri Pagamentos
(`base/EMPRESA.md`). Os prazos, as taxas, os preços, os lojistas e as vendas são fictícios.

## As 5 etapas

| Etapa | O que entra | Estado |
|---|---|---|
| 1. Base de conhecimento e busca | 30 artigos, busca por palavras (BM25), busca por sentido (embeddings do Gemini), fusão, limiar de "nada encontrado", avaliação da busca | **Pronta e medida** com o Google de verdade (13/11/2026). |
| 2. O agente | Responde com a fonte, consulta dados inventados e chama uma pessoa; rota `POST /atendimento` | **Pronta.** Testes sem API de verdade; fumaça com IA de verdade em 10 perguntas. |
| 3. A avaliação completa | Umas 60 perguntas com gabarito, de ponta a ponta | Não começou |
| 4. A página e a publicação | Conversa no celular e no computador; pgvector no banco | Não começou. Lembrete: o Dockerfile de hoje copia só `app/`; `base/` e `dados/` vão precisar entrar na imagem. Até lá, a API sobe sem o atendimento e a rota responde 503. |
| 5. Opcional | O Gemini no Vertex AI comparado com o Claude | Não começou |

Nada desta frente foi publicado. O trabalho está na branch `atendimento`, só no computador.

## Etapa 1: como a busca funciona

1. **Mascaramento primeiro (LGPD).** A pergunta passa pelo `app/mascaramento.py`, o mesmo da
   triagem, antes de qualquer coisa. Só o texto mascarado vira vetor.
2. **Busca por palavras** (`app/busca_palavras.py`). BM25 em Python puro, sem dependência
   nova: minúsculas, comparação sem acento, palavras vazias fora (inclusive "vc" e "pra") e
   uma redução simples de plural. O título conta duas vezes. Não entende sinônimo nem erro
   de digitação.
3. **Busca por sentido** (`app/busca_sentido.py`). Embeddings do Gemini pelo SDK
   google-genai, modelo `gemini-embedding-2`, 768 dimensões. Esse modelo não aceita o campo
   `task_type`: a documentação do Google manda escrever a tarefa no próprio texto, e o par é
   o da tarefa de busca: `task: search result | query: {texto}` na pergunta e
   `title: {título} | text: {texto}` no artigo (conferido de novo em 13/11/2026). Os vetores
   dos artigos ficam em `base/indice.json` (versionado); a pergunta vira vetor na hora. Com 30
   artigos, o cosseno roda na memória; a interface `IndiceVetores` está pronta para o
   pgvector.
4. **Fusão** (`app/busca.py`). Os dois rankings se juntam pela posição (RRF, k = 60). Saem
   os 3 melhores.
5. **Limiar.** Se nem o melhor artigo for parecido o bastante, o resultado é "nada
   encontrado". Com a busca por sentido, vale a maior similaridade; sem ela, a maior nota do
   BM25.
6. **Queda do Google.** A busca segue só por palavras e avisa no resultado.

### Os limiares (`base/limiares.json`)

Os limiares não são segredo: ficam em `base/limiares.json`, versionado, com a data e o
conjunto de calibração. Quem grava o arquivo é a calibração
(`python -m avaliacao.avaliar_busca --calibrar`). `LIMIAR_BM25` e `LIMIAR_SIMILARIDADE` no
ambiente só sobrescrevem; vazios, vale o arquivo. O limiar da similaridade só vale para o
modelo e as dimensões com que foi calibrado.

Eles saem de **outras 20 perguntas** (`avaliacao/perguntas_calibracao.jsonl`: 14 com
resposta e 6 sem), nunca das 48 da avaliação. A regra (`escolher_limiar`, em
`app/busca.py`) fica com o limiar que mais separa os dois grupos, pesando os dois igualmente;
no empate, fica o do meio.

| Limiar | Valor | Com resposta que passam | Sem resposta barradas |
|---|---|---|---|
| Nota do BM25 | 6,2882 | 10/14 | 6/6 |
| Similaridade (gemini-embedding-2, 768) | 0,7108 | 13/14 | 6/6 |

Os dois foram calibrados em 13/11/2026. A nota do BM25 depende da base inteira: quando os
artigos mudarem, recalibre. Um teste avisa se o arquivo deixar de bater com a calibração.

### Resultado da avaliação da busca

Rodada em 13/11/2026 com o Google de verdade (chave do AI Studio). Nada foi ajustado depois
de ver os números. Relatório completo: `avaliacao/resultados/busca.md`.

| Medida (40 com resposta, 8 sem) | Por palavras | Por sentido | Híbrida |
|---|---|---|---|
| **Respondidas e certas** (acima do limiar e com o artigo certo entre os 3) | 23/40 | **37/40** | 34/40 |
| Acerto no 1º lugar | 24/40 | 40/40 | 33/40 |
| Acerto entre os 3 primeiros | 32/40 | 40/40 | 36/40 |
| Sem resposta que ficaram em "nada encontrado" | 7/8 | 8/8 | 8/8 |
| Com resposta barradas por engano | 17/40 | 3/40 | 3/40 |
| Dados pessoais enviados para os embeddings | não se aplica | 0 de 8 | 0 de 8 |

> **Ressalva:** as perguntas foram escritas junto com a base, pela mesma pessoa. Com
> perguntas de lojistas de verdade, o resultado tende a ser pior.

A busca só por sentido saiu melhor que a híbrida: a fusão com o BM25 empurra artigos
errados para cima. **O agente continua com a híbrida**, como foi projetado: trocar por causa
destes números seria ajustar olhando a avaliação. A troca fica como proposta, para decidir
com as perguntas novas da etapa 3.

## Etapa 2: o agente

### O fluxo de cada mensagem (`app/atendimento.py`)

1. **Mascara a mensagem.** Daqui em diante, só o texto mascarado circula: triagem, busca, IA
   e banco.
2. **Triagem e busca ao mesmo tempo**, em duas linhas de execução, para ganhar tempo.
3. **Quem responde:**
   - tentativa de mandar na IA ou de pedir dado de outra loja (detectada por regras): uma
     resposta fixa, sem chamar a IA, e vai para uma pessoa;
   - a busca deu "nada encontrado": o agente diz que não sabe, sem chamar a IA, e vai para
     uma pessoa;
   - senão, o **Claude Haiku 5.5** responde (`app/agente.py`).
4. **A resposta da IA** vem sempre pela ferramenta `responder_lojista`, em modo estrito:
   resposta, artigos usados, precisa_pessoa, motivo e confiança. Antes, a IA pode consultar
   os dados do lojista, no máximo 3 vezes; depois da 3ª consulta, a resposta é forçada. Cada
   pedido força o uso de uma ferramenta e uma por vez. O texto fixo (instruções e
   ferramentas) vai para o cache de prompt. Nenhuma chamada usa temperature.
5. **A conferência:** artigo citado que não veio da busca não vale; resposta sem artigo e
   sem consulta também não; a resposta passa de novo pelo mascaramento (os e-mails da própria
   empresa, que estão nos artigos, ficam); se a IA pede uma pessoa ou a confiança dela fica
   abaixo de 0,75, vai para uma pessoa.
6. **O plano B:** se a IA falhar (rede, limite, formato), a resposta é o trecho do artigo
   achado, com "Uma pessoa da nossa equipe vai confirmar". Sem artigo, vai para uma pessoa.
   O atendimento nunca para: até uma busca que quebra vira "não sei".

### Quando chama uma pessoa

- a triagem marcou revisão humana (urgente, confiança baixa, categoria "outros");
- a busca deu "nada encontrado";
- reclamação: vai para a fila da Ouvidoria;
- alguém tenta mandar na IA ou pedir dado de outra loja;
- a IA pede uma pessoa, falha, cita artigo de fora ou responde com confiança baixa.

Mesmo indo para uma pessoa, a resposta da IA ainda leva os primeiros passos seguros do
artigo, se houver, e termina com "Uma pessoa da nossa equipe vai continuar o atendimento."

### As ferramentas (`app/ferramentas.py`, dados em `dados/lojistas.json`)

- `consultar_recebimentos`: as vendas do lojista, com valor bruto, taxa, líquido, data
  prevista e situação.
- `status_maquininha`: as maquininhas do lojista, com a situação (ligada, sem conexão,
  bloqueada) e a última conexão.
- **O lojista vem da sessão, nunca do texto.** As ferramentas não têm parâmetro: a IA não
  escolhe de quem é o dado. A saída tem só os campos de uma lista fechada; documento, conta,
  e-mail e telefone nunca chegam à IA.
- Três lojistas inventados, com casos que batem com a base: `loja-001` (vendas para cair),
  `loja-002` (uma maquininha bloqueada) e `loja-003` (valor retido por contestação, uma
  venda em análise e uma maquininha sem conexão). Os dias são contados a partir de hoje.
- O limite de 3 vale para as consultas; a ferramenta de resposta é a saída, não conta.

### A rota `POST /atendimento`

Exige a chave `X-API-Key`, como as outras. Recebe:

```json
{"mensagem": "A bobina acabou, onde compro mais?", "canal": "chat",
 "sessao": {"lojista_id": "loja-001"}}
```

Na demonstração, a sessão é simulada; em produção, viria do login. Devolve a resposta, as
fontes (id e título dos artigos), a fila, se precisa de uma pessoa e por quê, de onde veio a
resposta (`ia`, `plano_b` ou `fixa`), as consultas feitas, o custo e o tempo, com o detalhe
de triagem, busca e resposta. Grava na tabela `atendimentos` só o texto mascarado. Lojista
desconhecido dá 404. Uma mensagem por vez: conversa com histórico fica para depois.

### O custo e o tempo

O custo soma a triagem, a busca (os tokens que o Google cobrou pela pergunta, ao preço do
plano pago: US$ 0,20 por milhão; no gratuito, é zero) e a resposta (Haiku 5.5: US$ 0,10 e
US$ 0,50 por milhão de tokens de entrada e de saída, com o cache a 10%). O tempo total é o
relógio de ponta a ponta; como a triagem e a busca rodam juntas, ele não é a soma das partes.

### A fumaça com IA de verdade (13/11/2026)

`python scripts/fumaca_atendimento.py`: 10 perguntas da avaliação da busca, escolhidas antes
de rodar, de ponta a ponta. **Não é a avaliação da etapa 3.** Resultado em
`avaliacao/resultados/fumaca_atendimento.md`.

- Custo médio: US$ 0,000638 por mensagem (triagem 0,000262; busca 0,0000047; resposta
  0,000371). Tempo médio: 5,7 s.
- 8 das 10 foram para uma pessoa. Em 6 delas, um dos motivos é a triagem com confiança
  baixa (0,6 a 0,7): o prompt da triagem foi escrito para outro negócio (sistema por
  assinatura e entregas) e não reconhece bem as mensagens de lojista.
- O cache de prompt funcionou: a 1ª mensagem gravou 2.045 tokens, e as seguintes leram de lá.
- Problemas vistos: uma resposta se contradiz sobre a data (b01); uma deixou de fora o passo
  principal, bloquear a maquininha roubada (b14); uma explicou o estorno mas não como
  cancelar a venda (b19); a busca barrou "bubina" (b10). E a conferência mascarava o e-mail
  da ouvidoria (b38): **corrigido** depois da fumaça, com teste.

### Propostas (não aplicadas)

1. **Trocar a busca do agente para "só por sentido"**, decidindo com as perguntas novas da
   etapa 3, não com as 48 de hoje.
2. **Adaptar o prompt da triagem ao lojista com maquininha.** Hoje ela manda quase tudo para
   uma pessoa por confiança baixa.
3. **Datas:** mandar o dia da semana junto com cada data nas ferramentas, ou deixar a IA
   pensar antes de responder (hoje a ferramenta forçada pula o raciocínio). A b01 errou nisso.
4. **Resposta que pede uma pessoa sem citar artigo** passa pela conferência sem fonte (b14
   sugeriu o Pix sem citar). Dá para exigir a fonte também nesse caso.
5. Pôr `python -m avaliacao.avaliar_busca` no CI, como já está a avaliação das regras.

## Como rodar

```bash
pytest                                        # testes (nenhum chama a Anthropic nem o Google)
python scripts/indexar_base.py                # gera base/indice.json (precisa da chave)
python -m avaliacao.avaliar_busca --calibrar  # grava os limiares em base/limiares.json
python -m avaliacao.avaliar_busca             # avalia as 48 perguntas
python scripts/fumaca_atendimento.py          # fumaça do agente com IA de verdade
```

## A chave do Google AI Studio

Configurada no `.env` em 13/11/2026 (`GEMINI_API_KEY`, chave "triagem-atendimento-busca").
Para criar outra: https://aistudio.google.com/apikey, **Create API key**, e a linha
`GEMINI_API_KEY=` com a chave no `.env`. O `.env` nunca vai para o Git.

**Atenção ao plano gratuito.** Nos termos do Google, o que é enviado no plano gratuito pode
ser usado para melhorar os produtos deles, e pessoas podem ler. Os termos pedem para não
enviar dado pessoal ou sigiloso. Aqui só vão artigos inventados e perguntas já mascaradas.
Com dados de clientes de verdade, use o plano pago ou o Vertex AI.
