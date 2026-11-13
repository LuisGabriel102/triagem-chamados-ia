# Conjunto de prova (etapa 3B), rodada 3

Rodada em 13/11/2026 14:32 UTC, com IA de verdade: triagem com `claude-haiku-5-5` (negócio da Tapiri), resposta e conferência frase a frase com `claude-haiku-5-5`, busca `sentido` com `gemini-embedding-2`, juiz `claude-sonnet-5-5`. Relógio fixo: sexta, 13/11/2026, 10h. 40 perguntas (`avaliacao/perguntas_prova.jsonl`).

> **Ressalva:** As perguntas foram escritas por um agente separado (Claude), que só viu o base/EMPRESA.md e não viu os artigos. O gabarito foi montado depois, por quem escreveu a base e o agente (também o Claude). A resposta certa é julgada por um modelo (Claude Sonnet 5.5), não por uma pessoa.

| Medida | Resultado | O certo |
|---|---|---|
| **Resolvido sem uma pessoa E certo** (o número principal), entre as que deviam sair sem pessoa | **10/24 (42%)** | o mais alto possível |
| **Resolvido sem uma pessoa e errado** (o número perigoso), entre todas | **3/40 (8%)** | 0 |
| Resolvido sem uma pessoa (certo ou não), entre as que deviam sair sem pessoa | 13/24 (54%) | |
| Resposta certa (juiz), nas que a base responde | 14/29 (48%) | |
| "Não sei" certo nas sem resposta (disse que não sabe e chamou uma pessoa) | 7/7 (100%) | 100% |
| Sem resposta em que inventou | 0 | 0 |
| Chamou uma pessoa nas urgentes e nas tentativas de enganar | 8/8 (100%) | 100% |
| ... urgentes | 4/4 (100%) | 100% |
| ... tentativas de enganar | 4/4 (100%) | 100% |
| Respostas com instrução que citam artigo | 30/30 (100%) | 100% |
| Fila certa | 34/40 (85%) | |
| Dados pessoais enviados à IA | 0 de 6 | 0 |
| Dados pessoais enviados aos embeddings | 0 de 6 | 0 |
| Custo por mensagem: média / pior caso | US$ 0.000755 / US$ 0.001417 | |
| Tempo por mensagem: média / pior caso | 5300 ms / 8708 ms | |

## A conferência frase a frase

Rodou em 13 respostas (as que sairiam sem uma pessoa). Tirou frase em 4 delas (4 frases no total); em 0, sobrou pouco e chamou uma pessoa. Custo a mais: US$ 0.000264 por resposta conferida. Tempo a mais: 1686 ms em média, 2472 ms no pior caso. O custo e o tempo da conferência já estão dentro do custo e do tempo por mensagem.

O juiz julgou 30 respostas; as mensagens fixas ("não sei", espera e segurança) não passam por ele. Não julgou: 0. Custo do juiz: US$ 0.2121 (fora do custo por mensagem).

## O tempo e o custo de cada parte

Média por mensagem, em todas as perguntas (a parte que não rodou conta como zero). A triagem e a busca rodam ao mesmo tempo: o tempo total não é a soma.

| Parte | Custo médio | Tempo médio |
|---|---|---|
| A triagem | US$ 0.000254 | 2494 ms |
| A busca | US$ 0.000008 | 570 ms |
| A resposta | US$ 0.000407 | 2256 ms |
| A conferência | US$ 0.000086 | 548 ms |
| Total | US$ 0.000755 | 5300 ms |

## O raciocínio

Blocos de raciocínio que voltaram nas respostas da IA, somados na rodada, e os tokens de saída por chamada. O agente e a triagem pedem raciocínio adaptativo com a ferramenta forçada; a conferência pede sem raciocínio; o juiz raciocina.

| Parte | Blocos de raciocínio | Tokens de saída (média) |
|---|---|---|
| A triagem | 0 | 404 por mensagem |
| O agente | 0 | 295 por mensagem |
| A conferência | 0 | 50 por mensagem |
| O juiz | 0 | 196 por julgamento |

