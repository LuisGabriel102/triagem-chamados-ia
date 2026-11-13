import json
from dataclasses import replace

import httpx2
import pytest
from google.auth.exceptions import DefaultCredentialsError
from google.genai import errors as erros_google

from app import busca_sentido as modulo
from app.base_conhecimento import Artigo, carregar_artigos
from app.busca_sentido import (
    ErroSentido,
    GeradorGemini,
    IndiceMemoria,
    acesso_ao_google,
    atualizar_indice,
    carregar_indice_memoria,
    criar_gerador,
    normalizar_vetor,
)
from app.config import Configuracao
from app.esquemas import Categoria
from tests.falsos import ClienteEmbeddingFalso, GeradorVetoresFalso


def _artigo(id_artigo: str, texto: str = "Texto do artigo.") -> Artigo:
    return Artigo(id=id_artigo, titulo=id_artigo.title(), categoria=Categoria.OUTROS, texto=texto)


# --- O gerador do Gemini (com cliente falso: nada sai do computador) ---


def test_gemini_embedding_2_manda_a_tarefa_no_texto_e_768_dimensoes():
    cliente = ClienteEmbeddingFalso()
    gerador = GeradorGemini(cliente)
    gerador.vetor_pergunta("quando cai o dinheiro?")
    gerador.vetor_documento("Prazos", "O débito cai em 1 dia útil.")

    pergunta, documento = cliente.chamadas
    assert pergunta["model"] == "gemini-embedding-2"
    assert pergunta["contents"] == "task: search result | query: quando cai o dinheiro?"
    assert documento["contents"] == "title: Prazos | text: O débito cai em 1 dia útil."
    for chamada in cliente.chamadas:
        assert chamada["config"].output_dimensionality == 768
        # Esse modelo não aceita task_type.
        assert chamada["config"].task_type is None


