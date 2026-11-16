// Página de demonstração. Funciona de dois jeitos:
// - ao vivo, servida pela API: a triagem chama /demo/triagem e o atendimento, /demo/atendimento;
// - gravada, no GitHub Pages: a triagem mostra respostas reais da IA já gravadas, sem custo.
//   O atendimento roda só ao vivo.
// Todo texto que vem da API ou da gravação entra por textContent, nunca como HTML:
// a mensagem do cliente, a resposta da IA e o texto dos artigos não viram código.
(() => {
  "use strict";

  const MODO = document.body.dataset.modo === "gravado" ? "gravado" : "ao-vivo";
  const LIMITE = 1000;
  const REPOSITORIO = "https://github.com/LuisGabriel102/triagem-chamados-ia";
  const ESTATICO = MODO === "gravado" ? "estatico/" : "/estatico/";

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
    dado: {
      CPF: "CPF",
      CNPJ: "CNPJ",
      CARTAO: "cartão",
      EMAIL: "e-mail",
      TELEFONE: "telefone",
      RG: "RG",
      ENDERECO: "endereço",
      NOME: "nome",
    },
    busca: { sentido: "Por sentido", hibrida: "Híbrida", palavras: "Por palavras" },
    ferramenta: {
      consultar_recebimentos: "os recebimentos",
      status_maquininha: "as maquininhas",
    },
  };

  const MARCADOR = /(\[(?:CPF|CNPJ|CARTAO|EMAIL|TELEFONE|RG|ENDERECO|NOME)\])/;

  const numero = (valor, casas) =>
    valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

  const textoDoContador = (texto) =>
    `${texto.length.toLocaleString("pt-BR")} de 1.000 caracteres`;

  // "claude-haiku-5-5" vira "Claude Haiku 5.5". Outro formato fica como veio.
  function nomeDoModelo(id) {
    const partes = String(id || "").split("-");
    if (partes[0] !== "claude" || partes.length < 3) return id || "IA";
    const versao = partes.slice(2).filter((p) => /^\d+$/.test(p));
    const nome = partes[1].charAt(0).toUpperCase() + partes[1].slice(1);
    return `Claude ${nome} ${versao.join(".")}`.trim();
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

  function rolarAte(elemento) {
    if (!window.matchMedia("(max-width: 60rem)").matches) return;
    const suave = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    elemento.scrollIntoView({ behavior: suave ? "smooth" : "auto", block: "start" });
  }

  async function carregarJson(endereco) {
    const resposta = await fetch(endereco);
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    return resposta.json();
  }

  function caixaDeErro(caixa) {
    return {
      mostrar(mensagem) {
        caixa.textContent = mensagem;
        caixa.hidden = false;
      },
      esconder() {
        caixa.hidden = true;
        caixa.textContent = "";
      },
    };
  }

  function mensagemDeErro(status, corpo, oQue) {
    if (status === 429 && typeof corpo.detail === "string") return corpo.detail;
    if (status === 422) return "A mensagem precisa ter de 1 a 1.000 caracteres.";
    if (status === 404) return "A demonstração está desligada neste servidor.";
    if (status === 503) return "O atendimento não está disponível neste servidor.";
    return `${oQue} não respondeu. Tente de novo em alguns segundos.`;
  }

  // --- Abas: setas, Home e End trocam de aba; Tab entra no painel. ---

  function iniciarAbas() {
    const abas = [...document.querySelectorAll('[role="tab"]')];
    const escolher = (aba, focar) => {
      for (const outra of abas) {
        const ativa = outra === aba;
        outra.setAttribute("aria-selected", String(ativa));
        outra.tabIndex = ativa ? 0 : -1;
        document.getElementById(outra.getAttribute("aria-controls")).hidden = !ativa;
      }
      if (focar) aba.focus();
      try {
        history.replaceState(null, "", aba.id === "aba-atendimento" ? "#atendimento" : "#triagem");
      } catch {
        // Sem histórico (página aberta de um arquivo, por exemplo): fica como está.
      }
    };
    abas.forEach((aba, i) => {
      aba.addEventListener("click", () => escolher(aba, false));
      aba.addEventListener("keydown", (evento) => {
        const destino = {
          ArrowRight: abas[(i + 1) % abas.length],
          ArrowLeft: abas[(i - 1 + abas.length) % abas.length],
          Home: abas[0],
          End: abas[abas.length - 1],
        }[evento.key];
        if (!destino) return;
        evento.preventDefault();
        escolher(destino, true);
      });
    });
    if (location.hash === "#atendimento") escolher(abas[1], false);
  }

  // --- Triagem ---

  const formulario = document.getElementById("formulario");
  const campoTexto = document.getElementById("texto");
  const campoCanal = document.getElementById("canal");
  const botao = document.getElementById("botao");
  const contador = document.getElementById("contador");
  const erroTriagem = caixaDeErro(document.getElementById("erro"));
  const resultado = document.getElementById("resultado");
  const modelo = document.getElementById("modelo-ficha");
  const lista = document.getElementById("exemplos");
  const aviso = document.getElementById("aviso-modo");

  function contar() {
    contador.textContent = textoDoContador(campoTexto.value);
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
    if (rolar) rolarAte(resultado);
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

  // Ao vivo: cada triagem chama a API.

  async function triarAoVivo() {
    erroTriagem.esconder();
    const texto = campoTexto.value.trim();
    if (!texto) {
      erroTriagem.mostrar("Escreva uma mensagem ou escolha um exemplo.");
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
        erroTriagem.mostrar(mensagemDeErro(resposta.status, corpo, "A triagem"));
        return;
      }
      mostrarResultado(corpo);
    } catch {
      voltarAoVazio();
      erroTriagem.mostrar("A triagem não respondeu. Confira a conexão e tente de novo.");
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
      criarBotoes(await carregarJson(`${ESTATICO}exemplos.json`), () => triarAoVivo());
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
        erroTriagem.esconder();
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

  // --- Atendimento (só ao vivo) ---

  const campoLoja = document.getElementById("loja");
  const campoMensagem = document.getElementById("mensagem");
  const formularioAtendimento = document.getElementById("formulario-atendimento");
  const botaoAtendimento = document.getElementById("botao-atendimento");
  const contadorAtendimento = document.getElementById("contador-atendimento");
  const erroAtendimento = caixaDeErro(document.getElementById("erro-atendimento"));
  const resultadoAtendimento = document.getElementById("resultado-atendimento");
  const modeloAtendimento = document.getElementById("modelo-atendimento");
  const listaPerguntas = document.getElementById("perguntas");

  const ORIGEM = { ia: null, plano_b: "Plano B: trecho do artigo", fixa: "Resposta fixa, sem IA" };

  // O texto do artigo vem em Markdown simples: parágrafos, "## título" e listas com
  // "- " ou "1. ". Vira elementos da página, sempre por textContent.
  function artigoEmElementos(texto) {
    const pedacos = document.createDocumentFragment();
    for (const bloco of texto.split(/\n\s*\n/)) {
      let listaAtual = null;
      let tipoLista = "";
      for (const linha of bloco.split("\n")) {
        const titulo = linha.match(/^#{1,6}\s+(.*)$/);
        const item = linha.match(/^\s*(?:([-*])|(\d+)[.)])\s+(.*)$/);
        if (titulo) {
          listaAtual = null;
          const h = document.createElement("h4");
          h.textContent = titulo[1];
          pedacos.append(h);
        } else if (item) {
          const tipo = item[1] ? "ul" : "ol";
          if (!listaAtual || tipoLista !== tipo) {
            listaAtual = document.createElement(tipo);
            tipoLista = tipo;
            pedacos.append(listaAtual);
          }
          const li = document.createElement("li");
          li.textContent = item[3];
          listaAtual.append(li);
        } else if (linha.trim()) {
          listaAtual = null;
          pedacos.append(paragrafo("", linha.trim()));
        }
      }
    }
    return pedacos;
  }

  function fonteAbrivel(fonte) {
    const item = document.createElement("li");
    const detalhes = document.createElement("details");
    const titulo = document.createElement("summary");
    titulo.textContent = fonte.titulo;
    const corpo = document.createElement("div");
    corpo.className = "artigo";
    corpo.append(artigoEmElementos(fonte.texto));
    detalhes.append(titulo, corpo);
    item.append(detalhes);
    return item;
  }

  function preencherLista(ficha, seletor, itens) {
    const destino = ficha.querySelector(seletor);
    for (const texto of itens) {
      const item = document.createElement("li");
      item.textContent = texto;
      destino.append(item);
    }
    return itens.length > 0;
  }

  function mostrarAtendimento(dados) {
    const ficha = modeloAtendimento.content.firstElementChild.cloneNode(true);
    const preencher = (seletor, texto) => {
      ficha.querySelector(seletor).textContent = texto;
    };

    const faixa = ficha.querySelector(".faixa");
    faixa.dataset.prioridade = dados.prioridade;
    preencher(".faixa-prioridade", dados.precisa_pessoa ? "Chamou uma pessoa" : "Resolvido pela IA");
    preencher(".faixa-rotulo", dados.precisa_pessoa ? "Fila" : "Prioridade");
    preencher(
      ".fila",
      dados.precisa_pessoa ? dados.fila : NOMES.prioridade[dados.prioridade] || dados.prioridade
    );

    preencher(".resposta-atendimento", dados.resposta);
    const fontes = ficha.querySelector(".fontes");
    for (const fonte of dados.fontes) fontes.append(fonteAbrivel(fonte));
    if (!dados.fontes.length) {
      fontes.replaceWith(paragrafo("sem-fonte", "Nenhum artigo: sem fonte, sem conselho."));
    }
    ficha.querySelector(".bloco-pessoa").hidden = !preencherLista(
      ficha,
      ".motivos-pessoa",
      dados.motivos_pessoa
    );
    ficha.querySelector(".bloco-removidas").hidden = !preencherLista(
      ficha,
      ".removidas",
      dados.frases_removidas
    );

    ficha.querySelector(".texto-lido").append(textoComTarjas(dados.texto_mascarado));
    preencher(".escondidos", listaDeEscondidos(dados.dados_pessoais_encontrados));
    const consultas = [...new Set(dados.ferramentas_usadas || [])].map(
      (nome) => NOMES.ferramenta[nome] || nome
    );
    preencher(
      ".consultas",
      consultas.length
        ? `Consultou os dados da loja da sessão: ${consultas.join(" e ")}.`
        : "Não consultou os dados da loja."
    );
    const avisos = ficha.querySelector(".avisos");
    avisos.textContent = dados.avisos.length ? `Avisos: ${dados.avisos.join(" ")}` : "";
    avisos.hidden = !dados.avisos.length;

    ficha.dataset.origem = dados.origem_resposta;
    preencher(".origem", ORIGEM[dados.origem_resposta] || nomeDoModelo(dados.modelo));
    preencher(".busca", NOMES.busca[dados.modo_busca] || dados.modo_busca);
    const custo = dados.custo.total_usd;
    preencher(".custo", custo > 0 ? `US$ ${numero(custo, 5)}` : "Grátis");
    preencher(".tempo", `${numero(dados.tempo.total_ms / 1000, 1)} s`);

    resultadoAtendimento.replaceChildren(ficha);
    resultadoAtendimento.dataset.estado = "pronto";
    rolarAte(resultadoAtendimento);
  }

  function atendimentoVazio() {
    resultadoAtendimento.dataset.estado = "vazio";
    resultadoAtendimento.replaceChildren(
      paragrafo("vazio", "A resposta aparece aqui. Escolha uma pergunta pronta ou escreva a sua.")
    );
  }

  function contarAtendimento() {
    contadorAtendimento.textContent = textoDoContador(campoMensagem.value);
  }

  async function atender() {
    erroAtendimento.esconder();
    const mensagem = campoMensagem.value.trim();
    if (!mensagem) {
      erroAtendimento.mostrar("Escreva uma mensagem ou escolha uma pergunta pronta.");
      campoMensagem.focus();
      return;
    }
    if (!campoLoja.value) {
      erroAtendimento.mostrar("As lojas não carregaram. Recarregue a página.");
      return;
    }
    botaoAtendimento.disabled = true;
    botaoAtendimento.textContent = "Respondendo…";
    resultadoAtendimento.dataset.estado = "carregando";
    resultadoAtendimento.replaceChildren(
      paragrafo("carregando", "Buscando na ajuda e escrevendo a resposta…")
    );
    try {
      const resposta = await fetch("/demo/atendimento", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mensagem,
          canal: "chat",
          sessao: { lojista_id: campoLoja.value },
        }),
      });
      const corpo = await resposta.json().catch(() => ({}));
      if (!resposta.ok) {
        atendimentoVazio();
        erroAtendimento.mostrar(mensagemDeErro(resposta.status, corpo, "O atendimento"));
        return;
      }
      mostrarAtendimento(corpo);
    } catch {
      atendimentoVazio();
      erroAtendimento.mostrar("O atendimento não respondeu. Confira a conexão e tente de novo.");
    } finally {
      botaoAtendimento.disabled = false;
      botaoAtendimento.textContent = "Enviar mensagem";
    }
  }

  async function iniciarAtendimento() {
    campoMensagem.addEventListener("input", contarAtendimento);
    formularioAtendimento.addEventListener("submit", (evento) => {
      evento.preventDefault();
      atender();
    });
    contarAtendimento();
    try {
      for (const loja of await carregarJson("/demo/lojistas")) {
        const opcao = document.createElement("option");
        opcao.value = loja.id;
        opcao.textContent = `${loja.nome} (${loja.plano})`;
        campoLoja.append(opcao);
      }
    } catch {
      erroAtendimento.mostrar("As lojas não carregaram. Recarregue a página.");
    }
    try {
      for (const pergunta of await carregarJson(`${ESTATICO}perguntas_atendimento.json`)) {
        const botaoPergunta = document.createElement("button");
        botaoPergunta.type = "button";
        botaoPergunta.textContent = pergunta.nome;
        botaoPergunta.addEventListener("click", () => {
          campoMensagem.value = pergunta.texto.slice(0, LIMITE);
          contarAtendimento();
          atender();
        });
        listaPerguntas.append(botaoPergunta);
      }
    } catch {
      listaPerguntas.replaceChildren(
        paragrafo("erro", "As perguntas prontas não carregaram. Escreva uma mensagem.")
      );
    }
  }

  iniciarAbas();
  if (MODO === "gravado") {
    iniciarGravado();
    document.getElementById("ao-vivo-atendimento").hidden = true;
    document.getElementById("so-ao-vivo").hidden = false;
    document.querySelector("#painel-atendimento .saida").hidden = true;
  } else {
    iniciarAoVivo();
    iniciarAtendimento();
  }
})();
