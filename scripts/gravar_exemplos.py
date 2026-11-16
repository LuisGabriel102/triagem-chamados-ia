"""Passa os exemplos da página pela IA uma vez e grava as respostas reais.

Usa a IA do .env (PROVEDOR_IA). Com o Claude, são 6 chamadas (cerca de US$ 0,0015 no total).

    python scripts/gravar_exemplos.py

Gera docs/exemplos_gravados.json, que o site do GitHub Pages mostra sem custo.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.config import Configuracao  # noqa: E402
from app.servico import criar_servico  # noqa: E402
from app.site_estatico import ErroDeGravacao, carregar_exemplos, gravar_exemplos  # noqa: E402

DESTINO = RAIZ / "docs" / "exemplos_gravados.json"


def main() -> int:
    config = Configuracao()
    servico = criar_servico(config)
    if not servico.ia_configurada:
        falta = "GOOGLE_CLOUD_PROJECT" if config.provedor_ia == "gemini" else "ANTHROPIC_API_KEY"
        print(f"A IA não está configurada. Coloque o {falta} no .env e rode de novo.")
        return 1
    try:
        gravacao = gravar_exemplos(servico, carregar_exemplos())
    except ErroDeGravacao as erro:
        print(erro)
        return 1
    DESTINO.parent.mkdir(exist_ok=True)
    DESTINO.write_text(json.dumps(gravacao, ensure_ascii=False, indent=2) + "\n", "utf-8")
    total = 0.0
    for exemplo in gravacao["exemplos"]:
        r = exemplo["resultado"]
        total += r["custo_usd"]
        print(f"{exemplo['nome']}: {r['prioridade']}, fila {r['fila']}, US$ {r['custo_usd']:.6f}")
    print(f"Gravado em {DESTINO.relative_to(RAIZ)}. Custo total: US$ {total:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
