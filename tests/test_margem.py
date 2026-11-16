"""A margem de erro (intervalo de Wilson, 95%) dos números da avaliação."""

import pytest

from avaliacao.avaliar_agente import _pct
from avaliacao.margem import faixa_em_texto, intervalo_wilson


def test_numeros_oficiais_da_prova_2():
    # 11 de 21: a faixa é larga, de 32% a 72%.
    assert faixa_em_texto(11, 21) == "de 32% a 72%"
    # 2 de 40: de 1% a 17%.
    assert faixa_em_texto(2, 40) == "de 1% a 17%"


def test_todos_certos_nao_vira_certeza():
    # A conta simples daria de 100% a 100%. O Wilson não: com 8 casos, o de baixo é 68%.
    de, ate = intervalo_wilson(8, 8)
    assert ate == 1.0
    assert round(de, 2) == 0.68


def test_nenhum_certo_nao_fica_negativo():
    de, ate = intervalo_wilson(0, 7)
    assert de == 0.0
    assert 0.3 < ate < 0.4


def test_a_faixa_contem_a_taxa_medida():
    for parte, todo in [(1, 3), (23, 35), (2, 60), (39, 40)]:
        de, ate = intervalo_wilson(parte, todo)
        assert de <= parte / todo <= ate


def test_mais_perguntas_estreitam_a_faixa():
    de_pequena, ate_pequena = intervalo_wilson(5, 10)
    de_grande, ate_grande = intervalo_wilson(50, 100)
    assert ate_grande - de_grande < ate_pequena - de_pequena


@pytest.mark.parametrize(("parte", "todo"), [(1, 0), (-1, 5), (6, 5)])
def test_entrada_invalida(parte, todo):
    with pytest.raises(ValueError):
        intervalo_wilson(parte, todo)


def test_relatorio_mostra_a_faixa():
    assert _pct({"parte": 11, "todo": 21}) == "11/21 (52%; de 32% a 72%)"
    assert _pct({"parte": 0, "todo": 0}) == "—"
