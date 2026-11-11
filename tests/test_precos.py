from datetime import date

import pytest

from app.classificador import Uso
from app.config import Configuracao
from app.precos import Precos, preco_gemini, precos_do_provedor
from app.servico import calcular_custo, criar_servico
from tests.falsos import ClienteGeminiFalso


def test_claude_usa_o_preco_da_configuracao():
    config = Configuracao(_env_file=None, preco_entrada_usd_mtok=0.2, preco_saida_usd_mtok=1.0)
    assert precos_do_provedor(config) == Precos(
        entrada=0.2, saida=1.0, cache_leitura=0.10, cache_escrita=1.25
    )


def test_flash_lite_tem_preco_fixo():
    assert preco_gemini("gemini-3.5-flash-lite") == Precos(
        entrada=0.30, saida=2.50, cache_leitura=0.10, cache_escrita=0.0
    )


@pytest.mark.parametrize(
    ("dia", "entrada", "saida"),
    [
        (date(2026, 11, 11), 0.75, 3.75),
        (date(2026, 12, 31), 0.75, 3.75),
        (date(2027, 1, 1), 1.50, 7.50),
    ],
)
def test_flash_38_tem_preco_de_lancamento_ate_o_fim_de_2026(dia, entrada, saida):
    precos = preco_gemini("gemini-3.8-flash", hoje=dia)
    assert (precos.entrada, precos.saida) == (entrada, saida)


def test_fora_do_endpoint_global_custa_10_por_cento_a_mais():
    precos = preco_gemini("gemini-3.5-flash-lite", "us-central1")
    assert precos.entrada == pytest.approx(0.33)
    assert precos.saida == pytest.approx(2.75)


def test_modelo_sem_preco_fica_marcado():
    assert preco_gemini("gemini-9-ultra").conhecido is False


def test_custo_do_gemini_le_o_cache_a_10_por_cento_e_nao_cobra_gravacao():
    uso = Uso(tokens_entrada=200, tokens_saida=370, tokens_cache_leitura=1300)
    p = preco_gemini("gemini-3.5-flash-lite")
    esperado = (200 * 0.30 + 1300 * 0.30 * 0.10 + 370 * 2.50) / 1_000_000
    custo = calcular_custo(uso, p.entrada, p.saida, p.cache_leitura, p.cache_escrita)
    assert custo == pytest.approx(esperado)


def test_criar_servico_usa_o_gemini_e_o_preco_dele(monkeypatch):
    monkeypatch.setattr("app.classificador_gemini.genai.Client", lambda **_: ClienteGeminiFalso())
    servico = criar_servico(
        Configuracao(_env_file=None, provedor_ia="gemini", google_cloud_project="p")
    )
    assert servico.ia_configurada
    assert servico.modelo == "gemini-3.5-flash-lite"
    resultado = servico.triar("Fui cobrado duas vezes pelo pedido 458812.")
    assert resultado.custo_usd == pytest.approx((1500 * 0.30 + 370 * 2.50) / 1_000_000)
