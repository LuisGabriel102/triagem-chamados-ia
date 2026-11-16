# Resumo em uma página

**Luis Gabriel Albrecht** · projeto de portfólio · empresa e dados **inventados** (a Tapiri
Pagamentos, de maquininhas de cartão).

## O que é

Duas partes de um mesmo atendimento com IA:

1. **Triagem.** Lê o chamado, esconde os dados pessoais, classifica com o Claude (ou o Gemini) e
   escolhe a fila. Se a IA cair, um plano B por regras assume.
2. **Atendimento.** Responde o lojista com 30 artigos de ajuda e os dados da própria loja, mostra
   a fonte e chama uma pessoa quando precisa (urgência, tentativa de enganar, falta de fonte).

Vídeo de 21 segundos, com respostas reais da IA gravadas uma vez:
[`docs/video/demonstracao.webm`](video/demonstracao.webm).

## Os números (com a margem de erro de 95%)

| | Medido | Faixa |
|---|---|---|
| Triagem: os 4 campos certos no mesmo chamado | 36/40 | de 77% a 96% |
| Triagem: urgentes liberados sem uma pessoa | 0 | — |
| Atendimento: resolvido sem uma pessoa **e certo** | 11/21 | de 32% a 72% |
| Atendimento: resolvido sem uma pessoa **e errado** | 2/40 | de 1% a 17% |
| Urgências e tentativas de enganar com uma pessoa | 8/8 | de 68% a 100% |
| Dados pessoais de teste enviados à IA | 0 de 6 | — |
| Custo por mensagem do atendimento | US$ 0,00091 | — |

**Como ler.** São poucas perguntas, todas escritas para teste; com mensagens reais, o resultado
tende a ser pior. A resposta "certa" é julgada por um modelo (Claude Sonnet 5.5), ainda não
comparado com uma pessoa. As faixas da versão 1 e da versão 2 se sobrepõem: a prova não mostra
que a versão 2 é melhor.

## As decisões que mais pesam

- **O lojista vem da sessão, nunca do texto.** As ferramentas não têm parâmetro de lojista: a IA
  não escolhe de quem é o dado.
- **Sem fonte, sem conselho.** Toda instrução cita um artigo que veio da busca.
- **A conta é do código.** Datas, prazos e valores saem calculados; a IA só escreve.
- **A confiança da IA não decide sozinha.** Quem decide são motivos objetivos e a conferência.
- **Treino e prova separados.** As mudanças foram decididas em 60 perguntas; a prova foi aberta
  uma vez, com o código congelado, e nada foi ajustado depois.
- **Dados pessoais saem antes da IA.** CPF, CNPJ, cartão, e-mail, telefone, RG, endereço e o nome
  de quem se apresenta ("meu nome é", "sou a"), por regras de contexto.
- **O histórico da conversa é dado não confiável.** Passa pelo mascaramento e pela detecção de
  tentativa e vai à IA como dado, nunca como ordem.
- **A fila de revisão humana** (`/fila`) mostra o que a equipe recebe quando a IA chama uma
  pessoa.

## Um experimento que não deu certo (e ficou registrado)

A conferência frase a frase (uma segunda chamada ao mesmo modelo, o Claude Haiku 5.5, com outro
papel) erra boa parte dos cortes: medida sozinha, dos 22 cortes, 14 eram frases certas, 3 eram
cortes certos e 5 ficaram em dúvida, numa classificação feita por um modelo (o Claude Code), não
por uma pessoa (`avaliacao/resultados/conferencia_cortes.md`). A alternativa testada: o modelo
reescreve a resposta citando o trecho exato da fonte, e o código tira a frase sem citação. Nas
60, piorou: certo sem pessoa de 23/35 para 17/35, errado sem pessoa de 2/60 para 5/60. Ao ser
obrigado a citar, o modelo copiou pedaços da fonte em vez de responder. Ficou desligada.

## A prova 3

Escrita por um agente separado, com assunto e estilo sorteados (chat sem acento, áudio
transcrito, pessoa idosa...), para não se parecer com as anteriores. Rodou 3 vezes (mediana). Ao
montar o gabarito, li as mensagens e acrescentei uma regra ao mascaramento (o tratamento "dona",
visto na r24), antes de rodar. Fora isso, o código estava congelado.

| | Prova 3 | Faixa de 95% | Prova 2 |
|---|---|---|---|
| Resolvido sem uma pessoa **e certo** | 11/23 | de 29% a 67% | 11/21 |
| Resolvido sem uma pessoa **e errado** | 5/40 | de 5% a 26% | 2/40 |
| Urgências e tentativas com uma pessoa | 8/8 | de 68% a 100% | 8/8 |

Foi mais difícil, e o número perigoso subiu. Nas 3 rodadas, foram 16 erros em 9 perguntas: 6
vieram das 3 perguntas marcadas como difíceis antes de rodar (r07, r12 e r22), e 10 foram
invenções que a conferência deixou passar, como uma data que a própria IA calculou, um conselho
sobre plano que a base não dá e um caminho no app que não está no artigo. Na r12, a IA afirmou
sem fonte que não existe seguro, e isso também é invenção. É o próximo problema a atacar.

## O que ainda falta

- **O juiz contra uma pessoa:** a página para marcar 30 respostas está pronta e ainda não foi
  marcada.
- **Uma avaliação de conversas:** a conversa com histórico só passou por um teste de fumaça.
- **A conferência** ainda corta frases certas (14 dos 22 cortes medidos) e deixa passar invenção
  pequena. O próximo teste é um modelo mais forte só nela, ou deixar o Haiku raciocinar antes de
  conferir, sem forçar a ferramenta.

## Onde olhar

- [`README.md`](../README.md): como rodar, as rotas e todas as decisões.
- [`docs/ATENDIMENTO.md`](ATENDIMENTO.md): cada etapa, cada rodada e cada erro, com as datas.
- [`avaliacao/resultados/`](../avaliacao/resultados/): os relatórios de cada rodada.
