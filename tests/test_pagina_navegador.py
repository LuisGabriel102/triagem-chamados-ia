"""A página no navegador (Playwright), com clientes falsos: nada chama a Anthropic nem o Google.

Confere, em 390 px (celular) e 1280 px (computador), nas duas abas: nada vaza da largura da
tela, o contraste do texto e a navegação pelo teclado. E os dois caminhos de falha: o Google
fora do ar (a busca segue por palavras) e a IA fora do ar (entra o plano B).

Sem o Playwright e o Chromium instalados, os testes são pulados:
    pip install -e ".[captura]"
    python -m playwright install chromium
"""

import socket
import threading
import time
from collections.abc import Iterator

import anthropic
import httpx2
import pytest

sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn  # noqa: E402

from app.agente import AgenteClaude  # noqa: E402
from app.atendimento import ServicoAtendimento  # noqa: E402
from app.banco import criar_motor  # noqa: E402
from app.base_conhecimento import carregar_artigos  # noqa: E402
from app.busca import Busca  # noqa: E402
from app.busca_sentido import GeradorGemini, IndiceMemoria  # noqa: E402
from app.classificador import ClassificadorClaude  # noqa: E402
from app.config import Configuracao  # noqa: E402
from app.ferramentas import DadosLojistas  # noqa: E402
from app.main import criar_app  # noqa: E402
from app.servico import ServicoTriagem  # noqa: E402
from tests.falsos import (  # noqa: E402
    REQUISICAO_FALSA,
    ClienteAgenteFalso,
    ClienteEmbeddingFalso,
    ClienteFalso,
    entrada_valida,
    resposta_agente,
)

ARTIGOS = carregar_artigos()
SEM_REDE = anthropic.APIConnectionError(request=REQUISICAO_FALSA)
LARGURAS = (390, 1280)

# Conta o contraste de cada texto visível com o fundo de verdade (o primeiro ancestral com
# cor de fundo). Devolve os que ficam abaixo do mínimo da WCAG AA: 4,5 para texto comum e
# 3 para texto grande (24 px, ou 18,66 px em negrito).
CONTRASTE_JS = """
() => {
  const rgb = (c) => (c.match(/[\\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const fundo = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const c = rgb(getComputedStyle(e).backgroundColor);
      if (c.length >= 3 && (c.length < 4 || c[3] > 0.5)) return c;
    }
    return [255, 255, 255];
  };
  const ruins = [];
  let contados = 0, menor = 99;
  const andar = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (andar.nextNode()) {
    const no = andar.currentNode;
    const el = no.parentElement;
    if (!no.textContent.trim() || !el || el.closest(".so-leitor,template")) continue;
    if (!el.getClientRects().length) continue;
    const estilo = getComputedStyle(el);
    if (estilo.visibility === "hidden") continue;
    const a = lum(rgb(estilo.color)), b = lum(fundo(el));
    const razao = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    contados += 1; menor = Math.min(menor, razao);
    const tamanho = parseFloat(estilo.fontSize);
    const grande = tamanho >= 24 || (tamanho >= 18.66 && Number(estilo.fontWeight) >= 700);
    if (razao < (grande ? 3 : 4.5)) {
      ruins.push(`${no.textContent.trim().slice(0, 30)}: ${razao.toFixed(2)}`);
    }
  }
  return {ruins, contados, menor: Number(menor.toFixed(2))};
}
"""

# Elementos visíveis que passam da borda direita da tela (o leitor de tela fica de fora).
VAZAMENTO_JS = """
() => {
  const largura = document.documentElement.clientWidth;
  const fora = [];
  for (const el of document.querySelectorAll("body *")) {
    if (el.closest(".so-leitor,template")) continue;
    const r = el.getBoundingClientRect();
    if (r.width && r.right > largura + 1) {
      fora.push(`${el.tagName}.${el.className}: ${Math.round(r.right)}`);
    }
  }
  return {rolagem: document.documentElement.scrollWidth - largura, fora: fora.slice(0, 5)};
}
"""


def _atendimento(
    agente: ClienteAgenteFalso | None = None,
    triagem: ClienteFalso | None = None,
    busca: Busca | None = None,
) -> ServicoAtendimento:
    dados = DadosLojistas()
    cliente_triagem = triagem or ClienteFalso(
        entrada_valida(categoria="suporte_tecnico", prioridade="media", numero_pedido=None)
    )
    return ServicoAtendimento(
        ServicoTriagem(ClassificadorClaude(cliente_triagem, "claude-haiku-5-5")),
        busca or Busca(ARTIGOS, limiar_bm25=1.0),
        AgenteClaude(agente or ClienteAgenteFalso(), dados, "claude-haiku-5-5"),
        dados,
    )


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def servidor() -> Iterator[tuple[str, object]]:
    config = Configuracao(
        _env_file=None, anthropic_api_key=None, chave_api_app="segredo", demo_limite_por_hora=500
    )
    triagem = ServicoTriagem(ClassificadorClaude(ClienteFalso(), "claude-haiku-5-5"))
    app = criar_app(
        config=config, servico=triagem, motor=criar_motor("sqlite://"), atendimento=_atendimento()
    )
    porta = _porta_livre()
    servidor = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning")
    )
    linha = threading.Thread(target=servidor.run, daemon=True)
    linha.start()
    for _ in range(100):
        if servidor.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{porta}/", app
    servidor.should_exit = True
    linha.join(timeout=5)


