"""A base de conhecimento do atendimento: artigos curtos em Markdown, um por arquivo.

Cada arquivo em base/artigos/ começa com um cabeçalho entre linhas "---" e termina com
o bloco "## Quando chamar uma pessoa":

    ---
    titulo: Quando o dinheiro das vendas cai na conta
    categoria: financeiro
    ---

    Texto do artigo...

    ## Quando chamar uma pessoa

    - Situação em que o agente passa o caso para uma pessoa.

A categoria é uma das filas da triagem. O nome do arquivo, sem o ".md", é o id do artigo.
A empresa é inventada (base/EMPRESA.md): prazos, taxas e nomes não valem para nenhuma
empresa real.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from app.esquemas import Categoria

PASTA_BASE = Path(__file__).resolve().parent.parent / "base"
PASTA_ARTIGOS = PASTA_BASE / "artigos"
TITULO_ESCALONAMENTO = "## Quando chamar uma pessoa"
_PALAVRA = re.compile(r"\w+(?:[-']\w+)*")


class ErroBase(ValueError):
    """Artigo fora do formato."""


@dataclass(frozen=True)
class Artigo:
    id: str
    titulo: str
    categoria: Categoria
    texto: str  # o corpo, sem o cabeçalho

    @property
    def quando_chamar_pessoa(self) -> str:
        """O bloco final do artigo: quando o agente deve passar o caso para uma pessoa."""
        return self.texto.split(TITULO_ESCALONAMENTO, 1)[1].strip()


def descricao_do_negocio(caminho: Path = PASTA_BASE / "EMPRESA.md") -> str:
    """O que a Tapiri vende, tirado de base/EMPRESA.md, para a triagem do atendimento.

    É o parágrafo que começa com "A Tapiri vende", sem o negrito e sem a frase final que
    lembra que os números são inventados (isso a triagem não precisa saber).
    """
    paragrafos = caminho.read_text("utf-8").replace("\r\n", "\n").split("\n\n")
    texto = next(p for p in paragrafos if p.startswith("A Tapiri vende"))
    texto = texto.split("**Todos esses números", 1)[0]
    return " ".join(texto.replace("**", "").split())


def contar_palavras(texto: str) -> int:
    return len(_PALAVRA.findall(texto))


def ler_artigo(caminho: Path) -> Artigo:
    bruto = caminho.read_bytes()
    if bruto.startswith(b"\xef\xbb\xbf"):
        raise ErroBase(f"{caminho.name}: o arquivo tem BOM; salve em UTF-8 sem BOM")
    linhas = bruto.decode("utf-8").replace("\r\n", "\n").split("\n")
    if not linhas or linhas[0].strip() != "---":
        raise ErroBase(f"{caminho.name}: falta o cabeçalho entre linhas '---'")
    try:
        fim = linhas.index("---", 1)
    except ValueError as erro:
        raise ErroBase(f"{caminho.name}: o cabeçalho não fecha com '---'") from erro

    cabecalho: dict[str, str] = {}
    for linha in linhas[1:fim]:
        if not linha.strip():
            continue
        chave, separador, valor = linha.partition(":")
        if not separador:
            raise ErroBase(f"{caminho.name}: linha do cabeçalho sem ':' ({linha!r})")
        cabecalho[chave.strip()] = valor.strip()

    titulo = cabecalho.get("titulo", "")
    if not titulo:
        raise ErroBase(f"{caminho.name}: falta o título")
    try:
        categoria = Categoria(cabecalho.get("categoria", ""))
    except ValueError as erro:
        raise ErroBase(f"{caminho.name}: categoria fora das filas da triagem") from erro
    texto = "\n".join(linhas[fim + 1 :]).strip()
    if TITULO_ESCALONAMENTO not in texto:
        raise ErroBase(f"{caminho.name}: falta o bloco '{TITULO_ESCALONAMENTO}'")
    return Artigo(id=caminho.stem, titulo=titulo, categoria=categoria, texto=texto)


def carregar_artigos(pasta: Path = PASTA_ARTIGOS) -> list[Artigo]:
    """Lê todos os artigos da pasta, em ordem alfabética do id."""
    artigos = [ler_artigo(caminho) for caminho in sorted(pasta.glob("*.md"))]
    if not artigos:
        raise ErroBase(f"nenhum artigo em {pasta}")
    return artigos
