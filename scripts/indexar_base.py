"""Gera ou atualiza base/indice.json: os vetores dos artigos para a busca por sentido.

Só refaz o artigo que mudou. Muda tudo se o modelo ou as dimensões mudarem. Cada artigo
refeito é uma chamada ao Google: na primeira vez, são 30 chamadas.

Precisa da GEMINI_API_KEY (Google AI Studio) ou do GOOGLE_CLOUD_PROJECT (Vertex AI) no .env.

    python scripts/indexar_base.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.base_conhecimento import carregar_artigos  # noqa: E402
from app.busca_sentido import (  # noqa: E402
    ARQUIVO_INDICE,
    ErroSentido,
    acesso_ao_google,
    atualizar_indice,
    criar_gerador,
)
from app.config import Configuracao  # noqa: E402


def main() -> int:
    config = Configuracao()
    gerador = criar_gerador(config)
    if gerador is None:
        print(
            "Não há como chamar o Google. Coloque no .env a GEMINI_API_KEY (Google AI Studio)\n"
            "ou o GOOGLE_CLOUD_PROJECT (Vertex AI) e rode de novo. Veja docs/ATENDIMENTO.md."
        )
        return 1
    artigos = carregar_artigos()
    print(
        f"Indexando {len(artigos)} artigos com {gerador.modelo} ({gerador.dimensoes} dimensões), "
        f"pela {acesso_ao_google(config)}..."
    )
    try:
        relatorio = atualizar_indice(artigos, gerador, ARQUIVO_INDICE)
    except ErroSentido as erro:
        print(f"Parou no meio: {erro}. O que já foi feito ficou gravado; rode de novo.")
        return 1
    print(f"Refeitos: {len(relatorio.refeitos)}. Aproveitados: {len(relatorio.aproveitados)}.")
    if relatorio.removidos:
        print(f"Tirados do índice (artigo apagado): {', '.join(relatorio.removidos)}.")
    print(f"Índice gravado em {ARQUIVO_INDICE.relative_to(RAIZ)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
