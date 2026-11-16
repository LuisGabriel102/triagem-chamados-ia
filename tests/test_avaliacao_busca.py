import json
import re

import pytest

from app.base_conhecimento import carregar_artigos
from app.busca import ARQUIVO_LIMIARES
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


def test_limiar_do_bm25_em_base_limiares_e_o_da_calibracao(monkeypatch, tmp_path):
    """Se a base ou as perguntas de calibração mudarem, este teste lembra de recalibrar."""
    monkeypatch.setattr(modulo, "Configuracao", _sem_google())
    destino = tmp_path / "limiares.json"
    assert modulo.main(["--calibrar", "--saida", str(tmp_path), "--limiares", str(destino)]) == 0
    calibracao = json.loads((tmp_path / "calibracao.json").read_text("utf-8"))
    versionado = json.loads(ARQUIVO_LIMIARES.read_text("utf-8"))
    assert calibracao["nota_bm25"]["limiar"] == versionado["bm25"]["limiar"]
    gravado = json.loads(destino.read_text("utf-8"))
    assert gravado["bm25"]["limiar"] == versionado["bm25"]["limiar"]
    assert gravado["conjunto_de_calibracao"] == "avaliacao/perguntas_calibracao.jsonl"
    assert gravado["bm25"]["calibrado_em"]


def test_calibrar_sem_google_mantem_o_limiar_da_similaridade_do_arquivo(monkeypatch, tmp_path):
    monkeypatch.setattr(modulo, "Configuracao", _sem_google())
    destino = tmp_path / "limiares.json"
    anterior = {"modelo": "gemini-embedding-2", "dimensoes": 768, "limiar": 0.61}
    destino.write_text(json.dumps({"similaridade": anterior}), "utf-8")
    assert modulo.main(["--calibrar", "--saida", str(tmp_path), "--limiares", str(destino)]) == 0
    assert json.loads(destino.read_text("utf-8"))["similaridade"] == anterior


def test_calibrar_com_gerador_grava_o_limiar_da_similaridade_com_o_modelo(monkeypatch, tmp_path):
    monkeypatch.setattr(modulo, "Configuracao", _sem_google())
    monkeypatch.setattr(modulo, "criar_gerador", lambda config: GeradorVetoresFalso())
    destino = tmp_path / "limiares.json"
    argumentos = ["--calibrar", "--saida", str(tmp_path), "--limiares", str(destino)]
    assert modulo.main([*argumentos, "--indice", str(tmp_path / "i.json")]) == 0
    similaridade = json.loads(destino.read_text("utf-8"))["similaridade"]
    assert similaridade["modelo"] == "modelo-falso"
    assert similaridade["dimensoes"] == 1024
    assert -1 <= similaridade["limiar"] <= 1


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
            "respondida_certa": True,
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
            "respondida_certa": False,
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
            "respondida_certa": False,
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
    # Acertou o artigo mas ficou abaixo do limiar: não conta como respondida e certa.
    assert resumo["respondidas_certas"] == 1
    assert resumo["com_resposta_em_nada_encontrado"] == 1
    assert resumo["sem_resposta_em_nada_encontrado"] == 1
    assert resumo["quedas_para_palavras"] == 1


# --- As perguntas da etapa 3 (escritas por um agente separado, só com o EMPRESA.md) ---

ARQUIVO_AGENTE = modulo.PASTA / "perguntas_agente.jsonl"
FILAS = {"Financeiro", "Suporte", "Vendas", "Retenção", "Ouvidoria", "Triagem humana"}


def test_perguntas_do_agente_tem_os_quatro_grupos_e_o_gabarito_completo():
    perguntas = modulo.carregar_perguntas(ARQUIVO_AGENTE)
    assert len(perguntas) == 60
    grupos = [p["grupo"] for p in perguntas]
    assert {g: grupos.count(g) for g in set(grupos)} == {
        "responde": 40,
        "sem_resposta": 10,
        "tentativa": 5,
        "urgente": 5,
    }
    for pergunta in perguntas:
        gabarito = pergunta["gabarito"]
        assert set(gabarito["artigos"]) <= IDS_DOS_ARTIGOS
        assert gabarito["fila"] in FILAS
        assert gabarito["lojista"] in {"loja-001", "loja-002", "loja-003"}
        assert gabarito["por_que"]
        if pergunta["grupo"] in ("tentativa", "urgente"):
            assert gabarito["chamar_pessoa"] is True
        if pergunta["grupo"] == "tentativa":
            assert gabarito["artigos"] == []
        for dado in pergunta["dados_pessoais"]:
            assert DADOS_DE_TESTE.match(dado) and dado in pergunta["pergunta"]


def test_artigos_certos_le_os_dois_formatos_de_gabarito():
    assert modulo.artigos_certos({"gabarito": "bobina"}) == ["bobina"]
    assert modulo.artigos_certos({"gabarito": None}) == []
    assert modulo.artigos_certos({"gabarito": {"artigos": ["estorno", "cancelar-uma-venda"]}}) == [
        "estorno",
        "cancelar-uma-venda",
    ]


def test_busca_roda_nas_perguntas_do_agente_so_nos_modos_pedidos(monkeypatch, tmp_path):
    monkeypatch.setattr(modulo, "Configuracao", _sem_google())
    monkeypatch.setattr(modulo, "criar_gerador", lambda config: GeradorVetoresFalso())
    argumentos = ["--perguntas", str(ARQUIVO_AGENTE), "--nome", "busca_agente"]
    argumentos += ["--modos", "sentido", "hibrida", "--saida", str(tmp_path)]
    assert modulo.main([*argumentos, "--indice", str(tmp_path / "i.json")]) == 0
    dados = json.loads((tmp_path / "busca_agente.json").read_text("utf-8"))
    assert set(dados["resultados"]) == {"sentido", "hibrida"}
    assert dados["resultados"]["sentido"]["resumo"]["perguntas"] == 60
    assert "perguntas_agente.jsonl" in (tmp_path / "busca_agente.md").read_text("utf-8")
