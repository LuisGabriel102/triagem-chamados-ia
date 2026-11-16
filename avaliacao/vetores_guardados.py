"""Os vetores das perguntas da busca, guardados num arquivo, para medir a busca sem o Google.

Por que existe: a busca por sentido é a que o atendimento usa, e ela precisa do Google para
transformar a pergunta em vetor. O CI não tem chave (e não deve gastar). Os vetores dos 30
artigos já ficam em base/indice.json; aqui ficam os das 48 perguntas da avaliação da busca.
Com os dois arquivos, o teste tests/test_busca_regressao.py mede a busca por sentido a cada
envio, de graça, e falha se ela piorar.

Gravar de novo (gasta frações de centavo, precisa da GEMINI_API_KEY):
    python -m avaliacao.vetores_guardados

O arquivo guarda o texto já mascarado (é ele que vai ao Google), o modelo e as dimensões. Se o
mascaramento, o modelo ou as perguntas mudarem, o teste avisa que falta vetor.
"""

import json
import sys
from pathlib import Path
from typing import Any

from app.busca_sentido import criar_gerador
from app.config import Configuracao
from app.mascaramento import mascarar

PASTA = Path(__file__).parent
ARQUIVO_VETORES = PASTA / "vetores_perguntas_busca.json"
ARQUIVO_PERGUNTAS = PASTA / "perguntas_busca.jsonl"
CASAS = 6  # o suficiente para a ordem dos artigos não mudar, e o arquivo fica menor


class FaltaVetor(KeyError):
    """A pergunta não está no arquivo: grave os vetores de novo."""


class GeradorDeArquivo:
    """Faz o papel do gerador do Google, devolvendo os vetores guardados. Não chama nada."""

    def __init__(self, caminho: Path = ARQUIVO_VETORES) -> None:
        dados = json.loads(caminho.read_text("utf-8"))
        self.modelo: str = dados["modelo"]
        self.dimensoes: int = dados["dimensoes"]
        self._vetores: dict[str, list[float]] = dados["vetores"]

    def vetor_documento(self, titulo: str, texto: str) -> list[float]:
        raise FaltaVetor("os vetores dos artigos vêm de base/indice.json, não daqui")

    def vetor_pergunta(self, texto: str) -> list[float]:
        try:
            return self._vetores[texto]
        except KeyError:
            raise FaltaVetor(f"sem vetor guardado para: {texto[:60]}") from None


def gravar(config: Configuracao, caminho: Path = ARQUIVO_VETORES) -> dict[str, Any]:
    gerador = criar_gerador(config)
    if gerador is None:
        raise SystemExit("Não rodou: falta a GEMINI_API_KEY no .env.")
    perguntas = [
        json.loads(linha)
        for linha in ARQUIVO_PERGUNTAS.read_text("utf-8").splitlines()
        if linha.strip()
    ]
    vetores = {}
    for pergunta in perguntas:
        texto = mascarar(pergunta["pergunta"]).texto
        vetores[texto] = [round(x, CASAS) for x in gerador.vetor_pergunta(texto)]
    dados = {
        "modelo": gerador.modelo,
        "dimensoes": gerador.dimensoes,
        "aviso": "Vetores das perguntas de avaliacao/perguntas_busca.jsonl, já mascaradas.",
        "vetores": vetores,
    }
    caminho.write_text(json.dumps(dados, ensure_ascii=False) + "\n", "utf-8")
    return dados


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    dados = gravar(Configuracao())
    print(f"{len(dados['vetores'])} vetores ({dados['modelo']}, {dados['dimensoes']}) gravados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