@pytest.fixture(scope="module")
def navegador() -> Iterator[object]:
    with sync_api.sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch()
        except Exception as erro:  # o Chromium do Playwright não está instalado
            pytest.skip(f"Chromium do Playwright indisponível: {erro}")
        yield chromium
        chromium.close()


def _abrir(navegador, url: str, largura: int, esquema: str = "light"):
    pagina = navegador.new_page(viewport={"width": largura, "height": 900}, color_scheme=esquema)
    pagina.goto(url)
    return pagina


def _perguntar(pagina, nome: str) -> None:
    pagina.click("#aba-atendimento")
    pagina.wait_for_selector("#perguntas button")
    pagina.get_by_role("button", name=nome).click()
    pagina.wait_for_selector("#resultado-atendimento[data-estado='pronto']")


def _contraste_ok(pagina, minimo_de_textos: int) -> None:
    medida = pagina.evaluate(CONTRASTE_JS)
    print("contraste:", medida["contados"], "textos, menor razão", medida["menor"])
    assert medida["contados"] >= minimo_de_textos, medida
    assert medida["ruins"] == [], medida


def _sem_vazamento(pagina) -> None:
    medida = pagina.evaluate(VAZAMENTO_JS)
    assert medida["rolagem"] <= 0, medida
    assert medida["fora"] == [], medida


@pytest.mark.parametrize("largura", LARGURAS)
def test_as_duas_abas_cabem_na_tela(navegador, servidor, largura):
    url, app = servidor
    app.state.atendimento = _atendimento()
    pagina = _abrir(navegador, url, largura)
    assert pagina.get_by_text("Empresa e dados inventados. Não escreva dados reais.").is_visible()
    # Triagem, com a mensagem pronta, como antes.
    pagina.get_by_role("button", name="Cobrança em dobro").click()
    pagina.wait_for_selector("#resultado[data-estado='pronto']")
    _sem_vazamento(pagina)
    # Atendimento, com a fonte aberta.
    _perguntar(pagina, "Onde compro bobina")
    ficha = pagina.locator("#resultado-atendimento")
    assert "Resolvido pela IA" in ficha.inner_text()
    pagina.click(".fontes summary")
    assert pagina.locator(".artigo").is_visible()
    assert "Para trocar:" in pagina.locator(".artigo").inner_text()
    _sem_vazamento(pagina)
    pagina.close()


@pytest.mark.parametrize("esquema", ["light", "dark"])
def test_contraste_do_texto(navegador, servidor, esquema):
    url, app = servidor
    app.state.atendimento = _atendimento(
        ClienteAgenteFalso(("resposta", resposta_agente(precisa_pessoa=True, motivo="teste")))
    )
    pagina = _abrir(navegador, url, 1280, esquema)
    pagina.get_by_role("button", name="Cobrança em dobro").click()
    pagina.wait_for_selector("#resultado[data-estado='pronto']")
    _contraste_ok(pagina, 25)
    _perguntar(pagina, "Com dado pessoal")
    pagina.click(".fontes summary")
    _contraste_ok(pagina, 45)
    pagina.close()


def test_navegacao_pelo_teclado(navegador, servidor):
    url, app = servidor
    app.state.atendimento = _atendimento()
    pagina = _abrir(navegador, url, 390)
    pagina.focus("#aba-triagem")
    pagina.keyboard.press("ArrowRight")
    ativo = pagina.evaluate("document.activeElement.id")
    assert ativo == "aba-atendimento"
    assert pagina.get_attribute("#aba-atendimento", "aria-selected") == "true"
    assert pagina.is_visible("#painel-atendimento")
    assert pagina.is_hidden("#painel-triagem")
    # Tab sai da aba e entra no painel: o primeiro campo é a escolha da loja.
    pagina.keyboard.press("Tab")
    assert pagina.evaluate("document.activeElement.id") == "loja"
    # As perguntas prontas e a fonte funcionam com Enter.
    pagina.wait_for_selector("#perguntas button")
    pagina.focus("#perguntas button")
    pagina.keyboard.press("Enter")
    pagina.wait_for_selector("#resultado-atendimento[data-estado='pronto']")
    pagina.focus(".fontes summary")
    pagina.keyboard.press("Enter")
    assert pagina.locator(".artigo").is_visible()
    # Home volta para a primeira aba.
    pagina.focus("#aba-atendimento")
    pagina.keyboard.press("Home")
    assert pagina.get_attribute("#aba-triagem", "aria-selected") == "true"
    assert pagina.is_visible("#painel-triagem")
    pagina.close()


