# Os erros da etapa 3, classificados antes de qualquer conserto (etapa 3B)

Feito em 13/11/2026, antes de mudar o código da etapa 3B. As 60 perguntas da etapa 3
(`avaliacao/perguntas_agente.jsonl`) viraram o conjunto de **desenvolvimento**: podem ser usadas
para achar problemas. O conserto é só o que for geral (prompt, regra), nunca um caso de cada vez.

Fontes: `agente.json` (rodada 1) e `agente_rodada2.json` (rodada 2), com o comentário do juiz
de cada resposta reprovada. Cada erro tem um tipo principal.

## Os tipos

| Tipo | O que é | Rodada 1 | Rodada 2 |
|---|---|---|---|
| Incompleta | Responde, mas deixa de fora o passo principal ou o fato pedido | 5 (a03, a05, a08, a45, a51) | 6 (a03, a05, a08, a42, a51, a52) |
| Errada | Afirma algo que contradiz o artigo ou os dados | 4 (a06, a16, a21, a25) | 3 (a06, a16, a45) |
| Inventou | Afirma algo que não está no artigo nem nos dados (caminho, promessa, suposição) | 3 (a24, a33, a50) | 5 (a25, a33, a50, a57, a59) |
| Artigo errado | A resposta se apoiou em artigo que não era o do assunto | 0 | 0 |
| Não respondeu o que foi perguntado | "Não sei" numa pergunta que a base responde, ou trecho do plano B que não toca a pergunta | 5 (a09, a11, a28, a47, a56) | 6 (a09, a11, a28, a40, a47, a56) |
| **Total** | | **17** | **20** |

Notas:
- "Artigo errado" deu 0: em toda resposta reprovada, o artigo certo estava entre as fontes. A
  a33 e a a59 não têm artigo no gabarito (a base não cobre).
- O "não respondeu" tem três causas diferentes:
  - a busca ficou abaixo do limiar e deu "não sei" (a09, a11, a47, a56);
  - a urgência sem artigo recebeu só "não sei" (a28);
  - a API da Anthropic caiu (InternalServerError) e o plano B mandou um trecho do artigo que
    não tocava a pergunta (a40, na rodada 2; a39 a a43 caíram no plano B).
- Dois erros também prometem uma ação da equipe que o artigo não promete ("vou pedir que uma
  pessoa acompanhe", "vou encaminhar"): a05 e a52, na rodada 2.

## Por que o agente chamou uma pessoa sem precisar (as 35 que deviam sair sem pessoa)

Tirando a confiança e o "outros" da triagem (decisão 1 da etapa 3B), sobram estes motivos na
rodada 2:

| Motivo que sobra | Casos |
|---|---|
| Nenhum: só a triagem chamava uma pessoa | a01, a12, a24, a36, a48, a53, a57 |
| A IA pediu uma pessoa por precaução ("se não funcionar, chame a equipe"), num caso que o artigo resolve | a03, a08, a27, a34 |
| A busca deu "nada encontrado" | a09, a47, a56 |
| Confiança baixa da própria IA (as duas respostas estavam erradas) | a06, a45 |
| A triagem marcou urgente | a21, a25 |
| A API caiu e respondeu o plano B | a39, a40, a42, a43 |

## O que é geral e vai ser consertado

1. **Errada e inventou → conferência frase a frase** (decisão 3), nas respostas que saem sem uma
   pessoa. Mais três regras gerais no prompt do agente:
   - não prometer ação da equipe (o aviso de que uma pessoa continua é posto pelo sistema);
   - se a venda, o valor ou a data citados pelo lojista não aparecem nos dados, dizer isso, sem
     escolher a venda mais parecida;
   - se a mensagem traz uma premissa que contradiz os dados (por exemplo, o dia de hoje), usar os
     dados e dizer isso.
2. **Incompleta → regra no prompt:** começar pelo passo principal do artigo e trazer o prazo, o
   valor ou a data que o lojista quer saber. O limite de "umas 80 palavras" pode estar cortando o
   passo principal; passa para umas 120.
3. **Chamar uma pessoa por precaução → regra no prompt:** marcar precisa_pessoa só quando o caso,
   do jeito que o lojista contou, já bate com o bloco "Quando chamar uma pessoa". Se é só uma
   possibilidade ("se depois disso não funcionar"), dizer na resposta quando procurar a equipe, sem
   marcar.
4. **A urgência sem artigo (a28) → mensagem fixa de urgência** (decisão 4).
5. **A triagem só para a fila e a urgência** (decisão 1).

## O que não vai ser consertado, e por quê

- **A busca abaixo do limiar** (a09, a11, a47, a56). O limiar sai das 20 perguntas de calibração.
  Mudá-lo olhando as 60 seria ajustar ao conjunto. Fica anotado como limite conhecido.
- **A queda da API** (a39 a a43). O cliente já tenta de novo 2 vezes. É falha do provedor, e o
  plano B já chama uma pessoa.
- **A confiança baixa da própria IA** continua chamando uma pessoa. Nas duas vezes em que ela
  sobrou sozinha (a06 e a45), a resposta estava errada. Ela conta como "a IA pede uma pessoa".
