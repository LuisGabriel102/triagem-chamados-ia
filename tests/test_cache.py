"""O navegador pega sempre a versão nova da página depois de uma publicação.

O problema visto em 16/11/2026: quem tinha aberto o site antes recebia o demo.css e o demo.js
antigos (sem estilo e sem a aba Atendimento) até forçar a recarga. As duas proteções:
1. o CSS e o JS vão com a versão do conteúdo no endereço (?v=): arquivo novo, endereço novo;
2. a página e os estáticos vão com "Cache-Control: no-cache": o navegador confere antes de usar.
"""

import hashlib
import re

import pytest

from app.main import PASTA_ESTATICA, com_versoes, versao_do_arquivo


def _versao(nome: str) -> str:
    return hashlib.sha256((PASTA_ESTATICA / nome).read_bytes()).hexdigest()[:10]


@pytest.mark.parametrize(
    ("rota", "arquivos"),
    [("/", ["demo.css", "demo.js"]), ("/fila", ["demo.css", "fila.js"])],
)
def test_pagina_aponta_para_a_versao_atual_e_nao_fica_em_cache(abrir_api, rota, arquivos):
    resposta = abrir_api().get(rota)
    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == "no-cache"
    for nome in arquivos:
        assert f'"/estatico/{nome}?v={_versao(nome)}"' in resposta.text
        # Nenhum endereço sem versão sobrou na página.
        assert f'"/estatico/{nome}"' not in resposta.text


@pytest.mark.parametrize("nome", ["demo.css", "demo.js", "fila.js", "perguntas_atendimento.json"])
def test_estaticos_sempre_conferidos_com_o_servidor(abrir_api, nome):
    cliente = abrir_api()
    primeira = cliente.get(f"/estatico/{nome}")
    assert primeira.status_code == 200
    assert primeira.headers["cache-control"] == "no-cache"
    # Conferindo de novo, sem mudança: o servidor responde 304, sem reenviar o arquivo.
    etag = primeira.headers["etag"]
    segunda = cliente.get(f"/estatico/{nome}", headers={"If-None-Match": etag})
    assert segunda.status_code == 304
    assert segunda.headers["cache-control"] == "no-cache"


def test_arquivo_novo_ganha_endereco_novo(tmp_path):
    """A prova da proteção 1: o endereço que o navegador tinha guardado deixa de existir."""
    for nome in ("demo.css", "demo.js", "fila.js"):
        (tmp_path / nome).write_text("versão antiga", "utf-8")
    pagina = '<link href="/estatico/demo.css"><script src="/estatico/demo.js"></script>'
    antes = com_versoes(pagina, tmp_path)

    versao_do_arquivo.cache_clear()
    for nome in ("demo.css", "demo.js", "fila.js"):
        (tmp_path / f"novo-{nome}").write_text("versão nova", "utf-8")
        (tmp_path / f"novo-{nome}").replace(tmp_path / nome)
    versao_do_arquivo.cache_clear()
    depois = com_versoes(pagina, tmp_path)

    enderecos_antes = re.findall(r'"(/estatico/[^"]+)"', antes)
    enderecos_depois = re.findall(r'"(/estatico/[^"]+)"', depois)
    assert len(enderecos_antes) == len(enderecos_depois) == 2
    assert set(enderecos_antes).isdisjoint(enderecos_depois)


def test_titulo_da_aba_e_o_mesmo_do_h1_e_a_previa_do_link_nao_mudou(abrir_api):
    pagina = abrir_api().get("/").text
    assert "<title>Triagem e atendimento com IA</title>" in pagina
    assert "<h1>Triagem e atendimento com IA</h1>" in pagina
    # A prévia do link (o que aparece ao compartilhar) continua a de antes.
    assert '<meta property="og:title" content="Triagem de chamados com IA">' in pagina
