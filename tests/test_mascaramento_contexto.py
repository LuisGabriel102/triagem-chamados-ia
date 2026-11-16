"""RG, CEP, endereço e nome (16/11/2026): o que esconde e o que precisa ficar.

Todos os dados são inventados. Os casos "precisa ficar" vieram de textos do próprio
repositório (artigos e perguntas), onde a primeira versão das regras errou.
"""

import pytest

from app.mascaramento import mascarar


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("meu RG é 12.345.678-9", "meu RG é [RG]"),
        ("rg: 123456789", "rg: [RG]"),
        ("RG 12.345.678-X emitido ontem", "RG [RG] emitido ontem"),
        # A normalização (NFKC) já troca o "º" por "o", antes de tudo.
        ("identidade nº 1234567 SSP", "identidade no [RG] SSP"),
        ("o documento 12.345.678-9 está vencido", "o documento [RG] está vencido"),
    ],
)
def test_rg(texto, esperado):
    resultado = mascarar(texto)
    assert resultado.texto == esperado
    assert resultado.encontrados == {"RG": 1}


@pytest.mark.parametrize(
    "texto",
    [
        "a loja fica na Rua das Flores, 120",
        "moro na rua das flores 120",
        "Av. Brasil, nº 45, sala 3",
        "avenida principal número 900",
        "Travessa do Sol, 7 - casa 2",
    ],
)
def test_endereco(texto):
    resultado = mascarar(texto)
    assert "[ENDERECO]" in resultado.texto
    assert resultado.encontrados == {"ENDERECO": 1}
    # O número da casa não sobra solto depois do marcador.
    assert not any(c.isdigit() for c in resultado.texto.split("[ENDERECO]")[1][:3])


def test_endereco_esconde_a_casa_e_deixa_o_cep():
    # O CEP sozinho aponta uma região (decisão de antes, em test_mascaramento.py).
    resultado = mascarar("Rua das Flores, 120, CEP 57000-123")
    assert resultado.texto == "[ENDERECO], CEP 57000-123"


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("meu nome é Joana Prado", "meu nome é [NOME]"),
        ("meu nome e joana, tudo bem?", "meu nome e [NOME], tudo bem?"),
        ("me chamo Bruno de Souza e tenho um bazar", "me chamo [NOME] e tenho um bazar"),
        ("meu nome é joana da padaria", "meu nome é [NOME] da padaria"),
        ("Oi, aqui é o Carlos da oficina", "Oi, aqui é o [NOME] da oficina"),
        ("sou a Marlene Duarte, do ateliê", "sou a [NOME], do ateliê"),
        ("Atenciosamente, Marlene Duarte.", "Atenciosamente, [NOME]."),
        ("nome do titular: Ana Lima", "nome do titular: [NOME]"),
        ("Nome completo é Ana Maria dos Santos", "Nome completo é [NOME]"),
    ],
)
def test_nome(texto, esperado):
    resultado = mascarar(texto)
    assert resultado.texto == esperado
    assert resultado.encontrados == {"NOME": 1}


@pytest.mark.parametrize(
    "texto",
    [
        # Sem maiúscula depois de "sou" ou "aqui é": não é nome.
        "sou a dona da loja e quero trocar de plano",
        "aqui é do bazar, tudo bem?",
        "Sou proprietária de um ateliê",
        # Sigla e palavra de cargo não são nome.
        "não tenho empresa, não sou MEI nem nada",
        "Sou Cliente da Tapiri há dois anos",
        "Atenciosamente, Equipe Tapiri",
        # Texto de ajuda: "nome do titular" sem dois-pontos nem "é".
        "Nome do titular ou razão social: a mudança pede o documento.",
        # "rua" sem endereço; número que é quantidade, não casa.
        "vendi na rua das flores ontem 3 vezes",
        "passei na avenida e paguei 2 parcelas",
        "fui na rua comprar bobina",
        # Números que não são RG nem CEP.
        "o protocolo é 2026111612345",
        "vendi R$ 1.234,56 ontem",
        "a venda de 16/11/2026 às 14:30",
        "pedido 12345-6789 do estoque",
    ],
)
def test_precisa_ficar(texto):
    resultado = mascarar(texto)
    assert resultado.texto == texto
    assert resultado.encontrados == {}


def test_juntos_com_os_dados_antigos():
    texto = (
        "Meu nome é Joana Prado, CPF 529.982.247-25, RG 12.345.678-9, "
        "moro na Rua das Flores, 120, CEP 57000-123, e-mail joana@example.com."
    )
    resultado = mascarar(texto)
    assert resultado.texto == (
        "Meu nome é [NOME], CPF [CPF], RG [RG], moro na [ENDERECO], CEP 57000-123, e-mail [EMAIL]."
    )
    assert resultado.encontrados == {"NOME": 1, "CPF": 1, "RG": 1, "ENDERECO": 1, "EMAIL": 1}


def test_marcador_novo_nao_vira_palavra_da_busca():
    # O BM25 não pode achar o artigo de "alterar dados" só porque apareceu [NOME].
    from app.busca import _MARCADOR

    assert _MARCADOR.sub(" ", "[NOME] [RG] [ENDERECO]").split() == []
