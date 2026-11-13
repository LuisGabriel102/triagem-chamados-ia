# Atendimento com IA

Hoje a triagem decide para onde vai a mensagem. A versão nova vai responder sozinha o que
der, mostrando de onde tirou a resposta, e chamar uma pessoa quando precisar. O tema é o
lojista com maquininha de cartão, numa empresa **inventada**: a Tapiri Pagamentos
(`base/EMPRESA.md`). Os prazos, as taxas, os preços e as pessoas são fictícios.

## As 5 etapas

| Etapa | O que entra | Estado |
|---|---|---|
| 1. Base de conhecimento e busca | 30 artigos, busca por palavras (BM25), busca por sentido (embeddings do Gemini), fusão, limiar de "nada encontrado", avaliação da busca | **Pronta.** A busca por palavras foi medida. A busca por sentido está pronta e testada com um gerador falso, mas **não rodou de verdade**: falta a chave do Google (veja o fim deste documento). |
| 2. O agente | Responde com a fonte, consulta dados inventados e chama uma pessoa | Não começou |
| 3. A avaliação completa | Umas 60 perguntas com gabarito, de ponta a ponta | Não começou |
| 4. A página e a publicação | Conversa no celular e no computador; pgvector no banco | Não começou. Lembrete: o Dockerfile de hoje copia só a pasta `app/`; a `base/` vai precisar entrar na imagem. |
| 5. Opcional | O Gemini no Vertex AI comparado com o Claude | Não começou |

Nada desta frente foi publicado. O trabalho está na branch `atendimento`, só no computador.

## Etapa 1: como a busca funciona

1. **Mascaramento primeiro (LGPD).** A pergunta passa pelo `app/mascaramento.py`, o mesmo da
   triagem, antes de qualquer coisa. Só o texto mascarado vira vetor: CPF, CNPJ, cartão,
   e-mail e telefone nunca vão para o Google.
2. **Busca por palavras** (`app/busca_palavras.py`). BM25 em Python puro, sem dependência
   nova. Antes da conta: minúsculas, comparação sem acento, palavras vazias fora (inclusive
   as informais, como "vc" e "pra") e uma redução simples de plural. O título do artigo
   conta duas vezes. Não entende sinônimo nem erro de digitação: "bubina" não acha "bobina".
3. **Busca por sentido** (`app/busca_sentido.py`). Embeddings do Gemini pelo SDK
   google-genai, com o modelo `gemini-embedding-2` e 768 dimensões. Esse modelo não aceita
   o campo `task_type`; a documentação do Google manda escrever a tarefa no próprio texto:
   `task: search result | query: ...` na pergunta e `title: ... | text: ...` no artigo. É o
   que o código faz. Cada artigo é um trecho só, porque são curtos. Os vetores dos artigos
   ficam em `base/indice.json`; a pergunta vira vetor na hora. Com 30 artigos, o cosseno
   roda na memória. A interface `IndiceVetores` está pronta para o pgvector da etapa 4.
4. **Fusão** (`app/busca.py`). Os dois rankings se juntam pela posição (RRF, k = 60): cada
   artigo soma 1 / (60 + posição) em cada lista. Saem os 3 melhores.
5. **Limiar.** Se nem o melhor artigo for parecido o bastante, o resultado é "nada
   encontrado". É isso que vai fazer o agente dizer "não sei" e chamar uma pessoa. Com a
   busca por sentido, vale a maior similaridade; sem ela, a maior nota do BM25.
6. **Queda do Google.** Se o Google falhar, a busca segue só por palavras e avisa no
   resultado (`avisos`). O texto do erro do Google vai só para o log.

O acesso ao Google tem dois jeitos: a chave do Google AI Studio (`GEMINI_API_KEY`) ou, sem
ela, o Vertex AI (`GOOGLE_CLOUD_PROJECT`, com o login do gcloud). Sem nenhum dos dois, a
busca roda só por palavras.

## Como o limiar foi escolhido

O limiar sai de **outras 20 perguntas** (`avaliacao/perguntas_calibracao.jsonl`: 14 com
resposta e 6 sem), nunca das 48 da avaliação. Escolher o limiar olhando a avaliação
deixaria o número dela bom demais.