def test_gemini_embedding_001_manda_a_tarefa_no_task_type():
    cliente = ClienteEmbeddingFalso()
    gerador = GeradorGemini(cliente, modelo="gemini-embedding-001")
    gerador.vetor_pergunta("quando cai?")
    gerador.vetor_documento("Prazos", "O débito cai em 1 dia útil.")

    pergunta, documento = cliente.chamadas
    assert pergunta["contents"] == "quando cai?"
    assert pergunta["config"].task_type == "RETRIEVAL_QUERY"
    assert documento["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert documento["config"].title == "Prazos"


def test_vetor_volta_normalizado():
    vetor = GeradorGemini(ClienteEmbeddingFalso()).vetor_pergunta("oi")
    assert vetor[:2] == pytest.approx([0.6, 0.8])
    assert sum(x * x for x in vetor) == pytest.approx(1.0)


def test_dimensao_errada_vira_erro():
    gerador = GeradorGemini(ClienteEmbeddingFalso(dimensoes=3072))
    with pytest.raises(ErroSentido, match="3072"):
        gerador.vetor_pergunta("oi")


@pytest.mark.parametrize(
    ("erro", "trecho"),
    [
        (erros_google.ServerError(503, {"error": {"message": "fora"}}), "ServerError 503"),
        (erros_google.ClientError(429, {"error": {"message": "cota"}}), "ClientError 429"),
        (httpx2.ConnectError("sem rede"), "ConnectError"),
        (DefaultCredentialsError("sem login"), "gcloud auth"),
    ],
)
def test_falha_do_google_vira_erro_sem_o_texto_do_google(erro, trecho):
    gerador = GeradorGemini(ClienteEmbeddingFalso(erro=erro))
    with pytest.raises(ErroSentido, match=trecho) as capturado:
        gerador.vetor_pergunta("oi")
    assert "fora" not in str(capturado.value) and "cota" not in str(capturado.value)


# --- Como o gerador é montado a partir da configuração ---


def _config(**valores):
    return Configuracao(_env_file=None, anthropic_api_key=None, **valores)


def test_sem_chave_nem_projeto_nao_ha_gerador():
    config = _config(gemini_api_key=None, google_cloud_project="")
    assert acesso_ao_google(config) is None
    assert criar_gerador(config) is None


def test_chave_do_ai_studio_vem_antes_do_vertex(monkeypatch):
    criados = []
    monkeypatch.setattr(modulo.genai, "Client", lambda **kwargs: criados.append(kwargs))
    config = _config(gemini_api_key="chave-de-teste", google_cloud_project="projeto-teste")
    gerador = criar_gerador(config)
    assert acesso_ao_google(config) == "chave do Google AI Studio"
    assert criados[0]["api_key"] == "chave-de-teste"
    assert criados[0]["enterprise"] is False
    assert gerador.modelo == "gemini-embedding-2"
    assert gerador.dimensoes == 768


def test_sem_chave_usa_o_vertex(monkeypatch):
    criados = []
    monkeypatch.setattr(modulo.genai, "Client", lambda **kwargs: criados.append(kwargs))
    config = _config(gemini_api_key=None, google_cloud_project="projeto-teste")
    criar_gerador(config)
    assert acesso_ao_google(config) == "Vertex AI"
    assert criados[0]["enterprise"] is True
    assert criados[0]["project"] == "projeto-teste"
    assert "api_key" not in criados[0]


# --- A busca na memória (cosseno) ---


def test_indice_na_memoria_ordena_pelo_cosseno():
    indice = IndiceMemoria({"a": [1.0, 0.0], "b": [0.6, 0.8], "c": [0.0, 1.0]})
    resultado = indice.buscar([1.0, 0.1])
    assert [id_ for id_, _ in resultado] == ["a", "b", "c"]
    assert resultado[0][1] == pytest.approx(1 / (1.01**0.5))
    assert len(indice.buscar([1.0, 0.0], quantos=2)) == 2


def test_vetor_zerado_nao_quebra():
    assert normalizar_vetor([0.0, 0.0]) == [0.0, 0.0]
    assert IndiceMemoria({"a": [1.0, 0.0]}).buscar([0.0, 0.0]) == [("a", 0.0)]


# --- O cache dos vetores dos artigos (base/indice.json) ---


def test_cache_so_refaz_o_que_mudou(tmp_path):
    caminho = tmp_path / "indice.json"
    artigos = [_artigo("prazos"), _artigo("bobina"), _artigo("pix")]
    gerador = GeradorVetoresFalso()

    primeira = atualizar_indice(artigos, gerador, caminho)
    assert sorted(primeira.refeitos) == ["bobina", "pix", "prazos"]
    assert len(gerador.documentos) == 3

    segunda = atualizar_indice(artigos, gerador, caminho)
    assert segunda.refeitos == []
    assert len(segunda.aproveitados) == 3
    assert len(gerador.documentos) == 3  # nenhuma chamada nova

    artigos[1] = replace(artigos[1], texto="Texto novo da bobina.")
    terceira = atualizar_indice(artigos, gerador, caminho)
    assert terceira.refeitos == ["bobina"]
    assert len(gerador.documentos) == 4


def test_cache_refaz_tudo_se_o_modelo_ou_as_dimensoes_mudarem(tmp_path):
    caminho = tmp_path / "indice.json"
    artigos = [_artigo("prazos"), _artigo("bobina")]
    atualizar_indice(artigos, GeradorVetoresFalso(), caminho)
    assert (
        len(atualizar_indice(artigos, GeradorVetoresFalso(modelo="outro"), caminho).refeitos) == 2
    )
    assert len(atualizar_indice(artigos, GeradorVetoresFalso(dimensoes=32), caminho).refeitos) == 2


def test_cache_tira_artigo_apagado(tmp_path):
    caminho = tmp_path / "indice.json"
    atualizar_indice([_artigo("prazos"), _artigo("velho")], GeradorVetoresFalso(), caminho)
    relatorio = atualizar_indice([_artigo("prazos")], GeradorVetoresFalso(), caminho)
    assert relatorio.removidos == ["velho"]
    dados = json.loads(caminho.read_text("utf-8"))
    assert list(dados["artigos"]) == ["prazos"]
    assert dados["modelo"] == "modelo-falso"
    assert dados["dimensoes"] == 64


def test_cache_guarda_o_que_ja_foi_feito_quando_o_google_cai(tmp_path):
    caminho = tmp_path / "indice.json"
    artigos = [_artigo("a"), _artigo("b"), _artigo("c")]

    class CaiNoTerceiro(GeradorVetoresFalso):
        def vetor_documento(self, titulo, texto):
            if len(self.documentos) == 2:
                raise ErroSentido("falha na API do Google (ServerError 503)")
            return super().vetor_documento(titulo, texto)

    with pytest.raises(ErroSentido):
        atualizar_indice(artigos, CaiNoTerceiro(), caminho)
    gerador = GeradorVetoresFalso()
    relatorio = atualizar_indice(artigos, gerador, caminho)
    assert relatorio.refeitos == ["c"]
    assert gerador.documentos == ["C"]


def test_indice_ausente_ou_velho_da_erro_claro(tmp_path):
    caminho = tmp_path / "indice.json"
    artigos = [_artigo("prazos")]
    with pytest.raises(ErroSentido, match="não existe"):
        carregar_indice_memoria(artigos, "modelo-falso", 64, caminho)

    atualizar_indice(artigos, GeradorVetoresFalso(), caminho)
    indice = carregar_indice_memoria(artigos, "modelo-falso", 64, caminho)
    assert indice.buscar([1.0] * 64)[0][0] == "prazos"

    mudado = [replace(artigos[0], texto="Outro texto.")]
    with pytest.raises(ErroSentido, match="desatualizado em 1"):
        carregar_indice_memoria(mudado, "modelo-falso", 64, caminho)
    with pytest.raises(ErroSentido, match="desatualizado"):
        carregar_indice_memoria(artigos, "gemini-embedding-2", 768, caminho)


def test_indice_da_base_inteira_com_gerador_falso(tmp_path):
    artigos = carregar_artigos()
    caminho = tmp_path / "indice.json"
    relatorio = atualizar_indice(artigos, GeradorVetoresFalso(), caminho)
    assert len(relatorio.refeitos) == 30
    assert caminho.read_bytes()[:1] == b"{"  # UTF-8 sem BOM
