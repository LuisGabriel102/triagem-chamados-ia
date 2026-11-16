"""As 6 perguntas prontas do atendimento, pela página, e as fotos das duas abas.

Dois jeitos:

    python scripts/capturar_atendimento.py --ao-vivo
        GASTA (centavos): sobe a API com o .env, clica nas 6 perguntas prontas uma vez,
        com a IA de verdade, e grava as respostas em docs/atendimento_gravado.json.
        Precisa da ANTHROPIC_API_KEY e da GEMINI_API_KEY no .env.

    python scripts/capturar_atendimento.py
        NÃO GASTA: sobe a API sem chave nenhuma e devolve, para a página, as respostas já
        gravadas (do atendimento e da triagem, em docs/exemplos_gravados.json). Tira as
        fotos das duas abas em 390 px (celular) e 1280 px (computador), em docs/fotos/.

    pip install -e ".[captura]"
    python -m playwright install chromium
"""

import argparse
import json
import socket
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import uvicorn  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from app.config import Configuracao  # noqa: E402
from app.main import criar_app  # noqa: E402

PERGUNTAS = RAIZ / "app" / "estatico" / "perguntas_atendimento.json"
GRAVACAO = RAIZ / "docs" / "atendimento_gravado.json"
TRIAGEM_GRAVADA = RAIZ / "docs" / "exemplos_gravados.json"
FOTOS = RAIZ / "docs" / "fotos"
LOJA = "loja-001"
# A foto do atendimento mostra esta pergunta, com a fonte aberta.
PERGUNTA_DA_FOTO = "Quando cai minha venda"
EXEMPLO_DA_TRIAGEM = "Cobrança em dobro"


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def subir(config: Configuracao) -> tuple[str, uvicorn.Server, threading.Thread]:
    porta = _porta_livre()
    servidor = uvicorn.Server(
        uvicorn.Config(criar_app(config=config), host="127.0.0.1", port=porta, log_level="warning")
    )
    linha = threading.Thread(target=servidor.run, daemon=True)
    linha.start()
    for _ in range(200):
        if servidor.started:
            return f"http://127.0.0.1:{porta}/", servidor, linha
        time.sleep(0.05)
    raise RuntimeError("A API não subiu.")


