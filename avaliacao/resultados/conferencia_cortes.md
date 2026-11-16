# Os 22 cortes da conferência medida sozinha (rodada de 13/11/2026)

**O que foi a rodada.** Em 13/11/2026, a conferência frase a frase rodou isolada sobre as
respostas guardadas antes da conferência em duas rodadas das 60 de desenvolvimento
(`dev_v2_mudanca1b` e `dev_v2_mudanca2`): 53 respostas, 385 frases, US$ 0,0255. Ela marcou 22
frases como sem apoio, e nas 22 o trecho apontado estava mesmo na frase (pela regra do código,
todas seriam cortadas).

**A versão da conferência.** A do commit `432d70b` (a mudança 1 completa: para cortar, a
conferência aponta o trecho na frase), com o Claude Haiku 5.5 e o raciocínio desligado. O pedido,
a ferramenta e a regra do corte são os mesmos de hoje (16/11/2026); depois disso só entraram
um campo e um atributo usados pela conferência por citação. Uma diferença do script de 13/11 em
relação ao atendimento: ele mandava à conferência os dados das duas consultas da loja, mesmo
quando o agente não tinha consultado.

**Quem classificou.** As 22 frases foram classificadas uma a uma por um modelo (o Claude Code),
em 16/11/2026, não por uma pessoa, contra os artigos citados na resposta e os dados da loja na
hora da rodada (sexta, 13/11/2026, 10h). A lista das frases veio do resultado guardado da rodada
de 13/11 (o script e a saída ficaram fora do repositório). A contagem de 13/11 ("10 a 13 eram
certas, 6 eram cortes certos e 3 ficaram em dúvida") não ficou registrada frase a frase e soma
19, não 22.

- **certa:** o que a frase afirma está nos artigos citados ou nos dados (o corte foi errado);
- **corte certo:** a frase traz um fato que as fontes não têm ou contradiz as fontes;
- **em dúvida:** depende de interpretação.

## O resultado

| Classificação | Frases |
|---|---|
| Certa (o corte foi errado) | **14** |
| Corte certo | **3** |
| Em dúvida | **5** |
| **Total** | **22** |

A conferência acertou de 3 a 8 dos 22 cortes, conforme as 5 em dúvida.

## Frase a frase

| # | Resposta | Frase cortada | Classificação | Motivo |
|---|---|---|---|---|
| 1 | 1b a14 | Como a compra foi na última semana e a maquininha ainda está na caixa, você está dentro dos 7 dias corridos contados da entrega. | corte certo | O artigo conta 7 dias da entrega; a data da entrega não aparece, então "você está dentro" é conclusão sem apoio. |
| 2 | 1b a21 | Não parece ser a maquininha. | em dúvida | Os dados mostram a maquininha conectada e o artigo diz que a recusa vem do banco, mas "toda hora" pode ser o caso de todas as vendas recusadas, que o artigo liga à maquininha. |
| 3 | 1b a27 | Calma, a impressora provavelmente não quebrou. | certa | O artigo: papel em branco quer dizer bobina ao contrário. |
| 4 | 1b a27 | Tire a bobina e vire ela ao contrário. | certa | O artigo: "a bobina está ao contrário: vire e tente de novo". |
| 5 | 1b a40 | A antecipação cobra 1,79% ao mês, e não de uma vez só. | certa | O artigo: 1,79% ao mês, proporcional aos dias. |
| 6 | 1b a42 | Sim. | certa | Sem fato próprio; responde à pergunta que o artigo confirma. |
| 7 | 1b a42 | A Tapiri Mini aceita pagamento por aproximação, já ligado de fábrica. | certa | O artigo: toda maquininha Tapiri aceita, já ligado de fábrica (é o exemplo do próprio prompt da conferência). |
| 8 | 1b a43 | No domingo e nos feriados não há atendimento humano. | em dúvida | O humano no chat é de segunda a sábado, menos feriados nacionais; mas há atendimento 24 horas para urgências pelo telefone da central. |
| 9 | 1b a45 | Se o valor não cair até as 18h de hoje, procure a equipe da Tapiri. | certa | O artigo de prazos (citado) chama uma pessoa quando a data prevista passa; os dados dão a previsão de hoje até as 18h. |
| 10 | 1b a57 | Mas o sinal pode variar de lugar para lugar, então não é garantido que pegue em todo ponto da loja. | em dúvida | O artigo manda chegar perto de porta ou janela com pouco sinal; "não é garantido que pegue em todo ponto" é conclusão que ele sugere, mas não diz. |
| 11 | a2 a01 | Se até as 18h de hoje não aparecer na sua conta, procure a equipe da Tapiri. | certa | O mesmo da 9. |
| 12 | a2 a12 | Hoje é sexta, então um pedido feito agora cairia na segunda, 16/11. | corte certo | O artigo: pedido até as 16h de dia útil cai no mesmo dia; às 10h de sexta, cairia na sexta. A frase contradiz a fonte. |
| 13 | a2 a14 | Sim, você pode desistir sem custo e sem explicar o motivo, desde que o pedido seja feito em até 7 dias corridos contados da entrega da maquininha. | certa | É o artigo quase palavra por palavra. |
| 14 | a2 a17 | Sim, o valor pode ser descontado, mas você tem como se defender. | em dúvida | A defesa está no artigo; mas os dados mostram o valor bloqueado, e "descontado" vale só quando o dinheiro já caiu. |
| 15 | a2 a17 | Você tem 7 dias corridos para enviar sua defesa, até terça, 17/11/2026. | certa | O artigo dá os 7 dias corridos; os dados dão o prazo de terça, 17/11/2026. |
| 16 | a2 a18 | Se a venda foi ontem, quinta, 12/11/2026, o dinheiro deve cair em segunda, 14/12/2026 (dia 13/12 é domingo). | corte certo | Data calculada pela IA: 30 dias depois de 12/11 é 12/12, e o artigo não manda o crédito para o dia útil seguinte. |
| 17 | a2 a40 | Ela só existe no Plano Mensal. | certa | O artigo: existe no Plano Mensal; no Na Hora não há o que antecipar. |
| 18 | a2 a42 | Sim, a Tapiri Mini aceita pagamento por aproximação, e ela já vem com essa função ligada. | certa | O mesmo da 7. |
| 19 | a2 a50 | Se já cancelou, faça uma venda nova de 15. | em dúvida | O artigo diz "se cancelar por engano, faça uma venda nova"; aplicar isso à venda de 15 é um passo a mais. |
| 20 | a2 a51 | Olhei suas vendas e não encontrei um valor que explique os 80 reais. | certa | Os dados não têm nenhuma venda que explique 80 reais. |
| 21 | a2 a51 | Os valores que faltam podem ser vendas que ainda não caíram, já que o crédito no Plano Mensal cai em 30 dias. | certa | O artigo do dinheiro que não caiu dá exatamente esse motivo, com o crédito do Plano Mensal em 30 dias. |
| 22 | a2 a57 | Mas o sinal pode variar de lugar para lugar. | certa | O artigo trata do sinal fraco e manda chegar perto de porta ou janela. |

"1b" é a rodada `dev_v2_mudanca1b`; "a2" é a `dev_v2_mudanca2`.
