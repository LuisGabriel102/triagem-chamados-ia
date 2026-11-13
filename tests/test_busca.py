import json

import pytest
from google.genai import errors as erros_google

from app.base_conhecimento import carregar_artigos
from app.busca import (
    ARQUIVO_LIMIARES,
    SEM_ACESSO,
    SEM_LIMIAR_SIMILARIDADE,
    Busca,
    criar_busca,
    escolher_limiar,
    escolher_limiares,
    fundir_rankings,
)
from app.busca_sentido import (
    GeradorGemini,
    IndiceMemoria,
    atualizar_indice,
    carregar_indice_memoria,
)
from app.config import Configuracao
from tests.falsos import ClienteEmbeddingFalso, GeradorVetoresFalso

ARTIGOS = carregar_artigos()
DADOS_PESSOAIS = (
    "Meu CPF é 529.982.247-25, o cartão 4111 1111 1111 1111, "
    "o e-mail loja.bia@example.com e o telefone (82) 99999-1234. "
    "O dinheiro da venda não caiu."
)


@pytest.fixture
def com_sentido(tmp_path):
    """A busca completa, com um gerador de vetores falso no lugar do Google."""
    gerador = GeradorVetoresFalso()
    caminho = tmp_path / "indice.json"
    atualizar_indice(ARTIGOS, gerador, caminho)
    indice = carregar_indice_memoria(ARTIGOS, gerador.modelo, gerador.dimensoes, caminho)
    gerador.documentos.clear()
    busca = Busca(ARTIGOS, gerador, indice, limiar_bm25=1.0, limiar_similaridade=0.2)
    return busca, gerador


# --- Fusão dos rankings (RRF) ---


def test_fusao_soma_as_posicoes_dos_dois_rankings():
    fusao = fundir_rankings(["a", "b", "c"], ["b", "c", "a"])
    assert [id_ for id_, _ in fusao] == ["b", "a", "c"]
    assert dict(fusao)["b"] == pytest.approx(1 / 62 + 1 / 61)


def test_fusao_favorece_quem_aparece_nas_duas_listas():
    fusao = fundir_rankings(["so_palavras", "nas_duas"], ["so_sentido", "nas_duas"])
    assert fusao[0][0] == "nas_duas"


def test_fusao_de_um_ranking_so_mantem_a_ordem():
    assert [id_ for id_, _ in fundir_rankings(["c", "a", "b"])] == ["c", "a", "b"]


# --- Busca híbrida ---


def test_busca_hibrida_devolve_os_3_melhores(com_sentido):
    busca, gerador = com_sentido
    resultado = busca.buscar("a bobina da impressora acabou, onde compro papel?")
    assert resultado.modo == "hibrida"
    assert resultado.criterio == "similaridade"
    assert len(resultado.achados) == 3
    assert resultado.achados[0].artigo.id == "bobina"
    assert resultado.achados[0].similaridade is not None
    assert resultado.achados[0].nota_bm25 is not None
    assert resultado.avisos == []
    assert len(gerador.perguntas) == 1


def test_modo_palavras_nao_chama_o_google(com_sentido):
    busca, gerador = com_sentido
    resultado = busca.buscar("estorno na fatura do cliente", modo="palavras")
    assert resultado.modo == "palavras"
    assert resultado.criterio == "nota_bm25"
    assert resultado.achados[0].artigo.id == "estorno"
    assert resultado.achados[0].similaridade is None
    assert gerador.perguntas == []


def test_modo_sentido_usa_so_a_similaridade(com_sentido):
    busca, _ = com_sentido
    resultado = busca.buscar("estorno na fatura do cliente", modo="sentido")
    assert resultado.modo == "sentido"
    notas = [achado.similaridade for achado in resultado.candidatos]
    assert notas == sorted(notas, reverse=True)


# --- Limiar: "nada encontrado" ---


def test_limiar_da_similaridade_devolve_nada_encontrado(com_sentido):
    busca, _ = com_sentido
    resultado = busca.buscar("qual a previsão do tempo amanhã?")
    assert resultado.nada_encontrado
    assert resultado.achados == []
    assert resultado.melhor_nota < resultado.limiar == 0.2
    # Os candidatos continuam lá, para conferência.
    assert resultado.candidatos or resultado.melhor_nota == 0.0


def test_limiar_do_bm25_sem_a_busca_por_sentido():
    busca = Busca(ARTIGOS, limiar_bm25=5.0)
    perto = busca.buscar("a bobina acabou")
    assert not perto.nada_encontrado
    assert perto.criterio == "nota_bm25"
    longe = Busca(ARTIGOS, limiar_bm25=1000.0).buscar("a bobina acabou")
    assert longe.nada_encontrado
    assert longe.achados == []
    assert longe.candidatos[0].artigo.id == "bobina"


