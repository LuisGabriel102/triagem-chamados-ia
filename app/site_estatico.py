"""Site estático da demonstração, para o GitHub Pages (custo zero).

Os exemplos passam pela IA uma vez só (`gravar_exemplos`). O site mostra essas
respostas reais gravadas, sem chamar a IA a cada visita (`montar_site`).
"""

import html
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.esquemas import Canal, Origem, TriagemDemo
from app.servico import ServicoTriagem, para_demo

PASTA_APP = Path(__file__).parent
PASTA_PAGINAS = PASTA_APP / "paginas"
PASTA_ESTATICA = PASTA_APP / "estatico"
ARQUIVO_EXEMPLOS = PASTA_ESTATICA / "exemplos.json"

# No GitHub Pages não dá para mandar cabeçalhos: a política vai numa meta tag.
POLITICA_DE_SEGURANCA = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'"
)


class ErroDeGravacao(Exception):
    """A gravação não serve para o site (por exemplo, a IA não respondeu)."""


def carregar_exemplos(arquivo: Path = ARQUIVO_EXEMPLOS) -> list[dict[str, str]]:
    return json.loads(arquivo.read_text("utf-8"))


def gravar_exemplos(servico: ServicoTriagem, exemplos: list[dict[str, str]]) -> dict[str, Any]:
    """Passa cada exemplo pela IA e guarda a resposta real. Recusa respostas do plano B."""
    gravados = []
    for exemplo in exemplos:
        resultado = servico.triar(exemplo["texto"], Canal(exemplo["canal"]))
        if resultado.origem is not Origem.IA:
            raise ErroDeGravacao(
                f"A IA não respondeu no exemplo '{exemplo['nome']}' e o plano B assumiu. "
                "Confira a chave da Anthropic e rode de novo."
            )
        gravados.append({**exemplo, "resultado": para_demo(resultado).model_dump(mode="json")})
    return {
        "gravado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "modelo": servico.modelo,
        "exemplos": gravados,
    }


def validar_gravacao(gravacao: dict[str, Any]) -> None:
    exemplos = gravacao.get("exemplos") or []
    if not exemplos:
        raise ErroDeGravacao("A gravação não tem exemplos.")
    for exemplo in exemplos:
        resultado = TriagemDemo.model_validate(exemplo["resultado"])
        if resultado.origem is not Origem.IA:
            raise ErroDeGravacao(f"O exemplo '{exemplo['nome']}' não veio da IA.")


def _meta_publica(url_publica: str, tem_previa: bool) -> str:
    linhas = [f'<meta http-equiv="Content-Security-Policy" content="{POLITICA_DE_SEGURANCA}">']
    url = html.escape(url_publica.strip().rstrip("/"), quote=True)
    if url.startswith("https://"):
        linhas.append(f'<meta property="og:url" content="{url}/">')
        if tem_previa:
            linhas.append(f'<meta property="og:image" content="{url}/estatico/previa.png">')
            linhas.append('<meta name="twitter:card" content="summary_large_image">')
    return "\n".join(linhas)


def montar_site(
    destino: Path,
    gravacao: dict[str, Any],
    url_publica: str = "",
    pasta_estatica: Path = PASTA_ESTATICA,
) -> None:
    """Escreve o site em `destino`: index.html, arquivos da página e a gravação."""
    validar_gravacao(gravacao)
    tem_previa = (pasta_estatica / "previa.png").exists()
    pagina = (PASTA_PAGINAS / "demo.html").read_text("utf-8")
    trocas = {
        '<body data-modo="ao-vivo">': '<body data-modo="gravado">',
        'href="/estatico/demo.css"': 'href="estatico/demo.css"',
        'src="/estatico/demo.js"': 'src="estatico/demo.js"',
        '\n    <a href="/docs">Documentação da API</a>': "",
        "<!--META_PUBLICA-->": _meta_publica(url_publica, tem_previa),
        "Demonstração com limite de uso. Use só dados fictícios: nada do que você digita é "
        "gravado.": "Estas são respostas reais da IA, gravadas uma vez. Para testar com a sua "
        "mensagem, rode o projeto no seu computador.",
    }
    for antigo, novo in trocas.items():
        if pagina.count(antigo) != 1:
            raise ErroDeGravacao(f"A página mudou e o trecho não foi achado: {antigo[:40]!r}")
        pagina = pagina.replace(antigo, novo)

    destino.mkdir(parents=True, exist_ok=True)
    (destino / "index.html").write_text(pagina, "utf-8")
    (destino / "exemplos_gravados.json").write_text(
        json.dumps(gravacao, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    pasta = destino / "estatico"
    (pasta / "fontes").mkdir(parents=True, exist_ok=True)
    arquivos = ["demo.css", "demo.js", *(["previa.png"] if tem_previa else [])]
    for nome in arquivos:
        shutil.copy2(pasta_estatica / nome, pasta / nome)
    for fonte in (pasta_estatica / "fontes").iterdir():
        shutil.copy2(fonte, pasta / "fontes" / fonte.name)