def ao_vivo(pasta: Path) -> int:
    config = Configuracao(database_url=f"sqlite:///{pasta / 'demo.db'}")
    if not (config.anthropic_api_key and config.anthropic_api_key.get_secret_value()):
        print("ANTHROPIC_API_KEY não configurada. Nada foi rodado.")
        return 1
    perguntas = json.loads(PERGUNTAS.read_text("utf-8"))
    url, servidor, linha = subir(config)
    gravadas = []
    try:
        with sync_playwright() as playwright:
            navegador = playwright.chromium.launch()
            pagina = navegador.new_page(viewport={"width": 1280, "height": 900})
            pagina.goto(f"{url}#atendimento")
            pagina.wait_for_selector("#perguntas button")
            pagina.select_option("#loja", LOJA)
            for pergunta in perguntas:
                with pagina.expect_response("**/demo/atendimento", timeout=90_000) as chegou:
                    pagina.get_by_role("button", name=pergunta["nome"]).click()
                resposta = chegou.value
                corpo = resposta.json()
                pagina.wait_for_selector("#resultado-atendimento[data-estado='pronto']")
                gravadas.append({**pergunta, "lojista": LOJA, "status": resposta.status, **corpo})
                print(
                    f"{pergunta['nome']}: status {resposta.status}, "
                    f"pessoa={corpo.get('precisa_pessoa')}, origem={corpo.get('origem_resposta')}, "
                    f"US$ {corpo.get('custo', {}).get('total_usd')}"
                )
            navegador.close()
    finally:
        servidor.should_exit = True
        linha.join(timeout=10)
    GRAVACAO.write_text(
        json.dumps(
            {
                "gravado_em": datetime.now(UTC).isoformat(timespec="seconds"),
                "aviso": "Respostas reais da IA às 6 perguntas prontas, rodadas uma vez. "
                "Empresa e dados inventados.",
                "respostas": gravadas,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        "utf-8",
    )
    total = sum(r.get("custo", {}).get("total_usd", 0) for r in gravadas)
    print(f"Gravado em {GRAVACAO.relative_to(RAIZ)}. Custo das 6: US$ {total:.5f}")
    return 0


def fotos(pasta: Path) -> int:
    if not GRAVACAO.exists():
        print("Falta docs/atendimento_gravado.json. Rode antes com --ao-vivo.")
        return 1
    respostas = {r["texto"]: r for r in json.loads(GRAVACAO.read_text("utf-8"))["respostas"]}
    triagens = {
        e["texto"]: e["resultado"]
        for e in json.loads(TRIAGEM_GRAVADA.read_text("utf-8"))["exemplos"]
    }
    # Sem chave nenhuma: nada aqui chama a IA. A página recebe as respostas gravadas.
    config = Configuracao(
        _env_file=None,
        anthropic_api_key=None,
        gemini_api_key=None,
        google_cloud_project="",
        database_url=f"sqlite:///{pasta / 'demo.db'}",
    )
    url, servidor, linha = subir(config)

    def gravada(rota, banco: dict) -> None:
        enviado = json.loads(rota.request.post_data or "{}")
        chave = enviado.get("mensagem") or enviado.get("texto")
        corpo = banco[chave]
        rota.fulfill(status=200, content_type="application/json", body=json.dumps(corpo))

    FOTOS.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            navegador = playwright.chromium.launch()
            for largura in (390, 1280):
                pagina = navegador.new_page(
                    viewport={"width": largura, "height": 900},
                    device_scale_factor=2 if largura == 390 else 1,
                    color_scheme="light",
                )
                pagina.route("**/demo/atendimento", lambda r: gravada(r, respostas))
                pagina.route("**/demo/triagem", lambda r: gravada(r, triagens))
                pagina.goto(url)
                pagina.get_by_role("button", name=EXEMPLO_DA_TRIAGEM).click()
                pagina.wait_for_selector("#resultado[data-estado='pronto']")
                pagina.wait_for_timeout(600)
                pagina.evaluate("window.scrollTo(0, 0)")
                pagina.screenshot(path=str(FOTOS / f"triagem-{largura}.png"), full_page=True)

                pagina.click("#aba-atendimento")
                pagina.wait_for_selector("#perguntas button")
                pagina.select_option("#loja", LOJA)
                pagina.get_by_role("button", name=PERGUNTA_DA_FOTO).click()
                pagina.wait_for_selector("#resultado-atendimento[data-estado='pronto']")
                pagina.click("#resultado-atendimento .fontes summary")
                pagina.wait_for_timeout(600)
                pagina.evaluate("window.scrollTo(0, 0)")
                pagina.screenshot(path=str(FOTOS / f"atendimento-{largura}.png"), full_page=True)

                # A fila de revisão humana, com o exemplo gravado (sem chave).
                pagina.goto(f"{url}fila")
                pagina.wait_for_selector("#casos .caso")
                pagina.wait_for_timeout(400)
                pagina.screenshot(path=str(FOTOS / f"fila-{largura}.png"), full_page=True)
                pagina.close()
            navegador.close()
    finally:
        servidor.should_exit = True
        linha.join(timeout=10)
    print("Pronto: docs/fotos/ triagem, atendimento e fila, em 390 e 1280 px")
    return 0


VIDEO = RAIZ / "docs" / "video" / "demonstracao.webm"
# O roteiro do vídeo: um caso que a IA resolve (com a fonte aberta) e um que chama uma pessoa.
PERGUNTAS_DO_VIDEO = ["Quando cai minha venda", "Maquininha parada"]


def video(pasta: Path) -> int:
    """Grava um vídeo curto da página com as respostas gravadas. NÃO GASTA.

    As respostas chegam na hora (vêm do arquivo), então o roteiro tem pausas para dar tempo de
    ler. O custo e o tempo que aparecem na tela são os da gravação real.
    """
    if not GRAVACAO.exists():
        print("Falta docs/atendimento_gravado.json. Rode antes com --ao-vivo.")
        return 1
    respostas = {r["texto"]: r for r in json.loads(GRAVACAO.read_text("utf-8"))["respostas"]}
    triagens = {
        e["texto"]: e["resultado"]
        for e in json.loads(TRIAGEM_GRAVADA.read_text("utf-8"))["exemplos"]
    }
    config = Configuracao(
        _env_file=None,
        anthropic_api_key=None,
        gemini_api_key=None,
        google_cloud_project="",
        database_url=f"sqlite:///{pasta / 'demo.db'}",
    )
    url, servidor, linha = subir(config)

    def gravada(rota, banco: dict) -> None:
        enviado = json.loads(rota.request.post_data or "{}")
        corpo = banco[enviado.get("mensagem") or enviado.get("texto")]
        rota.fulfill(status=200, content_type="application/json", body=json.dumps(corpo))

    tamanho = {"width": 1100, "height": 760}
    try:
        with sync_playwright() as playwright:
            navegador = playwright.chromium.launch()
            contexto = navegador.new_context(
                viewport=tamanho,
                color_scheme="light",
                record_video_dir=str(pasta / "video"),
                record_video_size=tamanho,
            )
            pagina = contexto.new_page()
            pagina.route("**/demo/atendimento", lambda r: gravada(r, respostas))
            pagina.route("**/demo/triagem", lambda r: gravada(r, triagens))
            pagina.goto(url)
            pagina.wait_for_timeout(1500)
            pagina.get_by_role("button", name=EXEMPLO_DA_TRIAGEM).click()
            pagina.wait_for_selector("#resultado[data-estado='pronto']")
            pagina.locator("#resultado").scroll_into_view_if_needed()
            pagina.wait_for_timeout(3500)

            pagina.evaluate("window.scrollTo(0, 0)")
            pagina.click("#aba-atendimento")
            pagina.wait_for_selector("#perguntas button")
            pagina.select_option("#loja", LOJA)
            pagina.wait_for_timeout(1200)
            for nome in PERGUNTAS_DO_VIDEO:
                pagina.get_by_role("button", name=nome).click()
                pagina.wait_for_selector("#resultado-atendimento[data-estado='pronto']")
                pagina.locator("#resultado-atendimento").scroll_into_view_if_needed()
                pagina.wait_for_timeout(2500)
                fonte = pagina.locator("#resultado-atendimento .fontes summary").first
                if fonte.count():
                    fonte.click()
                    pagina.wait_for_timeout(2500)
                pagina.evaluate("window.scrollTo(0, 0)")
                pagina.wait_for_timeout(800)
            gravacao = pagina.video
            # O vídeo só termina de ser escrito quando o contexto fecha, e só pode ser salvo
            # enquanto o navegador ainda está aberto.
            contexto.close()
            VIDEO.parent.mkdir(parents=True, exist_ok=True)
            gravacao.save_as(str(VIDEO))
            navegador.close()
    finally:
        servidor.should_exit = True
        linha.join(timeout=10)
    print(f"Pronto: {VIDEO.relative_to(RAIZ)} ({VIDEO.stat().st_size // 1024} KB)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ao-vivo", action="store_true", help="roda as 6 com a IA (gasta)")
    parser.add_argument("--video", action="store_true", help="grava o vídeo (não gasta)")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as pasta:
        if args.ao_vivo:
            return ao_vivo(Path(pasta))
        if args.video:
            return video(Path(pasta))
        return fotos(Path(pasta))


if __name__ == "__main__":
    raise SystemExit(main())
