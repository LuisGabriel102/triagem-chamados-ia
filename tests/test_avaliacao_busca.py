import json
import re

import pytest

from app.base_conhecimento import carregar_artigos
from app.config import Configuracao
from avaliacao import avaliar_busca as modulo
from tests.falsos import GeradorVetoresFalso

IDS_DOS_ARTIGOS = {artigo.id for artigo in carregar_artigos()}
# Os únicos dados pessoais permitidos nas perguntas: os de teste do repositório.
DADOS_DE_TESTE = re.compile(
    r"^(529\.982\.247-25|111\.444\.777-35|4111 1111 1111 1111|[\w.]+@example\.com"
    r"|\(82\) 99999-1234)$"
)


def _sem_google():
    return lambda: Configuracao(
        _env_file=None, anthropic_api_key=None, gemini_api_key=None, google_cloud_project=""
    )


# --- Os arquivos de perguntas ---


def test_perguntas_da_avaliacao_tem_40_com_gabarito_e_8_sem_resposta():
    perguntas = modulo.carregar_perguntas(modulo.ARQUIVO_PERGUNTAS)
    assert len(perguntas) == 48
    assert len({p["id"] for p in perguntas}) == 48
    com = [p for p in perguntas if p["gabarito"]]
    assert len(com) == 40
    assert {p["gabarito"] for p in com} <= IDS_DOS_ARTIGOS
    # Todo artigo aparece em pelo menos uma pergunta.
    assert {p["gabarito"] for p in com} == IDS_DOS_ARTIGOS


@pytest.mark.parametrize("arquivo", [modulo.ARQUIVO_PERGUNTAS, modulo.ARQUIVO_CALIBRACAO])
def test_dados_pessoais_das_perguntas_sao_so_os_de_teste(arquivo):
    perguntas = modulo.carregar_perguntas(arquivo)
    for pergunta in perguntas:
        for dado in pergunta["dados_pessoais"]:
            assert DADOS_DE_TESTE.match(dado), dado
            assert dado in pergunta["pergunta"]
    assert not arquivo.read_bytes().startswith(b"\xef\xbb\xbf")


def test_algumas_perguntas_trazem_dados_pessoais():
    perguntas = modulo.carregar_perguntas(modulo.ARQUIVO_PERGUNTAS)
    assert sum(bool(p["dados_pessoais"]) for p in perguntas) >= 5


def test_calibracao_usa_outras_perguntas():
    avaliacao = modulo.carregar_perguntas(modulo.ARQUIVO_PERGUNTAS)
    calibracao = modulo.carregar_perguntas(modulo.ARQUIVO_CALIBRACAO)
    assert len(calibracao) == 20
    assert {p["pergunta"] for p in avaliacao}.isdisjoint(p["pergunta"] for p in calibracao)
    assert {p["gabarito"] for p in calibracao if p["gabarito"]} <= IDS_DOS_ARTIGOS
    assert sum(p["gabarito"] is None for p in calibracao) == 6


# --- O script ---


def test_sem_google_roda_so_a_busca_por_palavras(monkeypatch, tmp_path):
    monkeypatch.setattr(modulo, "Configuracao", _sem_google())
    assert modulo.main(["--saida", str(tmp_path), "--indice", str(tmp_path / "i.json")]) == 0
    dados = json.loads((tmp_path / "busca.json").read_text("utf-8"))
    palavras = dados["resultados"]["palavras"]
    assert palavras["rodou"]
    assert palavras["resumo"]["perguntas"] == 48
    assert palavras["resumo"]["dados_no_texto_mascarado"] == 0
    assert palavras["resumo"]["dados_pessoais"] >= 5
    assert not dados["resultados"]["sentido"]["rodou"]
    assert not dados["resultados"]["hibrida"]["rodou"]
    texto = (tmp_path / "busca.md").read_text("utf-8")
    assert "Ressalva" in texto and "escritas junto com a base" in texto
    assert "não rodou" in texto
    assert not (tmp_path / "i.json").exists()  # sem Google, nada de índice