def test_pergunta_sem_nenhuma_palavra_da_base_e_nada_encontrado():
    resultado = Busca(ARTIGOS).buscar("xyzw qwerty")
    assert resultado.nada_encontrado
    assert resultado.candidatos == []
    assert resultado.melhor_nota == 0.0


def test_sem_limiar_da_similaridade_decide_pela_nota_do_bm25(com_sentido):
    busca, gerador = com_sentido
    busca.limiar_similaridade = None
    resultado = busca.buscar("a bobina acabou")
    assert resultado.modo == "hibrida"
    assert resultado.criterio == "nota_bm25"
    assert SEM_LIMIAR_SIMILARIDADE in resultado.avisos


@pytest.mark.parametrize(
    ("com", "sem", "esperado"),
    [
        ([5.0, 6.0, 7.0], [1.0, 2.0], 3.5),  # separa tudo: o meio entre 2 e 5
        ([0.8, 0.9], [0.1], 0.45),
        ([3.0], [1.0, 5.0], 2.0),  # 5 sem resposta não dá para barrar sem perder o 3
    ],
)
def test_escolher_limiar(com, sem, esperado):
    assert escolher_limiar(com, sem) == pytest.approx(esperado)


def test_escolher_limiar_sem_os_dois_grupos_da_erro():
    with pytest.raises(ValueError):
        escolher_limiar([1.0], [])


# --- LGPD: o mascaramento vem antes dos vetores ---


def test_mascaramento_roda_antes_dos_vetores(com_sentido):
    busca, gerador = com_sentido
    resultado = busca.buscar(DADOS_PESSOAIS)
    enviado = gerador.perguntas[0]
    assert enviado == resultado.pergunta_mascarada
    for dado in ("529.982.247-25", "52998224725", "4111", "loja.bia@example.com", "99999-1234"):
        assert dado not in enviado
    for marcador in ("[CPF]", "[CARTAO]", "[EMAIL]", "[TELEFONE]"):
        assert marcador in enviado


def test_mascaramento_roda_antes_dos_vetores_no_gemini():
    cliente = ClienteEmbeddingFalso()
    indice = IndiceMemoria({artigo.id: [1.0] + [0.0] * 767 for artigo in ARTIGOS})
    Busca(ARTIGOS, GeradorGemini(cliente), indice, limiar_similaridade=0.5).buscar(DADOS_PESSOAIS)
    enviado = cliente.chamadas[0]["contents"]
    assert "529.982.247-25" not in enviado and "[CPF]" in enviado
    assert "loja.bia@example.com" not in enviado


# --- Queda do Google: segue só por palavras e avisa ---


@pytest.mark.parametrize(
    "erro",
    [
        erros_google.ServerError(503, {"error": {"message": "indisponível"}}),
        erros_google.ClientError(429, {"error": {"message": "cota"}}),
    ],
)
def test_queda_do_google_cai_para_a_busca_por_palavras(erro):
    gerador = GeradorGemini(ClienteEmbeddingFalso(erro=erro))
    indice = IndiceMemoria({artigo.id: [1.0] + [0.0] * 767 for artigo in ARTIGOS})
    busca = Busca(ARTIGOS, gerador, indice, limiar_bm25=1.0, limiar_similaridade=0.5)
    resultado = busca.buscar("a bobina acabou, onde compro?")
    assert resultado.modo == "palavras"
    assert resultado.criterio == "nota_bm25"
    assert resultado.achados[0].artigo.id == "bobina"
    assert len(resultado.avisos) == 1
    assert "A busca por sentido falhou" in resultado.avisos[0]
    assert "só da busca por palavras" in resultado.avisos[0]
    assert "indisponível" not in resultado.avisos[0]  # o texto do Google fica só no log


def test_sem_acesso_ao_google_busca_por_palavras_e_avisa():
    resultado = Busca(ARTIGOS, limiar_bm25=1.0).buscar("a bobina acabou")
    assert resultado.modo == "palavras"
    assert resultado.avisos == [SEM_ACESSO]


# --- Montagem a partir da configuração ---


def test_criar_busca_sem_chave_roda_so_por_palavras():
    config = Configuracao(
        _env_file=None, anthropic_api_key=None, gemini_api_key=None, google_cloud_project=""
    )
    busca = criar_busca(config, ARTIGOS)
    assert not busca.sentido_disponivel
    resultado = busca.buscar("perdi a maquininha, como bloqueio?")
    assert resultado.modo == "palavras"
    assert resultado.candidatos[0].artigo.id == "maquininha-perdida-ou-roubada"