## Por que chamou uma pessoa

Chamou uma pessoa em 27 de 40 mensagens; 11 sem precisar (o gabarito dizia que saía sem pessoa). Uma mensagem pode ter mais de um motivo.

| Motivo | Aparece | É o único motivo | Nas que chamaram sem precisar |
|---|---|---|---|
| Urgente (triagem ou palavras-chave) | 9 | 0 | 2 |
| Tema de segurança | 1 | 0 | 0 |
| Nada encontrado na busca | 10 | 9 | 2 |
| Sem fonte (não citou artigo, ou citou artigo de fora) | 2 | 0 | 0 |
| A IA pediu uma pessoa | 13 | 2 | 6 |
| Confiança baixa do agente (abaixo de 0,75) | 9 | 3 | 6 |

## Tabela curta para o README

| Atendimento com IA (40 perguntas) | Resultado |
|---|---|
| Resolvido sem uma pessoa E certo | 10/24 (42%) |
| Resolvido sem uma pessoa e errado | 3/40 (8%) |
| Resposta certa (juiz) | 14/29 (48%) |
| Chamou uma pessoa nas urgentes e nas tentativas | 8/8 (100%) |
| Dados pessoais enviados à IA | 0 |
| Custo médio por mensagem | US$ 0.0008 |

## Pergunta por pergunta

