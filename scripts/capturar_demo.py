"""Tira a foto da página de demonstração com a IA de verdade.

Precisa da ANTHROPIC_API_KEY no .env. Faz 1 chamada à IA (menos de 1 centavo).

    pip install -e ".[captura]"
    python -m playwright install chromium
    python scripts/capturar_demo.py

Gera:
    docs/demo.png             foto da página, para o README
    app/estatico/previa.png   imagem que aparece quando o link é colado no LinkedIn
"""

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = "Cobrança em dobro"


def porta_livre() -> int:
    with socket.socket() as conexao:
        conexao.bind(("127.0.0.1", 0))
        return conexao.getsockname()[1]


def esperar_api(url: str, segundos: float = 30) -> dict:
    fim = time.monotonic() + segundos
    while True:
        try:
            with urllib.request.urlopen(f"{url}/saude", timeout=2) as resposta:
                return json.load(resposta)
        except OSError:
            if time.monotonic() > fim:
                raise
            time.sleep(0.3)


def main() -> int:
    porta = porta_livre()
    url = f"http://127.0.0.1:{porta}"
    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(porta)], cwd=RAIZ
    )
    try:
        if not esperar_api(url).get("ia_configurada"):
            print("A IA não está configurada. Coloque a ANTHROPIC_API_KEY no .env e rode de novo.")
            return 1
        with sync_playwright() as playwright:
            navegador = playwright.chromium.launch()
            pagina = navegador.new_page(
                viewport={"width": 1280, "height": 900}, device_scale_factor=2, color_scheme="light"
            )
            pagina.goto(url)
            pagina.get_by_role("button", name=EXEMPLO).click()
            pagina.wait_for_selector("#resultado[data-estado='pronto']", timeout=60_000)
            if pagina.locator(".ficha[data-origem='ia']").count() == 0:
                print("A IA não respondeu e o plano B assumiu. Essa foto não serve. Rode de novo.")
                return 1
            (RAIZ / "docs").mkdir(exist_ok=True)
            pagina.screenshot(path=str(RAIZ / "docs" / "demo.png"), full_page=True)
            # Prévia de link: formato 1,91 por 1, o que o LinkedIn usa.
            pagina.set_viewport_size({"width": 1200, "height": 627})
            pagina.evaluate("window.scrollTo(0, 0)")
            pagina.screenshot(path=str(RAIZ / "app" / "estatico" / "previa.png"))
            navegador.close()
        print("Pronto: docs/demo.png e app/estatico/previa.png")
        return 0
    finally:
        servidor.terminate()
        servidor.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
