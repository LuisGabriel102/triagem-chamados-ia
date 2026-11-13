import json
from datetime import date, datetime

import pytest

from app.ferramentas import (
    FERRAMENTAS_DE_DADOS,
    DadosLojistas,
    LojistaDesconhecido,
    proximo_dia_util,
)

# Uma sexta-feira, às 10h.
AGORA = datetime(2026, 11, 13, 10, 0)
DADOS = DadosLojistas(agora=lambda: AGORA)
# O que nunca pode chegar à IA, de nenhum lojista.
PROIBIDOS = [
    "529.982.247-25",
    "111.444.777-35",
    "12345-6",
    "65432-1",
    "11223-4",
    "agencia",
    "conta_recebimento",
    '"documento"',  # a chave do cadastro (prazo_documentos é outra coisa)
    "example.com",
    "99999-1234",
    "TPS-",
    "TPM-",
    "numero_serie",
    "nome_fantasia",
]


def test_ferramentas_nao_tem_parametro_de_lojista():
    for ferramenta in FERRAMENTAS_DE_DADOS:
        assert ferramenta["strict"] is True
        esquema = ferramenta["input_schema"]
        assert esquema["properties"] == {}
        assert esquema["additionalProperties"] is False


@pytest.mark.parametrize("lojista", ["loja-001", "loja-002", "loja-003"])
@pytest.mark.parametrize("ferramenta", ["consultar_recebimentos", "status_maquininha"])
def test_a_ia_nunca_recebe_documento_conta_nem_contato(lojista, ferramenta):
    saida = json.dumps(DADOS.executar(ferramenta, lojista), ensure_ascii=False)
    for proibido in PROIBIDOS:
        assert proibido not in saida, proibido


def test_os_tres_casos_que_batem_com_a_base():
    vendas_1 = DADOS.consultar_recebimentos("loja-001")["vendas"]
    assert any(v["situacao"] == "a_receber" for v in vendas_1)
    maquininhas_2 = DADOS.status_maquininha("loja-002")["maquininhas"]
    assert any(m["situacao"] == "bloqueada" for m in maquininhas_2)
    vendas_3 = DADOS.consultar_recebimentos("loja-003")["vendas"]
    retida = next(v for v in vendas_3 if v["situacao"] == "retido_contestacao")
    assert retida["prazo_documentos"] == "2026-11-17"


def test_datas_contadas_a_partir_de_hoje_e_valor_liquido():
    recebimentos = DADOS.consultar_recebimentos("loja-001")
    assert recebimentos["hoje"] == "2026-11-13"
    assert recebimentos["plano"] == "Plano Mensal"
    debito = next(v for v in recebimentos["vendas"] if v["venda"] == "v-1001")
    assert debito["data_venda"] == "2026-11-12"
    assert debito["data_prevista"] == "2026-11-13"
    assert debito["valor_liquido"] == round(45.90 * (1 - 0.0119), 2)


def test_data_prevista_no_fim_de_semana_vai_para_segunda():
    assert proximo_dia_util(date(2026, 11, 14)) == date(2026, 11, 16)  # sábado
    assert proximo_dia_util(date(2026, 11, 15)) == date(2026, 11, 16)  # domingo
    assert proximo_dia_util(date(2026, 11, 13)) == date(2026, 11, 13)  # sexta


def test_status_da_maquininha_traz_a_ultima_conexao():
    saida = DADOS.status_maquininha("loja-003")
    feira = next(m for m in saida["maquininhas"] if m["apelido"] == "Feira")
    assert feira["situacao"] == "sem_conexao"
    assert feira["ultima_conexao"] == "2026-11-11 10:00"


def test_lojista_desconhecido_e_ferramenta_desconhecida_dao_erro():
    assert DADOS.existe("loja-001") and not DADOS.existe("loja-999")
    with pytest.raises(LojistaDesconhecido):
        DADOS.executar("consultar_recebimentos", "loja-999")
    with pytest.raises(ValueError):
        DADOS.executar("apagar_tudo", "loja-001")
