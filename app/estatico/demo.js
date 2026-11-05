// Página de demonstração. Funciona de dois jeitos:
// - ao vivo, servida pela API: manda o chamado para /demo/triagem;
// - gravada, no GitHub Pages: mostra respostas reais da IA já gravadas, sem custo.
// Todo texto que vem da API ou da gravação entra por textContent, nunca como HTML:
// a mensagem do cliente e a resposta da IA não viram código.
(() => {
  "use strict";

  const MODO = document.body.dataset.modo === "gravado" ? "gravado" : "ao-vivo";
  const LIMITE = 1000;
  const REPOSITORIO = "https://github.com/LuisGabriel102/triagem-chamados-ia";

  const NOMES = {
    categoria: {
      financeiro: "Financeiro",
      suporte_tecnico: "Suporte técnico",
      comercial: "Comercial",
      cancelamento: "Cancelamento",
      reclamacao: "Reclamação",
      outros: "Outros",
    },
    prioridade: { urgente: "Urgente", alta: "Alta", media: "Média", baixa: "Baixa" },
    sentimento: { positivo: "Positivo", neutro: "Neutro", negativo: "Negativo" },
    dado: { CPF: "CPF", CNPJ: "CNPJ", CARTAO: "cartão", EMAIL: "e-mail", TELEFONE: "telefone" },
  };

  const MARCADOR = /(\[(?:CPF|CNPJ|CARTAO|EMAIL|TELEFONE)\])/;

  const formulario = document.getElementById("formulario");
  const campoTexto = document.getElementById("texto");
  const campoCanal = document.getElementById("canal");
  const botao = document.getElementById("botao");
  const contador = document.getElementById("contador");
  const caixaErro = document.getElementById("erro");
  const resultado = document.getElementById("resultado");
  const modelo = document.getElementById("modelo-ficha");
  const lista = document.getElementById("exemplos");
  const aviso = document.getElementById("aviso-modo");

  const numero = (valor, casas) =>
    valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

  // "claude-haiku-5-5" vira "Claude Haiku 5.5". Outro formato fica como veio.
  function nomeDoModelo(id) {
    const partes = String(id || "").split("-");
    if (partes[0] !== "claude" || partes.length < 3) return id || "IA";
    const versao = partes.slice(2).filter((p) => /^\d+$/.test(p));
    const nome = partes[1].charAt(0).toUpperCase() + partes[1].slice(1);
    return `Claude ${nome} ${versao.join(".")}`.trim();
  }

  function contar() {
    contador.textContent = `${campoTexto.value.length.toLocaleString("pt-BR")} de 1.000 caracteres`;
  }

  function mostrarErro(mensagem) {
    caixaErro.textContent = mensagem;
    caixaErro.hidden = false;
  }

  function esconderErro() {
    caixaErro.hidden = true;
    caixaErro.textContent = "";
  }

  function paragrafo(classe, texto) {
    const p = document.createElement("p");
    p.className = classe;
    p.textContent = texto;
    return p;
  }

  function textoComTarjas(texto) {
    const pedacos = document.createDocumentFragment();
    for (const parte of texto.split(MARCADOR)) {
      if (!parte) continue;
      const achado = parte.match(/^\[(\w+)\]$/);
      if (achado && NOMES.dado[achado[1]]) {
        const tarja = document.createElement("span");
        tarja.className = "tarja";
        tarja.title = `${NOMES.dado[achado[1]]} escondido`;
        const rotulo = document.createElement("span");
        rotulo.className = "so-leitor";
        rotulo.textContent = "dado escondido: ";
        tarja.append(rotulo, NOMES.dado[achado[1]]);
        pedacos.append(tarja);
      } else {
        pedacos.append(document.createTextNode(parte));
      }
    }
    return pedacos;
  }

  function listaDeEscondidos(encontrados) {
    const itens = Object.entries(encontrados || {});
    if (!itens.length) return "Nenhum dado pessoal encontrado.";
    const partes = itens.map(([tipo, quantidade]) => `${NOMES.dado[tipo] || tipo} (${quantidade})`);
    return `Dados escondidos antes de chamar a IA: ${partes.join(", ")}.`;
  }

  function mostrarResultado(dados, rolar = true) {
    const ficha = modelo.content.firstElementChild.cloneNode(true);
    const preencher = (seletor, texto) => {
      ficha.querySelector(seletor).textContent = texto;
    };

    const faixa = ficha.querySelector(".faixa");
    faixa.dataset.prioridade = dados.prioridade;
    preencher(".faixa-prioridade", NOMES.prioridade[dados.prioridade] || dados.prioridade);
    preencher(".fila", dados.fila);

    preencher(
      ".revisao",
      dados.revisao_humana ? "Uma pessoa revisa antes de seguir." : "Liberado sem revisão humana."
    );
    const motivos = ficha.querySelector(".motivos");
    for (const motivo of dados.motivos_revisao || []) {
      const item = document.createElement("li");
      item.textContent = motivo;
      motivos.append(item);
    }

    preencher(".categoria", NOMES.categoria[dados.categoria] || dados.categoria);
    preencher(".sentimento", NOMES.sentimento[dados.sentimento] || dados.sentimento);
    preencher(
      ".confianca",
      dados.confianca === null ? "Não se aplica" : `${Math.round(dados.confianca * 100)}%`
    );
    preencher(".pedido", dados.numero_pedido || "Não citado");

    ficha.querySelector(".texto-lido").append(textoComTarjas(dados.texto_mascarado));
    preencher(".escondidos", listaDeEscondidos(dados.dados_pessoais_encontrados));
    preencher(".resumo", dados.resumo);
    preencher(".resposta", dados.resposta_sugerida);
    preencher(".justificativa", dados.justificativa);

    const pelaIA = dados.origem === "ia";
    ficha.dataset.origem = dados.origem;
    preencher(".origem", pelaIA ? nomeDoModelo(dados.modelo) : "Plano B por regras");
    preencher(".custo", dados.custo_usd > 0 ? `US$ ${numero(dados.custo_usd, 5)}` : "Grátis");
    preencher(".tempo", `${numero(dados.tempo_ms / 1000, 1)} s`);

    resultado.replaceChildren(ficha);
    resultado.dataset.estado = "pronto";

    if (rolar && window.matchMedia("(max-width: 60rem)").matches) {
      const suave = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      resultado.scrollIntoView({ behavior: suave ? "smooth" : "auto", block: "start" });
    }
  }

  function voltarAoVazio() {
    resultado.dataset.estado = "vazio";
    resultado.replaceChildren(
      paragrafo("vazio", "O resultado aparece aqui. Escreva uma mensagem ou escolha um exemplo.")
    );
  }

  function criarBotoes(exemplos, aoEscolher) {
    for (const exemplo of exemplos) {
      const botaoExemplo = document.createElement("button");
      botaoExemplo.type = "button";
      botaoExemplo.textContent = exemplo.nome;
      botaoExemplo.addEventListener("click", () => {
        campoTexto.value = exemplo.texto.slice(0, LIMITE);
        campoCanal.value = exemplo.canal;
        contar();
        aoEscolher(exemplo);
      });
      lista.append(botaoExemplo);
    }
  }

  async function carregarJson(endereco) {
    const resposta = await fetch(endereco);
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    return resposta.json();
  }

  // Ao vivo: cada triagem chama a API.

  function mensagemDeErro(status, corpo) {
    if (status === 429 && typeof corpo.detail === "string") return corpo.detail;
    if (status === 422) return "A mensagem precisa ter de 1 a 1.000 caracteres.";
    if (status === 404) return "A demonstração está desligada neste servidor.";
    return "A triagem não respondeu. Tente de novo em alguns segundos.";
  }

  async function triarAoVivo() {
    esconderErro();
    const texto = campoTexto.value.trim();
    if (!texto) {
      mostrarErro("Escreva uma mensagem ou escolha um exemplo.");
      campoTexto.focus();
      return;
    }
    botao.disabled = true;
    botao.textContent = "Fazendo a triagem…";
    resultado.dataset.estado = "carregando";
    resultado.replaceChildren(paragrafo("carregando", "Lendo o chamado…"));
    try {
      const resposta = await fetch("/demo/triagem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto, canal: campoCanal.value }),
      });
      const corpo = await resposta.json().catch(() => ({}));
      if (!resposta.ok) {
        voltarAoVazio();
        mostrarErro(mensagemDeErro(resposta.status, corpo));
        return;
      }
      mostrarResultado(corpo);
    } catch {
      voltarAoVazio();
      mostrarErro("A triagem não respondeu. Confira a conexão e tente de novo.");
    } finally {
      botao.disabled = false;
      botao.textContent = "Fazer triagem";
    }
  }

  async function iniciarAoVivo() {
    campoTexto.addEventListener("input", contar);
    formulario.addEventListener("submit", (evento) => {
      evento.preventDefault();
      triarAoVivo();
    });
    contar();
    try {
      criarBotoes(await carregarJson("/estatico/exemplos.json"), () => triarAoVivo());
    } catch {
      lista.replaceChildren(paragrafo("erro", "Os exemplos não carregaram. Escreva uma mensagem."));
    }
  }

  // Gravado: respostas reais da IA, gravadas uma vez. Nenhuma chamada a cada visita.

  function avisarGravacao(gravacao) {
    const data = new Date(gravacao.gravado_em).toLocaleDateString("pt-BR", { timeZone: "UTC" });
    const link = document.createElement("a");
    link.href = REPOSITORIO;
    link.textContent = "o passo a passo está no GitHub";
    aviso.replaceChildren(
      `Estas são respostas reais da IA (${nomeDoModelo(gravacao.modelo)}), gravadas em ${data}. ` +
        "Para testar com a sua mensagem, rode o projeto no seu computador: ",
      link,
      "."
    );
  }

  async function iniciarGravado() {
    botao.hidden = true;
    contador.hidden = true;
    campoTexto.readOnly = true;
    campoCanal.disabled = true;
    campoTexto.placeholder = "Escolha um exemplo acima.";
    formulario.addEventListener("submit", (evento) => evento.preventDefault());
    try {
      const gravacao = await carregarJson("exemplos_gravados.json");
      avisarGravacao(gravacao);
      criarBotoes(gravacao.exemplos, (exemplo) => {
        esconderErro();
        mostrarResultado(exemplo.resultado);
      });
      const primeiro = gravacao.exemplos[0];
      if (primeiro) {
        campoTexto.value = primeiro.texto;
        campoCanal.value = primeiro.canal;
        mostrarResultado(primeiro.resultado, false);
      }
    } catch {
      lista.replaceChildren(paragrafo("erro", "Os exemplos gravados não carregaram. Recarregue a página."));
    }
  }

  if (MODO === "gravado") {
    iniciarGravado();
  } else {
    iniciarAoVivo();
  }
})();
