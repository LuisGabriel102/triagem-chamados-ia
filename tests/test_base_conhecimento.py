import re

import pytest

from app.base_conhecimento import (
    PASTA_ARTIGOS,
    PASTA_BASE,
    TITULO_ESCALONAMENTO,
    ErroBase,
    carregar_artigos,
    contar_palavras,
    ler_artigo,
)
from app.esquemas import Categoria

# Marcas reais que não podem aparecer na base (a empresa é inventada).
MARCAS_REAIS = [
    "cielo",
    "stone",
    "pagseguro",
    "pagbank",
    "getnet",
    "mercado pago",
    "sumup",
    "infinitepay",
    "picpay",
    "nubank",
    "safrapay",
    "sipag",
    "visa",
    "mastercard",
    "hipercard",
    "american express",
    "whatsapp",
    "instagram",
    "correios",
]


def test_carrega_os_30_artigos_com_categoria_da_triagem():
    artigos = carregar_artigos()
    assert len(artigos) == 30
    assert len({artigo.id for artigo in artigos}) == 30
    assert {artigo.categoria for artigo in artigos} == set(Categoria)


@pytest.mark.parametrize("artigo", carregar_artigos(), ids=lambda artigo: artigo.id)
def test_cada_artigo_e_curto_e_diz_quando_chamar_uma_pessoa(artigo):
    assert 100 <= contar_palavras(artigo.texto) <= 250
    assert artigo.titulo
    # O bloco vem no fim e tem pelo menos uma situação em lista.
    assert artigo.quando_chamar_pessoa.startswith("- ")


def test_arquivos_em_utf8_sem_bom():
    for caminho in [*PASTA_ARTIGOS.glob("*.md"), PASTA_BASE / "EMPRESA.md"]:
        bruto = caminho.read_bytes()
        assert not bruto.startswith(b"\xef\xbb\xbf"), caminho.name
        bruto.decode("utf-8")


def test_nenhuma_marca_real_na_base():
    textos = [caminho.read_text("utf-8").lower() for caminho in PASTA_BASE.rglob("*.md")]
    for marca in MARCAS_REAIS:
        padrao = re.compile(rf"\b{re.escape(marca)}\b")
        assert not any(padrao.search(texto) for texto in textos), marca


def test_empresa_marca_prazos_e_taxas_como_inventados():
    texto = (PASTA_BASE / "EMPRESA.md").read_text("utf-8")
    assert "Tapiri Pagamentos" in texto
    assert "inventad" in texto


def _escrever(pasta, nome, conteudo):
    caminho = pasta / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


ARTIGO_OK = (
    f"---\ntitulo: Teste\ncategoria: outros\n---\n\nTexto.\n\n{TITULO_ESCALONAMENTO}\n\n- Sempre.\n"
)


def test_le_cabecalho_e_corpo(tmp_path):
    artigo = ler_artigo(_escrever(tmp_path, "teste.md", ARTIGO_OK))
    assert artigo.id == "teste"
    assert artigo.titulo == "Teste"
    assert artigo.categoria is Categoria.OUTROS
    assert artigo.texto.startswith("Texto.")
    assert artigo.quando_chamar_pessoa == "- Sempre."


@pytest.mark.parametrize(
    ("conteudo", "trecho_do_erro"),
    [
        ("Sem cabeçalho.", "cabeçalho"),
        ("---\ntitulo: X\ncategoria: outros\n\nTexto.", "não fecha"),
        (ARTIGO_OK.replace("categoria: outros", "categoria: vendas"), "categoria"),
        (ARTIGO_OK.replace("titulo: Teste", "titulo:"), "título"),
        (ARTIGO_OK.replace(TITULO_ESCALONAMENTO, "## Outro bloco"), "Quando chamar"),
    ],
)
def test_artigo_fora_do_formato_da_erro_claro(tmp_path, conteudo, trecho_do_erro):
    with pytest.raises(ErroBase, match=trecho_do_erro):
        ler_artigo(_escrever(tmp_path, "ruim.md", conteudo))


def test_artigo_com_bom_da_erro(tmp_path):
    caminho = tmp_path / "bom.md"
    caminho.write_bytes(b"\xef\xbb\xbf" + ARTIGO_OK.encode("utf-8"))
    with pytest.raises(ErroBase, match="BOM"):
        ler_artigo(caminho)


def test_pasta_vazia_da_erro(tmp_path):
    with pytest.raises(ErroBase, match="nenhum artigo"):
        carregar_artigos(tmp_path)
