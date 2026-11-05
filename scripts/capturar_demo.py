"""Tira a foto da página de demonstração, a partir das respostas reais gravadas.

Não chama a IA: usa docs/exemplos_gravados.json (rode antes scripts/gravar_exemplos.py).

    pip install -e ".[captura]"
    python -m playwright install chromium
    python scripts/capturar_demo.py

Gera:
    docs/demo.png             foto da página, para o README
    app/estatico/previa.png   imagem que aparece quando o link é colado no LinkedIn
"""

import functools
import json
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from playwright.sync_api import sync_playwright  # noqa: E402

from app.site_estatico import montar_site  # noqa: E402

GRAVACAO = RAIZ / "docs" / "exemplos_gravados.json"


class SemRegistro(SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # silencia o log de cada arquivo
        pass


def main() -> int:
    if not GRAVACAO.exists():
        print("Falta docs/exemplos_gravados.json. Rode antes: python scripts/gravar_exemplos.py")
        return 1
    with tempfile.TemporaryDirectory() as pasta:
        montar_site(Path(pasta), json.loads(GRAVACAO.read_text("utf-8")))
        manipulador = functools.partial(SemRegistro, directory=pasta)
        servidor = ThreadingHTTPServer(("127.0.0.1", 0), manipulador)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{servidor.server_address[1]}/"
        try:
            with sync_playwright() as playwright:
                navegador = playwright.chromium.launch()
                pagina = navegador.new_page(
                    viewport={"width": 1280, "height": 900},
                    device_scale_factor=2,
                    color_scheme="light",
                )
                pagina.goto(url)
                # A página abre já mostrando o primeiro exemplo gravado.
                pagina.wait_for_selector("#resultado[data-estado='pronto']")
                pagina.wait_for_timeout(500)
                (RAIZ / "docs").mkdir(exist_ok=True)
                pagina.screenshot(path=str(RAIZ / "docs" / "demo.png"), full_page=True)
                # Prévia de link: formato 1,91 por 1, o que o LinkedIn usa.
                pagina.set_viewport_size({"width": 1200, "height": 627})
                pagina.evaluate("window.scrollTo(0, 0)")
                pagina.screenshot(path=str(RAIZ / "app" / "estatico" / "previa.png"))
                navegador.close()
        finally:
            servidor.shutdown()
    print("Pronto: docs/demo.png e app/estatico/previa.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
