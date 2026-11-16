"""Conserto 2: os dias úteis e as datas por extenso são contados em Python."""

from datetime import date, datetime

import pytest

from app.agente import PROMPT_AGENTE, montar_contexto
from app.datas import (
    data_prevista,
    dias_uteis_entre,
    ha_quanto_tempo,
    momento_por_extenso,
    por_extenso,
    prazos_a_partir_de,
    proximo_dia_util,
    somar_dias_uteis,
)

SEXTA = date(2026, 11, 13)


def test_por_extenso_com_o_dia_da_semana():
    assert por_extenso(SEXTA) == "sexta, 13/11/2026"
    assert por_extenso(date(2026, 11, 16)) == "segunda, 16/11/2026"
    assert momento_por_extenso(datetime(2026, 11, 11, 9, 5)) == "quarta, 11/11/2026, 09:05"


def test_dias_uteis():
    assert somar_dias_uteis(SEXTA, 1) == date(2026, 11, 16)  # sexta + 1 = segunda
    assert somar_dias_uteis(date(2026, 11, 14), 1) == date(2026, 11, 16)  # sábado + 1
    assert somar_dias_uteis(date(2026, 11, 12), 1) == SEXTA  # quinta + 1
    assert proximo_dia_util(date(2026, 11, 15)) == date(2026, 11, 16)  # domingo
    assert proximo_dia_util(SEXTA) == SEXTA
    assert dias_uteis_entre(SEXTA, date(2026, 11, 16)) == 1
    assert dias_uteis_entre(SEXTA, SEXTA) == 0


@pytest.mark.parametrize(
    ("plano", "forma", "esperado"),
    [
        ("Plano Na Hora", "debito", date(2026, 11, 16)),
        ("Plano Na Hora", "credito", date(2026, 11, 16)),
        ("Plano Na Hora", "parcelado", date(2026, 11, 16)),
        ("Plano Mensal", "debito", date(2026, 11, 16)),
        ("Plano Mensal", "credito", date(2026, 12, 14)),  # 13/12 é domingo
        ("Plano Mensal", "parcelado", date(2026, 12, 14)),
        ("Plano Mensal", "pix", SEXTA),
        ("Plano Na Hora", "pix", SEXTA),
    ],
)
def test_data_prevista_pelas_regras_dos_artigos(plano, forma, esperado):
    assert data_prevista(plano, forma, SEXTA) == esperado


def test_prazos_a_partir_de_hoje():
    assert prazos_a_partir_de(SEXTA) == {
        "1 dia útil": "segunda, 16/11/2026",
        "30 dias": "segunda, 14/12/2026 (13/12 é domingo)",
    }


def test_ha_quanto_tempo():
    assert ha_quanto_tempo(1) == "1 minuto"
    assert ha_quanto_tempo(1500) == "25 horas"
    assert ha_quanto_tempo(2880) == "2 dias"


def test_a_mensagem_leva_hoje_e_os_prazos_fora_do_cache():
    contexto = montar_contexto("quando cai?", "chat", [], SEXTA)
    assert "<hoje>sexta, 13/11/2026</hoje>" in contexto
    assert "- 1 dia útil: segunda, 16/11/2026" in contexto
    # O texto fixo, que vai para o cache, não tem data nenhuma.
    assert "2026" not in PROMPT_AGENTE
    assert "Não faça conta de data" in PROMPT_AGENTE