def test_criar_busca_com_chave_e_sem_indice_avisa_para_indexar(monkeypatch, tmp_path):
    from app import busca as modulo

    monkeypatch.setattr(modulo, "criar_gerador", lambda config: GeradorVetoresFalso())
    monkeypatch.setattr(
        modulo,
        "carregar_indice_memoria",
        lambda artigos, modelo, dimensoes: carregar_indice_memoria(
            artigos, modelo, dimensoes, tmp_path / "nao-existe.json"
        ),
    )
    busca = criar_busca(Configuracao(_env_file=None, anthropic_api_key=None), ARTIGOS)
    resultado = busca.buscar("a bobina acabou")
    assert resultado.modo == "palavras"
    assert "scripts/indexar_base.py" in resultado.avisos[0]


def test_limiar_vazio_no_env_quer_dizer_use_o_arquivo():
    config = Configuracao(_env_file=None, limiar_similaridade="", limiar_bm25="")
    assert config.limiar_similaridade is None
    assert config.limiar_bm25 is None


# --- Limiares: base/limiares.json, versionado; o ambiente só sobrescreve ---

LIMIARES_DE_TESTE = {
    "bm25": {"limiar": 4.5, "calibrado_em": "2026-11-13"},
    "similaridade": {
        "limiar": 0.62,
        "modelo": "gemini-embedding-2",
        "dimensoes": 768,
        "calibrado_em": "2026-11-13",
    },
}


def _config_limiares(**valores):
    return Configuracao(_env_file=None, anthropic_api_key=None, **valores)


def test_limiares_vem_do_arquivo_versionado(tmp_path):
    caminho = tmp_path / "limiares.json"
    caminho.write_text(json.dumps(LIMIARES_DE_TESTE), "utf-8")
    limiares = escolher_limiares(_config_limiares(), "gemini-embedding-2", 768, caminho)
    assert limiares.bm25 == 4.5
    assert limiares.similaridade == 0.62
    assert "calibrado em 2026-11-13" in limiares.origem_bm25


def test_variavel_de_ambiente_sobrescreve_o_arquivo(tmp_path):
    caminho = tmp_path / "limiares.json"
    caminho.write_text(json.dumps(LIMIARES_DE_TESTE), "utf-8")
    config = _config_limiares(limiar_bm25=7.0, limiar_similaridade=0.7)
    limiares = escolher_limiares(config, "gemini-embedding-2", 768, caminho)
    assert (limiares.bm25, limiares.similaridade) == (7.0, 0.7)
    assert "ambiente" in limiares.origem_bm25 and "ambiente" in limiares.origem_similaridade


def test_limiar_de_outro_modelo_nao_vale(tmp_path):
    caminho = tmp_path / "limiares.json"
    caminho.write_text(json.dumps(LIMIARES_DE_TESTE), "utf-8")
    limiares = escolher_limiares(_config_limiares(), "gemini-embedding-001", 768, caminho)
    assert limiares.similaridade is None
    assert "outro modelo" in limiares.origem_similaridade


def test_sem_arquivo_de_limiares_nao_ha_limiar(tmp_path):
    limiares = escolher_limiares(_config_limiares(), None, None, tmp_path / "nao-existe.json")
    assert limiares.bm25 == 0.0
    assert limiares.similaridade is None


def test_o_arquivo_versionado_tem_data_e_conjunto_de_calibracao():
    dados = json.loads(ARQUIVO_LIMIARES.read_text("utf-8"))
    assert dados["conjunto_de_calibracao"] == "avaliacao/perguntas_calibracao.jsonl"
    assert dados["bm25"]["calibrado_em"]
    assert dados["bm25"]["limiar"] > 0


def test_erro_inesperado_do_sdk_tambem_cai_para_a_busca_por_palavras():
    gerador = GeradorGemini(ClienteEmbeddingFalso(erro=ValueError("opção recusada pelo SDK")))
    indice = IndiceMemoria({artigo.id: [1.0] + [0.0] * 767 for artigo in ARTIGOS})
    busca = Busca(ARTIGOS, gerador, indice, limiar_bm25=1.0, limiar_similaridade=0.5)
    resultado = busca.buscar("a bobina acabou, onde compro?")
    assert resultado.modo == "palavras"
    assert "erro inesperado na chamada ao Google (ValueError)" in resultado.avisos[0]
    assert "opção recusada" not in resultado.avisos[0]
