// A fila de revisão humana (/fila). Sem a chave da API, mostra o exemplo gravado
// (/estatico/fila_exemplo.json). Com a chave, lê /chamados?revisao_humana=true e
// /atendimentos?precisa_pessoa=true deste servidor. Tudo entra na tela como texto, nunca
// como HTML. A chave fica só numa variável: não vai para o localStorage.
(function () {
  "use strict";

  const ORDEM = { urgente: 0, alta: 1, media: 2, baixa: 3 };
  const PRIORIDADE = { urgente: "Urgente", alta: "Alta", media: "Média", baixa: "Baixa" };
  const TIPO = { triagem: "Triagem", atendimento: "Atendimento" };
  const MARCADOR = /(\[(?:CPF|CNPJ|CARTAO|EMAIL|TELEFONE|RG|ENDERECO|NOME)\])/;
  const DADO = {
    CPF: "CPF",
    CNPJ: "CNPJ",
    CARTAO: "cartão",
    EMAIL: "e-mail",
    TELEFONE: "telefone",
    RG: "RG",
    ENDERECO: "endereço",
    NOME: "nome",
  };

  const lista = document.getElementById("casos");
  const modelo = document.getElementById("modelo-caso");
  const contagem = document.getElementById("contagem");
  const filtro = document.getElementById("filtro-fila");
  const origem = document.getElementById("origem-fila");
  const erro = document.getElementById("erro-fila");
  let cartoes = [];

  function textoComTarjas(texto) {
    const pedacos = document.createDocumentFragment();
    for (const parte of (texto || "").split(MARCADOR)) {
      if (!parte) continue;
      const achado = parte.match(/^\[(\w+)\]$/);
      if (achado && DADO[achado[1]]) {
        // A mesma tarja da página principal, com o texto para leitor de tela.
        const tarja = document.createElement("span");
        tarja.className = "tarja";
        tarja.title = `${DADO[achado[1]]} escondido`;
        const rotulo = document.createElement("span");
        rotulo.className = "so-leitor";
        rotulo.textContent = "dado escondido: ";
        tarja.append(rotulo, DADO[achado[1]]);
        pedacos.append(tarja);
      } else {
        pedacos.append(document.createTextNode(parte));
      }
    }
    return pedacos;
  }

  // Os dados ao vivo viram o mesmo formato do exemplo gravado.
  function doChamado(c) {
    return {
      tipo: "triagem",
      titulo: `Chamado ${c.id}`,
      criado_em: c.criado_em,
      fila: c.fila,
      prioridade: c.prioridade,
      motivos: c.motivos_revisao || [],
      texto_mascarado: c.texto_mascarado,
      resumo: c.resumo,
      resposta: c.resposta_sugerida,
      rotulo_resposta: "Resposta sugerida para você revisar",
      fontes: [],
    };
  }

  function doAtendimento(a) {
    return {
      tipo: "atendimento",
      titulo: `Atendimento ${a.id}`,
      criado_em: a.criado_em,
      fila: a.fila,
      prioridade: a.prioridade,
      motivos: a.motivos_pessoa || [],
      texto_mascarado: a.texto_mascarado,
      resumo: null,
      resposta: a.resposta,
      rotulo_resposta: "O que o lojista já recebeu",
      fontes: (a.fontes || []).map((f) => f.titulo),
    };
  }

  function ordenar(itens) {
    // Urgente primeiro; dentro da mesma prioridade, o mais antigo espera menos tempo na fila.
    return [...itens].sort(
      (a, b) =>
        (ORDEM[a.prioridade] ?? 9) - (ORDEM[b.prioridade] ?? 9) ||
        String(a.criado_em || "").localeCompare(String(b.criado_em || ""))
    );
  }

  function preencherFiltro() {
    const atual = filtro.value;
    const filas = [...new Set(cartoes.map((c) => c.fila))].sort();
    filtro.replaceChildren(new Option("Todas", ""));
    for (const fila of filas) filtro.append(new Option(fila, fila));
    filtro.value = filas.includes(atual) ? atual : "";
  }

  function mostrar() {
    const visiveis = cartoes.filter((c) => !filtro.value || c.fila === filtro.value);
    lista.replaceChildren();
    for (const c of visiveis) {
      const item = modelo.content.firstElementChild.cloneNode(true);
      const preencher = (seletor, texto) => {
        item.querySelector(seletor).textContent = texto;
      };
      const prioridade = item.querySelector(".prioridade");
      prioridade.textContent = PRIORIDADE[c.prioridade] || c.prioridade;
      prioridade.dataset.prioridade = c.prioridade;
      preencher(".tipo", TIPO[c.tipo] || c.tipo);
      preencher(".fila", `Fila ${c.fila}`);
      preencher(".titulo", c.titulo);
      const quando = item.querySelector(".quando");
      if (c.criado_em) quando.textContent = new Date(c.criado_em).toLocaleString("pt-BR");
      else quando.hidden = true;
      const motivos = item.querySelector(".motivos");
      for (const motivo of c.motivos) {
        const li = document.createElement("li");
        li.textContent = motivo;
        motivos.append(li);
      }
      item.querySelector(".texto").append(textoComTarjas(c.texto_mascarado));
      const resumo = item.querySelector(".resumo");
      if (c.resumo) resumo.textContent = `Resumo da IA: ${c.resumo}`;
      else resumo.hidden = true;
      preencher(".rotulo-resposta", c.rotulo_resposta);
      preencher(".resposta", c.resposta);
      const fontes = item.querySelector(".fontes");
      if (c.fontes.length) fontes.textContent = `Fontes: ${c.fontes.join("; ")}`;
      else fontes.hidden = true;
      lista.append(item);
    }
    contagem.textContent = `(${visiveis.length})`;
    if (!visiveis.length) {
      const vazio = document.createElement("li");
      vazio.className = "vazio";
      vazio.textContent = "Nenhum caso esperando uma pessoa.";
      lista.append(vazio);
    }
  }

  function usar(itens, texto) {
    cartoes = ordenar(itens);
    origem.textContent = texto;
    preencherFiltro();
    mostrar();
  }

  async function carregarExemplo() {
    try {
      const resposta = await fetch("/estatico/fila_exemplo.json");
      const dados = await resposta.json();
      usar(
        dados.cartoes,
        "Exemplo: respostas reais da IA, gravadas uma vez. Para ver a fila de verdade deste " +
          "servidor, use a chave da API."
      );
    } catch {
      erro.textContent = "O exemplo não carregou. Recarregue a página.";
      erro.hidden = false;
    }
  }

  async function carregarAoVivo(chave) {
    erro.hidden = true;
    const cabecalhos = { "X-API-Key": chave };
    try {
      const [chamados, atendimentos] = await Promise.all([
        fetch("/chamados?revisao_humana=true&limite=100", { headers: cabecalhos }),
        fetch("/atendimentos?precisa_pessoa=true&limite=100", { headers: cabecalhos }),
      ]);
      if (chamados.status === 401 || atendimentos.status === 401) {
        erro.textContent = "Chave inválida.";
        erro.hidden = false;
        return;
      }
      if (!chamados.ok || !atendimentos.ok) {
        erro.textContent = "A fila não carregou. Tente de novo.";
        erro.hidden = false;
        return;
      }
      const itens = [
        ...(await chamados.json()).map(doChamado),
        ...(await atendimentos.json()).map(doAtendimento),
      ];
      usar(itens, "Ao vivo: os casos deste servidor que esperam uma pessoa (os 100 mais recentes de cada tipo).");
    } catch {
      erro.textContent = "O servidor não respondeu. Confira a conexão e tente de novo.";
      erro.hidden = false;
    }
  }

  document.getElementById("formulario-chave").addEventListener("submit", (evento) => {
    evento.preventDefault();
    const chave = document.getElementById("chave").value.trim();
    if (!chave) {
      erro.textContent = "Escreva a chave da API.";
      erro.hidden = false;
      return;
    }
    carregarAoVivo(chave);
  });
  filtro.addEventListener("change", mostrar);
  carregarExemplo();
})();
