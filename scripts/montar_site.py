"""Monta o site estático da demonstração a partir da gravação. Não chama a IA.

    python scripts/montar_site.py _site --url https://luisgabriel102.github.io/triagem-chamados-ia

Usado pelo GitHub Actions para publicar no GitHub Pages.
"""

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.site_estatico import ErroDeGravacao, montar_site  # noqa: E402

GRAVACAO = RAIZ / "docs" / "exemplos_gravados.json"


def main(argumentos: list[str] | None = None) -> int:
    leitor = argparse.ArgumentParser(description="Monta o site estático da demonstração.")
    leitor.add_argument("destino", type=Path)
    leitor.add_argument("--url", default="", help="Endereço público do site, para a prévia")
    args = leitor.parse_args(argumentos)
    if not GRAVACAO.exists():
        print("Falta docs/exemplos_gravados.json. Rode antes: python scripts/gravar_exemplos.py")
        return 1
    try:
        montar_site(args.destino, json.loads(GRAVACAO.read_text("utf-8")), url_publica=args.url)
    except ErroDeGravacao as erro:
        print(erro)
        return 1
    print(f"Site montado em {args.destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
