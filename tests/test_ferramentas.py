import json
from datetime import datetime

import pytest

from app.ferramentas import FERRAMENTAS_DE_DADOS, DadosLojistas, LojistaDesconhecido

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


def _venda(lojista, venda):
    return next(v for v in DADOS.consultar_recebimentos(lojista)["vendas"] if v["venda"] == venda)


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
    retida = _venda("loja-003", "v-3001")
    assert retida["situacao"] == "retido_contestacao"
    assert retida["prazo_documentos"] == "terça, 17/11/2026"
    assert retida["dias_ate_o_prazo_documentos"] == 4


# --- Conserto 2: as datas vêm calculadas, com o dia da semana ---


def test_datas_com_o_dia_da_semana_e_o_quando_calculado():
    recebimentos = DADOS.consultar_recebimentos("loja-001")
    assert recebimentos["hoje"] == "sexta, 13/11/2026"
    assert recebimentos["plano"] == "Plano Mensal"
    debito = _venda("loja-001", "v-1001")
    assert debito["data_venda"] == "quinta, 12/11/2026"
    assert debito["data_prevista"] == "sexta, 13/11/2026"
    assert debito["quando"] == "cai hoje, até as 18h"
    assert debito["valor_liquido"] == round(45.90 * (1 - 0.0119), 2)


def test_a_data_prevista_sai_das_regras_do_plano():
    # Plano Mensal: crédito à vista e parcelado em 30 dias.
    assert _venda("loja-001", "v-1002")["data_prevista"] == "quinta, 03/12/2026"
    assert _venda("loja-001", "v-1003")["quando"] == "cai na terça, 08/12/2026, daqui a 25 dias"
    # Pix cai na hora; débito em 1 dia útil.
    assert _venda("loja-001", "v-1004")["quando"] == "caiu na quarta, 11/11/2026"
    assert _venda("loja-001", "v-1005")["quando"] == "caiu na quarta, 11/11/2026"
    # Plano Na Hora: crédito em 1 dia útil. Venda em análise diz quando cai se for liberada.
    assert _venda("loja-002", "v-2001")["data_prevista"] == "sexta, 13/11/2026"
    assert _venda("loja-003", "v-3003")["quando"] == (
        "em análise; se for liberada, cai na sexta, 13/11/2026"
    )


def test_venda_de_sexta_no_debito_cai_na_segunda():
    sabado = DadosLojistas(agora=lambda: datetime(2026, 11, 14, 9, 0))  # um sábado
    debito = next(
        v for v in sabado.consultar_recebimentos("loja-001")["vendas"] if v["venda"] == "v-1001"
    )
    assert debito["data_venda"] == "sexta, 13/11/2026"
    assert debito["quando"] == "cai no próximo dia útil: segunda, 16/11/2026"


def test_status_da_maquininha_traz_a_ultima_conexao_por_extenso():
    saida = DADOS.status_maquininha("loja-003")
    assert saida["agora"] == "sexta, 13/11/2026, 10:00"
    feira = next(m for m in saida["maquininhas"] if m["apelido"] == "Feira")
    assert feira["situacao"] == "sem_conexao"
    assert feira["ultima_conexao"] == "quarta, 11/11/2026, 10:00"
    assert feira["ultima_conexao_ha"] == "2 dias"


def test_lojista_desconhecido_e_ferramenta_desconhecida_dao_erro():
    assert DADOS.existe("loja-001") and not DADOS.existe("loja-999")
    with pytest.raises(LojistaDesconhecido):
        DADOS.executar("consultar_recebimentos", "loja-999")
    with pytest.raises(ValueError):
        DADOS.executar("apagar_tudo", "loja-001")