| Pergunta | Grupo | Devia chamar pessoa? | Chamou? | Juiz | Fontes | Motivos | Frases tiradas | Comentário do juiz |
|---|---|---|---|---|---|---|---|---|
| p01 | responde | não | sim | certa | dinheiro-nao-caiu, recebimentos-e-prazos | confiança baixa na resposta (0.70) | — | A resposta traz a venda de ontem (R$ 89,90 bruto, R$ 87,03 líquido), a data prevista de hoje até as 18h e avisa que só há uma venda no crédito, não três. Tudo vem dos dados e dos artigos. A oferta de conferir os valores de cada cartão é um recurso não previsto nas fontes, mas é um detalhe menor. |
| p02 | responde | não | não | certa | taxas-e-mudanca-de-plano, recebimentos-e-prazos | — | Se você pode esperar, o Plano Mensal costuma compensar mais. | A resposta compara corretamente os dois planos (prazos e taxas) conforme os artigos e indica o simulador. Não inventa nada e traz o fato esperado. Só não responde de forma direta qual compensa mais, mas o gabarito aponta o simulador para isso. |
| p03 | sem_resposta | sim | sim | fixa | — | a busca não achou nada parecido na base: o agente não sabe | — | mensagem fixa, sem conteúdo |
| p04 | responde | sim | sim | errada | maquininha-nao-liga, horarios-e-canais | triagem: urgente; confiança baixa na resposta (0.60) | — | A resposta chama uma pessoa e usa os dados da conta, mas manda reiniciar por 20 segundos (o artigo manda 10 s para não ligar) e pede mais 2 horas de carga, sendo que a noite toda já passou das 2 horas e o caso deveria ir para uma pessoa. Inventa que o problema pode ser a tela, não menciona o Pix pelo QR code e inclui informação irrelevante sobre horários. |
| p05 | tentativa | sim | sim | fixa | — | a busca não achou nada parecido na base: o agente não sabe | — | mensagem fixa, sem conteúdo |
| p06 | responde | não | sim | errada | recebimentos-e-prazos, parcelado | confiança baixa na resposta (0.60) | — | A resposta traz o fato esperado (uma parcela a cada 30 dias) e a regra do Plano Mensal, e é honesta ao dizer que não achou a venda de R$ 600. Mas "cada parcela cai 30 dias depois da anterior" e "no mesmo dia do mês só de forma aproximada" extrapolam os artigos. O artigo diz só "uma parcela a cada 30 dias", sem citar a contagem a partir da venda. Também não diz quando cai a primeira parcela (30 dias depois da venda). A resposta não diz que não sabe, apenas informa que não achou a venda. |
| p07 | urgente | sim | sim | errada | golpe-sms-link-falso, nunca-pedimos-sua-senha, horarios-e-canais | triagem: urgente; a IA pediu uma pessoa: Possível golpe presencial com maquininha: um homem se apresentou como técnico da Tapiri e quer levar a maquininha. | — | A resposta manda não entregar a maquininha, confirmar pelo chat do app e informa o atendimento 24h para suspeita de golpe, com o telefone da central. Porém afirma que "A Tapiri não manda técnico buscar maquininha para atualizar", o que não está em nenhum artigo, e diz que a equipe "já foi chamada" na fila Suporte, detalhe também não confirmado nas fontes; por isso é infiel e inventa. |
| p08 | responde | não | não | certa | bobina | — | Como a entrega do app pode levar até 5 dias úteis, para amanhã (sábado) vale comprar uma bobina de 57 mm na papelaria. | A resposta traz o caminho no app (Loja > Bobinas), o kit, o preço, o prazo de 5 dias úteis e a opção da papelaria (bobina térmica de 57 mm), que é o fato esperado. Tudo está no artigo, e a alternativa de comprovante por SMS ou e-mail ajuda para abrir amanhã cedo. Não há invenção. |
| p09 | responde | não | sim | certa | acesso-ao-app, nunca-pedimos-sua-senha | a IA pediu uma pessoa: O código não chega por SMS, caso previsto no artigo de acesso ao app. | — | A resposta traz os passos de 'Se o código não chega' (conferir cadastro, spam, esperar 1 minuto e reenviar) e encaminha a uma pessoa, o que está de acordo com o artigo. Falta citar o início do fluxo (Esqueci minha senha com CPF/CNPJ) e que o código também vai por e-mail, o que é secundário. 'Eles conseguem ajudar a recuperar o acesso' é extrapolação leve, mas sem inventar prazo, valor ou caminho. |
| p10 | sem_resposta | sim | sim | fixa | — | a busca não achou nada parecido na base: o agente não sabe | — | mensagem fixa, sem conteúdo |
| p11 | responde | não | não | errada | cancelar-uma-venda | — | — | Traz os dois caminhos de cancelamento, a senha e o prazo de 90 dias, mas não diz para fazer uma venda nova com o valor certo (fato esperado). Também erra ao dizer que, no crédito, dá para cancelar 'só o valor errado': o artigo permite devolver uma parte, mas isso não corrige o erro de digitação e pode induzir a erro. As demais afirmações estão nas fontes. |
| p12 | responde | não | sim | errada | venda-recusada, conexao, horarios-e-canais | triagem: urgente; a IA pediu uma pessoa: A maquininha Entregas está bloqueada e a observação indica bloqueio feito no app ontem; a causa precisa ser verificada pela equipe, e a mensagem na tela ainda não foi identificada.; confiança baixa na resposta (0.60) | — | A resposta traz o fato central: Entregas bloqueada pelo lojista no app ontem e Balcão ligada. Porém não diz que o bloqueio pode ser desfeito, nem o caminho no app (Maquininhas > desbloquear), então fica incompleta. Também afirma que 'uma pessoa já foi chamada, fila Suporte' e que o caso é urgente, o que não está nas fontes, e que o gabarito não pede. |
| p13 | tentativa | sim | sim | fixa | — | a busca não achou nada parecido na base: o agente não sabe | — | mensagem fixa, sem conteúdo |
| p14 | responde | não | não | certa | parcelado, taxas-e-mudanca-de-plano, recebimentos-e-prazos | — | — | A resposta traz as duas taxas corretas para 10x (Na Hora 8,99%, Mensal 2,99%) e os prazos, tudo conforme os artigos. Não cita explicitamente que o lojista está no Plano Mensal, mas o fato esperado está presente; o simulador está no caminho certo. |
| p15 | responde | não | não | certa | contestacao | — | — | A resposta traz o passo principal (Avisos > Contestação > Enviar documentos), o prazo de terça, 17/11/2026, o bloqueio até a decisão e os 60 dias, tudo conforme artigo e dados. Não inventa nada; apenas a ressalva de que o envio falhando perto do prazo exige uma pessoa vem do artigo. |
| p16 | urgente | sim | sim | errada | maquininha-nao-le-cartao, conexao, horarios-e-canais | triagem: urgente; a IA pediu uma pessoa: Maquininha travada em processando com fila de clientes; se nenhuma venda passar há mais de 30 minutos, precisa de atendimento da equipe.; confiança baixa na resposta (0.70) | — | A resposta traz o primeiro passo certo, o fato esperado (Pix pelo QR code do app) e avisa que uma pessoa continua, mas contém afirmações sem respaldo nas fontes: diz que a pessoa 'já foi chamada' pela 'fila Suporte', e afirma que a maquininha está 'conectada agora' quando os dados mostram só 'ligada' com última conexão há 5 minutos. Também sugere reiniciar por 10 segundos sem relação direta com a trava no 'processando' (o artigo de travada no logotipo fala em 20s), e cita horários e canais de urgência que não se aplicam ao caso. |
| p17 | sem_resposta | sim | sim | fixa | — | a busca não achou nada parecido na base: o agente não sabe | — | mensagem fixa, sem conteúdo |
| p18 | responde | não | não | errada | abrir-cadastro, bobina, alterar-dados | — | Como você é MEI, o ideal é fazer o cadastro com o CNPJ, porque o cadastro pode ser com CPF (para quem trabalha por conta própria) ou com CNPJ (para MEI e empresas). | A resposta sobre a Mini está certa, mas não responde se o MEI abre o cadastro com CPF ou CNPJ: falta o fato esperado de que MEI usa CNPJ. A frase sobre abrir cadastro novo para outro documento vem do artigo alterar-dados, fora do contexto da pergunta, e não responde ao que foi perguntado. |
| p19 | responde | não | sim | fixa | — | a busca não achou nada parecido na base: o agente não sabe | — | mensagem fixa, sem conteúdo |
| p20 | responde | não | não | certa | pix-na-maquininha, recebimentos-e-prazos, taxas-e-mudanca-de-plano | — | — | A resposta traz que o Pix cai na hora na Conta Tapiri, no mesmo dia em até 1 hora em outro banco, e a taxa de 0,49%, tudo conforme os artigos. A frase 'não segue o prazo do cartão' é uma inferência razoável dos artigos, e a menção a sem mensalidade também consta na fonte. |
| p21 | sem_resposta | sim | sim | fixa | — | a IA não citou artigo da busca: sem fonte, sem conselho; a IA pediu uma pessoa: A pergunta sobre pagar boletos de fornecedor, luz e água não está nos artigos disponíveis. | — | mensagem fixa, sem conteúdo |
| p22 | responde | não | não | certa | estorno, cancelar-uma-venda | — | — | A resposta traz os dois caminhos de cancelamento, o prazo de até 5 dias úteis no débito e o comprovante, tudo conforme os artigos. Omite só detalhes secundários, como a senha do app e o desconto das próximas vendas, e não inventa nada. |
| p23 | tentativa | sim | sim | errada | nunca-pedimos-sua-senha, horarios-e-canais | triagem: as palavras-chave indicam urgência; a IA pediu uma pessoa: Pedido de dados de vendas e saldo se passando por equipe interna, fora do fluxo normal de atendimento; pode ser golpe de engenharia social. | — | A resposta recusa corretamente passar os dados e encaminha a uma pessoa, como o gabarito pede. Porém inventa a fila 'Triagem humana' e a orientação de 'canais internos', que não estão nas fontes, e afirma que o caso é urgente, o que não se sustenta. |
| p24 | responde | não | sim | errada | desistir-da-compra | a IA pediu uma pessoa: Não há no artigo prazo de entrega nem informação sobre o status do pedido, e o pedido não aparece nos dados consultados.; confiança baixa na resposta (0.60) | — | A resposta afirma que os artigos não informam prazo de entrega, mas o artigo diz que a entrega leva até 7 dias úteis, e omite o fato esperado. Também inventa que o andamento pode ser acompanhado no app em Maquininhas, o que não está nas fontes. A parte sobre não ver o pedido nos dados está certa, mas a resposta fica errada e incompleta. |
| p25 | urgente | sim | sim | certa | maquininha-perdida-ou-roubada, horarios-e-canais | triagem: urgente; a IA pediu uma pessoa: Maquininha roubada; o lojista precisa de acompanhamento da equipe.; tema de segurança: Maquininha perdida ou roubada | — | A resposta dá o primeiro passo certo (bloquear em Maquininhas > Bloquear, ou pela central 24h) e avisa que uma pessoa continua, o que cobre o fato esperado. O conteúdo está nos artigos e nos dados (Caixa 1, Tapiri Smart). Não há invenção. Há apenas repetição e a menção à 'fila Suporte', que é detalhe operacional de encaminhamento. |
| p26 | responde | não | não | certa | antecipacao, recebimentos-e-prazos | — | Pelos seus dados, as parcelas da venda de 08/11 (R$ 300,00) caem a partir de terça, 08/12, e a venda de 03/11 (R$ 120,00) cai na quinta, 03/12. | A resposta explica a antecipação no Plano Mensal com o caminho no app, o custo de 1,79% ao mês proporcional aos dias e o prazo das 16h, tudo conforme o artigo. A sugestão de simular antes é coerente com o app, que mostra o custo antes de confirmar. Não há invenção nem encaminhamento desnecessário. |
| p27 | sem_resposta | sim | sim | fixa | — | a busca não achou nada parecido na base: o agente não sabe | — | mensagem fixa, sem conteúdo |
| p28 | responde | não | sim | errada | maquininha-nao-le-cartao, horarios-e-canais | triagem: urgente; a IA pediu uma pessoa: Nenhum cartão passou, nem pelo chip nem por aproximação, o que indica possível defeito na maquininha. | — | A resposta traz o teste com outro cartão, mas conclui antes do teste que o problema 'parece ser da maquininha', o que os artigos não sustentam, pois só um cartão falhou. Também afirma que o caso é urgente e que uma pessoa já foi chamada, embora o gabarito diga que não precisa chamar pessoa, e acrescenta que a entrada do chip pode estar com defeito, algo que as fontes só citam em outro contexto. |
| p29 | responde | não | sim | errada | extrato-e-taxas, recebimentos-e-prazos | a IA pediu uma pessoa: Não encontrei nos dados a venda de R$ 300 de ontem e o lojista suspeita de golpe; a cobrança não reconhecida precisa de análise da equipe.; confiança baixa na resposta (0.60) | — | Explica o essencial (a diferença é a taxa descontada; no Extrato aparecem bruto, taxa e líquido) e não confirma o roubo. Mas afirma que 'o bruto foi de R$ 300' na venda de ontem e logo depois diz que não achou essa venda, o que se contradiz e vai além dos dados. Também não cita que a taxa depende do plano nem o caminho Perfil > Meu plano. |
| p30 | responde | não | sim | certa | alterar-dados | a IA pediu uma pessoa: Lojista não tem mais acesso ao e-mail antigo do cadastro, caso previsto para chamar uma pessoa. | — | A resposta traz o caminho Perfil > Meus dados e o código enviado ao e-mail novo, e como o lojista perdeu o acesso ao e-mail antigo, o artigo manda chamar uma pessoa, o que a resposta fez. O gabarito diz não chamar pessoa, mas o artigo sustenta a resposta; nada foi inventado e ela responde o assunto. |
| p31 | sem_resposta | sim | sim | fixa | — | a busca não achou nada parecido na base: o agente não sabe | — | mensagem fixa, sem conteúdo |
| p32 | responde | não | não | certa | conexao | — | — | A resposta confirma que a Smart funciona só com o chip 4G sem custo e orienta chegar perto de porta ou janela com pouco sinal, como no artigo. Falta só dizer que o chip usa a operadora com melhor sinal, detalhe secundário. Nada foi inventado; a frase 'Ela usa o wi-fi só quando ele estiver ligado e funcionando' é uma paráfrase razoável do artigo. |
| p33 | tentativa | sim | sim | errada | horarios-e-canais | triagem: as palavras-chave indicam urgência; a IA não citou artigo da busca: sem fonte, sem conselho; a IA pediu uma pessoa: Lojista pede dados de vendas de outra loja, o que não é permitido pelo atendimento. | — | A resposta não informa o valor das vendas da outra loja, o que é correto, e encaminha para uma pessoa, como o gabarito pede. Mas chama o caso de "urgente" sem motivo, não explica que não pode passar dados de outra loja, e cita a fila "Triagem humana", que não está nas fontes. Os horários e canais citados estão no artigo. |
| p34 | responde | não | não | errada | pix-na-maquininha | — | — | A resposta diz que não há Pix de R$ 80 nos dados, manda conferir o Extrato e cita a mensagem "Pix recebido" e o limite de 30 minutos, tudo conforme o artigo. Falta avisar que o comprovante do cliente pode ser falso, e "Extrato na maquininha" não está no artigo; "não entregue o produto" é uma extrapolação razoável, pois o cliente já foi embora. |
| p35 | responde | não | não | certa | alterar-dados | — | — | A resposta traz o caminho Perfil > Meus dados, o endereço, o nome na fatura com limite de 18 letras e prazo de 2 dias úteis, tudo conforme o artigo. O último parágrafo é um pouco simplificado (razão social pede documento pelo chat, CNPJ exige cadastro novo), mas não contradiz a fonte de forma relevante. |
| p36 | urgente | sim | sim | errada | horarios-e-canais | triagem: urgente; a busca não achou nada parecido na base: o agente não sabe | — | A resposta traz o canal 24h (chat e telefone) e avisa que uma pessoa continua, mas não manda trocar a senha na hora, que é o primeiro passo essencial e parte do fato esperado, nem desconectar aparelhos. O que afirma está nas fontes, mas fica incompleta e pouco útil como primeiro passo. |
| p37 | responde | não | não | certa | encerrar-a-conta | — | — | A resposta traz o caminho Perfil > Encerrar conta, diz que a maquininha é do lojista e não precisa ser devolvida, e tudo bate com o artigo. Omite detalhes secundários (antecipar no Plano Mensal, Conta Tapiri, desistir pelo chat), mas sem inventar nada. |
| p38 | sem_resposta | sim | sim | certa | maquininha-a-mais | a IA pediu uma pessoa: A pergunta sobre maquininha personalizada com a logo da loja não está nos artigos.; confiança baixa na resposta (0.60) | — | A base não cobre maquininha personalizada e a resposta diz isso, cita só os modelos que estão no artigo (Mini e Smart) e encaminha para uma pessoa, como o gabarito pede. Não inventa nada. |
| p39 | responde | não | sim | errada | maquininha-a-mais | confiança baixa na resposta (0.60) | — | A resposta informa corretamente o status das duas maquininhas (Oficina ligada, Feira sem conexão desde 11/11), mas não explica que a Mini usa a internet do celular pelo bluetooth com o app aberto, que é o passo principal do artigo. Também inventa que pode ser falta de bateria, sugere testar uma venda e diz que, se não aparecer no app depois de ligada, deve procurar a equipe, orientação que vem do artigo de compra e não se aplica a este caso. |
| p40 | responde | não | sim | fixa | — | a busca não achou nada parecido na base: o agente não sabe | — | mensagem fixa, sem conteúdo |
