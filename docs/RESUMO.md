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
- **Dados pessoais saem antes da IA.** CPF, CNPJ, cartão, e-mail, telefone, RG, endereço e nome
  (por regras de contexto).

## O que ainda falta (e está pronto para medir)

- **A conferência erra cerca de metade dos cortes.** A alternativa por citação (o modelo cita o
  trecho exato da fonte e o código tira o que não tem prova) está pronta e desligada, esperando a
  medida nas 60 (cerca de US$ 0,44).
- **A prova 3**, escrita de outro jeito para não se parecer com as anteriores, está pronta e
  ainda não rodou (cerca de US$ 0,90 nas 3 rodadas).
- **O juiz contra uma pessoa:** a página para marcar 30 respostas está pronta e ainda não foi
  marcada.

## Onde olhar

- [`README.md`](../README.md): como rodar, as rotas e todas as decisões.
- [`docs/ATENDIMENTO.md`](ATENDIMENTO.md): cada etapa, cada rodada e cada erro, com as datas.
- [`avaliacao/resultados/`](../avaliacao/resultados/): os relatórios de cada rodada.
