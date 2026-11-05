"""Site estático do GitHub Pages: gravação das respostas e montagem das páginas."""

import json
import shutil

import anthropic
import pytest

from app.classificador import ClassificadorClaude
from app.esquemas import TAMANHO_MAXIMO_DEMO, Canal
from app.servico import ServicoTriagem
from app.site_estatico import (
    PASTA_ESTATICA,
    ErroDeGravacao,
    carregar_exemplos,
    gravar_exemplos,
    montar_site,
)
from tests.falsos import REQUISICAO_FALSA, ClienteFalso

URL_PAGES = "https://luisgabriel102.github.io/triagem-chamados-ia"


def gravacao_falsa() -> dict:
    servico = ServicoTriagem(ClassificadorClaude(ClienteFalso(), "claude-haiku-5-5"))
    return gravar_exemplos(servico, carregar_exemplos())


def test_exemplos_da_pagina_sao_validos():
    exemplos = carregar_exemplos()
    assert len(exemplos) == 6
    assert len({e["nome"] for e in exemplos}) == 6
    for exemplo in exemplos:
        Canal(exemplo["canal"])
        assert 0 < len(exemplo["texto"]) <= TAMANHO_MAXIMO_DEMO


def test_gravacao_guarda_a_resposta_da_ia_de_cada_exemplo():
    gravacao = gravacao_falsa()
    assert gravacao["modelo"] == "claude-haiku-5-5"
    assert gravacao["gravado_em"].endswith("+00:00")
    assert len(gravacao["exemplos"]) == 6
    primeiro = gravacao["exemplos"][0]["resultado"]
    assert primeiro["origem"] == "ia"
    assert "[CPF]" in primeiro["texto_mascarado"]
    # O texto do exemplo (fictício) aparece na caixa da página, de propósito: é o "antes".
    # O que a IA leu e respondeu nunca tem o dado.
    resultados = json.dumps([e["resultado"] for e in gravacao["exemplos"]], ensure_ascii=False)
    assert "529.982.247-25" not in resultados
    assert "joana.silva@example.com" not in resultados


def test_gravacao_recusa_resposta_do_plano_b():
    cliente = ClienteFalso(erro=anthropic.APIConnectionError(request=REQUISICAO_FALSA))
    servico = ServicoTriagem(ClassificadorClaude(cliente, "claude-haiku-5-5"))
    with pytest.raises(ErroDeGravacao, match="plano B"):
        gravar_exemplos(servico, carregar_exemplos())


def test_site_montado_funciona_sem_servidor(tmp_path):
    montar_site(tmp_path, gravacao_falsa(), url_publica=URL_PAGES)
    pagina = (tmp_path / "index.html").read_text("utf-8")
    assert '<body data-modo="gravado">' in pagina
    # Caminhos relativos: o site fica numa subpasta do github.io.
    assert 'href="estatico/demo.css"' in pagina
    assert 'src="estatico/demo.js"' in pagina
    assert '"/estatico/' not in pagina
    # Não existe documentação da API num site estático.
    assert 'href="/docs"' not in pagina
    assert 'http-equiv="Content-Security-Policy"' in pagina
    assert f'<meta property="og:url" content="{URL_PAGES}/">' in pagina
    for arquivo in (
        "estatico/demo.css",
        "estatico/demo.js",
        "estatico/fontes/atkinson-hyperlegible-latin-400-normal.woff2",
        "estatico/fontes/OFL.txt",
    ):
        assert (tmp_path / arquivo).exists(), arquivo
    gravado = json.loads((tmp_path / "exemplos_gravados.json").read_text("utf-8"))
    assert len(gravado["exemplos"]) == 6


def test_site_usa_a_previa_quando_ela_existe(tmp_path):
    pasta = tmp_path / "estatico"
    shutil.copytree(PASTA_ESTATICA, pasta)
    (pasta / "previa.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    montar_site(tmp_path / "site", gravacao_falsa(), url_publica=URL_PAGES, pasta_estatica=pasta)
    pagina = (tmp_path / "site" / "index.html").read_text("utf-8")
    assert f'content="{URL_PAGES}/estatico/previa.png"' in pagina
    assert (tmp_path / "site" / "estatico" / "previa.png").exists()


def test_site_recusa_gravacao_que_nao_veio_da_ia(tmp_path):
    gravacao = gravacao_falsa()
    gravacao["exemplos"][0]["resultado"]["origem"] = "regras"
    with pytest.raises(ErroDeGravacao, match="não veio da IA"):
        montar_site(tmp_path, gravacao)


def test_estilo_usa_caminhos_relativos_para_a_fonte():
    estilo = (PASTA_ESTATICA / "demo.css").read_text("utf-8")
    assert 'url("fontes/atkinson-hyperlegible-latin-400-normal.woff2")' in estilo
    assert "/estatico/fontes" not in estilo
