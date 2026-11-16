# Publicar o atendimento

Passo a passo para quando o Gabriel disser "pode publicar". Até lá, nada vai para o GitHub.

O Render publica a branch `main`. O link que já foi mostrado não pode quebrar: a aba Triagem
tem que continuar igual a antes.

## Onde as coisas estão (15/11/2026)

- **No GitHub:** só a branch `main`, no commit `cccdcc0` ("Gravação dos exemplos e fotos da
  página", 05/11/2026). A branch `atendimento` nunca foi enviada.
- **Neste computador:** a branch `atendimento` tem tudo: o commit `5122266` (o Gemini no
  Vertex AI, que ainda não está no GitHub) e o atendimento inteiro, até a etapa 4.

## 1. Antes do push

1. **O plano do Google (decidido em 15/11/2026): o faturamento será ativado antes de publicar.**
   Confira no Google AI Studio que o projeto da `GEMINI_API_KEY` está ligado a uma conta de
   faturamento ativa. No plano gratuito, o Google usaria o que é enviado para melhorar os
   produtos, e pessoas poderiam ler; no pago, não. Quem visita a página pode escrever qualquer
   coisa, mesmo com o texto já mascarado. O resumo dos termos está no fim deste arquivo.
2. **Como o serviço roda (conferido em 15/11/2026): Docker, no plano Free do Render, sem
   disco.**
   - Desde a etapa 4, a imagem leva `base/` e `dados/`. Antes, o atendimento não subia na
     imagem e a rota respondia 503.
   - Sem disco, nada esconde o `dados/lojistas.json` da imagem: o atendimento sobe.
   - O sistema de arquivos é temporário: o SQLite da imagem (`/app/dados/triagem.db`) se apaga
     a cada publicação ou reinício. Já era assim antes. As rotas da página não gravam nada, então
     a demonstração não perde nada.
   - No plano Free, o serviço dorme sem visitas; a primeira visita depois disso demora mais.
3. Rodar os testes e o ruff: `pytest` e `ruff check .` e `ruff format --check .`.

## 2. As variáveis no painel do Render

Só os nomes. Os valores ficam no painel, nunca no Git.

| Variável | Situação |
|---|---|
| `ANTHROPIC_API_KEY` | Já existe. Confira que é a chave nova (a antiga foi trocada). |
| `GEMINI_API_KEY` | **Nova.** A chave do Google AI Studio, para a busca por sentido. Sem ela, a busca roda só por palavras e o resto funciona. |
| `CHAVE_API_APP` | Já existe. Protege `/chamados`, `/atendimento` e `/metricas`. |
| `URL_PUBLICA` | Já existe, se a prévia do link estiver ligada. Não muda. |
| `DATABASE_URL` | Só se o serviço usa um PostgreSQL. Não muda. |
| `DEMO_LIMITE_POR_HORA`, `DEMO_LIMITE_POR_DIA` | Opcionais (padrão: 10 por pessoa por hora e 200 por dia). Valem para a triagem e para o atendimento, com contas separadas. |

Não use `PROVEDOR_IA=gemini` no Render: o Gemini no Vertex AI precisa do login do Google Cloud,
que não existe lá.

Custo máximo por dia com os limites padrão: 200 atendimentos a cerca de US$ 0,001 e 200
triagens a cerca de US$ 0,00025, ou seja, perto de US$ 0,25.

## 3. O push e a junção no main

```bash
git fetch origin
# O main do GitHub não pode ter mudado. Esta linha tem que sair vazia:
git log --oneline atendimento..origin/main

# 1) A branch atendimento vai para o GitHub. O Render não publica esta branch.
git push origin atendimento

# 2) A junção no main. O Render publica quando o main chega ao GitHub.
git switch -c main origin/main
git -c user.email=128643986+LuisGabriel102@users.noreply.github.com \
    merge --no-ff atendimento -m "Junta o atendimento com IA (etapas 1 a 4)"
pytest
git push origin main
```

O push no `main` também dispara o CI (testes, a imagem Docker e a conferência da imagem no ar)
e o fluxo do GitHub Pages. A página do GitHub Pages ganha as abas; a aba Atendimento explica
que ele roda só ao vivo, e a triagem gravada continua igual.

## 4. O que conferir no ar

1. **`/saude`** responde `"status": "ok"` e `"ia_configurada": true`.
2. **Aba Triagem:** toque em "Cobrança em dobro". A ficha tem que sair como antes: Urgente,
   Financeiro, o CPF com tarja, o custo e o tempo.
3. **Aba Atendimento, 2 perguntas prontas:**
   - "Onde compro bobina": "Resolvido pela IA", a fonte "Bobina, como trocar e onde comprar o
     papel" abre o texto, e a busca diz "Por sentido" (prova que a `GEMINI_API_KEY` está lá;
     "Por palavras" quer dizer que ela falta ou falhou).
   - "Maquininha parada": "Chamou uma pessoa", a fila Suporte e a mensagem fixa de urgência.
4. **No celular:** abra o link, troque de aba, toque numa pergunta pronta e abra a fonte. Nada
   pode sair da largura da tela.
5. **A prévia do link:** o título e a imagem da prévia não mudaram (`og:title` e
   `app/estatico/previa.png` ficaram iguais).
6. **`/docs`:** as rotas `/demo/atendimento` e `/demo/lojistas` aparecem; `/atendimento` pede a
   chave.

## 5. Se algo der errado

- No Render, volte para o deploy anterior (Rollback, na lista de deploys). A triagem volta a
  ser a de antes.
- No Git, desfaça a junção sem apagar histórico: `git revert -m 1 <commit da junção>` e push no
  `main`.

## Os termos do Gemini (conferidos em 15/11/2026)

Página lida: os termos adicionais da API do Gemini (ai.google.dev/gemini-api/terms, que leva a
aistudio.google.com/docs/terms), com vigência de 23/03/2026.

- **Plano gratuito:** o Google usa o conteúdo enviado e as respostas para melhorar os produtos e
  a tecnologia de aprendizado de máquina; pessoas podem ler (desligado da conta antes). O termo
  pede para não enviar informação sensível, confidencial ou pessoal.
- **Plano pago** (projeto com faturamento ativo no Google Cloud): o Google não usa os pedidos e
  as respostas para melhorar os produtos. Guarda um registro por tempo limitado, só para detectar
  abuso e por obrigação legal.
- A tabela de preços marca os embeddings (`gemini-embedding-2`) do mesmo jeito: usados para
  melhorar os produtos no gratuito, não usados no pago.