A regra (`escolher_limiar`, em `app/busca.py`): para cada pergunta, pega a nota do artigo
mais parecido. Testa os pontos entre notas vizinhas e fica com o que deixa passar mais
perguntas com resposta e barra mais perguntas sem resposta, pesando os dois grupos
igualmente. No empate, fica o do meio.

- **BM25: 6,2882** (`LIMIAR_BM25`). Na calibração, passam 10 de 14 com resposta e são
  barradas 6 de 6 sem resposta. A margem é estreita: a pergunta sem resposta com a maior
  nota teve 6,229, e a com resposta logo acima teve 6,3475. A nota do BM25 depende da base
  inteira: quando os artigos mudarem, recalibre. Um teste avisa se o valor na configuração
  deixar de bater com a calibração.
- **Similaridade: ainda não calibrada** (`LIMIAR_SIMILARIDADE` vazio). Ela precisa da busca
  por sentido rodando. Enquanto estiver vazia, a decisão de "nada encontrado" usa a nota do
  BM25, e o resultado avisa isso. A avaliação calibra a similaridade na hora, se precisar.

Detalhe de cada pergunta: `avaliacao/resultados/calibracao.md`.

## Resultado da avaliação da busca

Rodada em 13/11/2026, **só com a busca por palavras**. As buscas por sentido e híbrida não
rodaram (sem chave). Relatório completo: `avaliacao/resultados/busca.md`.

| Medida (busca por palavras) | Resultado |
|---|---|
| Acerto no 1º lugar (40 perguntas com resposta) | 24/40 (60%) |
| Acerto entre os 3 primeiros | 32/40 (80%) |
| Sem resposta que ficaram em "nada encontrado" | 7/8 |
| Com resposta que viraram "nada encontrado" por engano | 17/40 (42%) |
| Dados pessoais no texto que iria para os embeddings | 0 de 8 |

> **Ressalva:** as perguntas foram escritas junto com a base, pela mesma pessoa. Com
> perguntas de lojistas de verdade, o resultado tende a ser pior.

O que os números dizem: a busca por palavras erra quando o lojista usa outra palavra
("adiantar" em vez de "antecipar") ou escreve errado ("bubina"). E o limiar do BM25,
calibrado em poucas perguntas, barra muita pergunta boa. É o caso que a busca por sentido
deve resolver; o número dela só sai com a chave.

## Como rodar

```bash
pytest                                        # testes (nenhum chama o Google)
python -m avaliacao.avaliar_busca --calibrar  # escolhe os limiares
python -m avaliacao.avaliar_busca             # avalia as 48 perguntas
python scripts/indexar_base.py                # gera base/indice.json (precisa da chave)
```

Com a chave configurada, a avaliação também atualiza o índice antes (só o que mudou) e
manda cada pergunta ao Google uma vez só. Uma rodada completa, na primeira vez, faz cerca
de 100 chamadas de embedding: 30 artigos, 20 perguntas de calibração e 48 de avaliação.

## Para ligar a busca por sentido: criar a chave no Google AI Studio

1. Entre em https://aistudio.google.com/apikey com a sua conta Google de sempre.
2. Na primeira vez, aceite os termos. O AI Studio cria sozinho um projeto e uma chave.
   Se não aparecer nenhuma chave, clique em **Create API key** (Criar chave de API).
3. Copie a chave. Ela aparece inteira só nessa tela; guarde com cuidado.
4. Abra o arquivo `.env` do projeto e acrescente uma linha:
   `GEMINI_API_KEY=` seguido da chave, sem espaço e sem aspas. O `.env` nunca vai para o Git.
5. Rode `python scripts/indexar_base.py` e depois
   `python -m avaliacao.avaliar_busca --calibrar`.
6. Grave no `.env` o `LIMIAR_SIMILARIDADE` que a calibração mostrar.
7. Rode `python -m avaliacao.avaliar_busca`. O relatório sai em
   `avaliacao/resultados/busca.md`, agora com as três colunas.

**Atenção ao plano gratuito.** Nos termos do Google, o que é enviado no plano gratuito pode
ser usado para melhorar os produtos deles, e pessoas podem ler. Os termos pedem para não
enviar dado pessoal ou sigiloso. Aqui só vão artigos inventados e perguntas já mascaradas.
Com dados de clientes de verdade, use o plano pago ou o Vertex AI.