def test_com_gerador_falso_roda_os_tres_modos_sem_vazar_dados(monkeypatch, tmp_path):
    monkeypatch.setattr(modulo, "Configuracao", _sem_google())
    gerador = GeradorVetoresFalso()
    monkeypatch.setattr(modulo, "criar_gerador", lambda config: gerador)
    assert modulo.main(["--saida", str(tmp_path), "--indice", str(tmp_path / "i.json")]) == 0
    resultados = json.loads((tmp_path / "busca.json").read_text("utf-8"))["resultados"]
    for modo in ("palavras", "sentido", "hibrida"):
        assert resultados[modo]["rodou"], modo
        assert resultados[modo]["resumo"]["quedas_para_palavras"] == 0
    for modo in ("sentido", "hibrida"):
        assert resultados[modo]["resumo"]["dados_enviados"] == 0
    # Nenhum dado pessoal chegou ao gerador, em nenhuma pergunta.
    for texto in gerador.perguntas:
        assert "529.982.247-25" not in texto and "example.com" not in texto
        assert "4111" not in texto and "99999-1234" not in texto
    # Cada pergunta vai uma vez só (a híbrida reaproveita o vetor da busca por sentido).
    assert len(gerador.perguntas) == len(set(gerador.perguntas))
    assert "calibrado nesta rodada" in (tmp_path / "busca.md").read_text("utf-8")


def test_queda_do_google_na_primeira_pergunta_marca_nao_rodou(monkeypatch, tmp_path):
    monkeypatch.setattr(modulo, "Configuracao", _sem_google())
    gerador = GeradorVetoresFalso()
    monkeypatch.setattr(modulo, "criar_gerador", lambda config: gerador)

    def cair(texto):
        raise modulo.ErroSentido("falha na API do Google (ServerError 503)")

    original = modulo._preparar_sentido

    def preparar(config, artigos, caminho):
        gravador, indice, motivo = original(config, artigos, caminho)
        gerador.vetor_pergunta = cair
        return gravador, indice, motivo

    monkeypatch.setattr(modulo, "_preparar_sentido", preparar)
    assert modulo.main(["--saida", str(tmp_path), "--indice", str(tmp_path / "i.json")]) == 0
    resultados = json.loads((tmp_path / "busca.json").read_text("utf-8"))["resultados"]
    assert resultados["palavras"]["rodou"]
    assert not resultados["sentido"]["rodou"]
    assert "ServerError 503" in resultados["sentido"]["motivo"]


def test_limiar_do_bm25_da_configuracao_e_o_da_calibracao(monkeypatch, tmp_path):
    """Se a base ou as perguntas de calibração mudarem, este teste lembra de recalibrar."""
    monkeypatch.setattr(modulo, "Configuracao", _sem_google())
    assert modulo.main(["--calibrar", "--saida", str(tmp_path)]) == 0
    calibracao = json.loads((tmp_path / "calibracao.json").read_text("utf-8"))
    assert calibracao["nota_bm25"]["limiar"] == Configuracao(_env_file=None).limiar_bm25
    assert calibracao["similaridade"] is None


def test_gravador_reaproveita_o_vetor_e_guarda_o_que_foi_enviado():
    gerador = GeradorVetoresFalso()
    gravador = modulo.GeradorGravador(gerador)
    gravador.vetor_pergunta("a bobina acabou")
    gravador.vetor_pergunta("a bobina acabou")
    assert gravador.enviados == ["a bobina acabou", "a bobina acabou"]
    assert gravador.chamadas == 1
    assert gerador.perguntas == ["a bobina acabou"]


def test_resumo_separa_com_e_sem_resposta():
    linhas = [
        {
            "gabarito": "bobina",
            "acerto_1": True,
            "acerto_3": True,
            "nada_encontrado": False,
            "dados_pessoais": 1,
            "dados_enviados": 0,
            "dados_no_texto_mascarado": 0,
            "modo_que_rodou": "hibrida",
        },
        {
            "gabarito": "pix-na-maquininha",
            "acerto_1": False,
            "acerto_3": True,
            "nada_encontrado": True,
            "dados_pessoais": 0,
            "dados_enviados": 0,
            "dados_no_texto_mascarado": 0,
            "modo_que_rodou": "palavras",
        },
        {
            "gabarito": None,
            "acerto_1": False,
            "acerto_3": False,
            "nada_encontrado": True,
            "dados_pessoais": 0,
            "dados_enviados": 0,
            "dados_no_texto_mascarado": 0,
            "modo_que_rodou": "hibrida",
        },
    ]
    resumo = modulo.resumir(linhas, "hibrida")
    assert resumo["com_resposta"] == 2 and resumo["sem_resposta"] == 1
    assert resumo["acerto_1"] == 1 and resumo["acerto_3"] == 2
    assert resumo["com_resposta_em_nada_encontrado"] == 1
    assert resumo["sem_resposta_em_nada_encontrado"] == 1
    assert resumo["quedas_para_palavras"] == 1