def test_o_endereco_com_atendimento_abre_a_aba(navegador, servidor):
    url, _ = servidor
    pagina = _abrir(navegador, f"{url}#atendimento", 1280)
    assert pagina.get_attribute("#aba-atendimento", "aria-selected") == "true"
    pagina.close()


def test_dado_pessoal_aparece_com_tarja(navegador, servidor):
    url, app = servidor
    app.state.atendimento = _atendimento()
    pagina = _abrir(navegador, url, 390)
    _perguntar(pagina, "Com dado pessoal")
    ficha = pagina.locator("#resultado-atendimento")
    texto = ficha.inner_text()
    assert "529.982.247-25" not in texto and "lia.nova@example.com" not in texto
    assert pagina.locator("#resultado-atendimento .tarja").count() == 2
    assert "Dados escondidos antes de chamar a IA" in texto
    pagina.close()


def test_google_fora_do_ar_a_pagina_responde_pela_busca_por_palavras(navegador, servidor):
    url, app = servidor
    gerador = GeradorGemini(ClienteEmbeddingFalso(erro=httpx2.ConnectError("sem rede")))
    indice = IndiceMemoria({artigo.id: [1.0] + [0.0] * 767 for artigo in ARTIGOS})
    busca = Busca(ARTIGOS, gerador, indice, limiar_bm25=1.0, limiar_similaridade=0.5)
    app.state.atendimento = _atendimento(busca=busca)
    pagina = _abrir(navegador, url, 390)
    _perguntar(pagina, "Onde compro bobina")
    ficha = pagina.locator("#resultado-atendimento")
    assert ficha.locator(".busca").inner_text() == "Por palavras"
    assert "A busca por sentido falhou" in ficha.locator(".avisos").inner_text()
    assert "A bobina térmica" in ficha.locator(".resposta-atendimento").inner_text()
    pagina.close()


def test_ia_fora_do_ar_a_pagina_mostra_o_plano_b(navegador, servidor):
    url, app = servidor
    app.state.atendimento = _atendimento(
        ClienteAgenteFalso(erro=SEM_REDE), triagem=ClienteFalso(erro=SEM_REDE)
    )
    pagina = _abrir(navegador, url, 390)
    _perguntar(pagina, "Onde compro bobina")
    ficha = pagina.locator("#resultado-atendimento")
    assert ficha.locator(".origem").inner_text() == "Plano B: trecho do artigo"
    assert ficha.locator(".faixa-prioridade").inner_text() == "Chamou uma pessoa"
    assert "Encontrei isto na nossa ajuda" in ficha.locator(".resposta-atendimento").inner_text()
    assert "a IA falhou" in ficha.locator(".motivos-pessoa").inner_text()
    pagina.close()


def test_limite_de_uso_aparece_como_erro(navegador, servidor):
    url, app = servidor
    app.state.atendimento = _atendimento()
    pagina = _abrir(navegador, url, 1280)
    pagina.route(
        "**/demo/atendimento",
        lambda rota: rota.fulfill(
            status=429,
            content_type="application/json",
            body='{"detail": "Você chegou ao limite de testes desta hora."}',
        ),
    )
    pagina.click("#aba-atendimento")
    pagina.wait_for_selector("#perguntas button")
    pagina.get_by_role("button", name="Onde compro bobina").click()
    erro = pagina.locator("#erro-atendimento")
    erro.wait_for()
    assert "limite de testes" in erro.inner_text()
    pagina.close()


def test_no_github_pages_a_triagem_gravada_segue_igual(navegador, tmp_path):
    import functools
    import json
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    from pathlib import Path

    from app.site_estatico import montar_site

    gravacao = Path(__file__).resolve().parent.parent / "docs" / "exemplos_gravados.json"
    montar_site(tmp_path, json.loads(gravacao.read_text("utf-8")))

    class Quieto(SimpleHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quieto, directory=tmp_path))
    threading.Thread(target=http.serve_forever, daemon=True).start()
    try:
        for largura in LARGURAS:
            pagina = _abrir(navegador, f"http://127.0.0.1:{http.server_address[1]}/", largura)
            pagina.wait_for_selector("#resultado[data-estado='pronto']")
            _sem_vazamento(pagina)
            pagina.click("#aba-atendimento")
            # O atendimento roda só ao vivo: a aba explica, sem formulário quebrado.
            assert pagina.is_visible("#so-ao-vivo")
            assert pagina.is_hidden("#formulario-atendimento")
            _sem_vazamento(pagina)
            pagina.close()
    finally:
        http.shutdown()


def test_mostra_a_consulta_aos_dados_da_loja(navegador, servidor):
    url, app = servidor
    app.state.atendimento = _atendimento(
        ClienteAgenteFalso(("consulta", "consultar_recebimentos"), ("resposta", resposta_agente()))
    )
    pagina = _abrir(navegador, url, 390)
    _perguntar(pagina, "Quando cai minha venda")
    consultas = pagina.locator("#resultado-atendimento .consultas").inner_text()
    assert consultas == "Consultou os dados da loja da sessão: os recebimentos."
    pagina.close()
