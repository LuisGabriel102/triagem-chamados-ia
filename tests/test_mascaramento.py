import json
import re
from pathlib import Path

import pytest

from app.mascaramento import (
    cnpj_valido,
    cpf_valido,
    limpar_texto,
    luhn_valido,
    mascarar,
    parece_telefone,
)

CHAMADOS_TESTE = Path(__file__).parent.parent / "avaliacao" / "chamados_teste.jsonl"


def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


@pytest.mark.parametrize(
    ("texto", "marcador"),
    [
        # CPF
        ("Meu CPF é 529.982.247-25, obrigado.", "[CPF]"),
        ("CPF 529982247-25", "[CPF]"),
        ("CPF 529 982 247 25", "[CPF]"),
        ("CPF 11144477735 para localizar", "[CPF]"),
        # Dígito verificador errado (cliente digitou errado), mas a palavra CPF está perto.
        ("meu cpf é 11144477736", "[CPF]"),
        # E-mail
        ("Escreva para joana.silva@example.com", "[EMAIL]"),
        # CNPJ, inclusive o alfanumérico
        ("CNPJ 11.222.333/0001-81", "[CNPJ]"),
        ("CNPJ 11222333000181", "[CNPJ]"),
        ("CNPJ 12.ABC.345/01DE-35", "[CNPJ]"),
        ("CNPJ 12ABC34501DE35", "[CNPJ]"),
        # Cartão, inclusive com validade logo depois e com dígito errado após a palavra cartão
        ("cartão 4111 1111 1111 1111 recusado", "[CARTAO]"),
        ("cartão 4111111111111111 recusado", "[CARTAO]"),
        ("pagamento com 4111 1111 1111 1111 12/28", "[CARTAO]"),
        ("pagamento com 4111 1111 1111 1111 123 12/28", "[CARTAO]"),
        ("5555555555554444 08/29", "[CARTAO]"),
        ("cartão 4111 1111 1111 1112 (digitei errado)", "[CARTAO]"),
        # Telefone
        ("Liga no (82) 99999-0000 por favor", "[TELEFONE]"),
        ("Liga no 82 98888-0000 por favor", "[TELEFONE]"),
        ("Liga no (82) 9 9999-0000 por favor", "[TELEFONE]"),
        ("Liga no 82 9 9999-0000 por favor", "[TELEFONE]"),
        ("Liga no +55 82 99999-1234 por favor", "[TELEFONE]"),
        ("Liga no +55 (82) 9 9999-0000 por favor", "[TELEFONE]"),
        # Este passa no teste de cartão por acaso: precisa sair como telefone.
        ("Liga no +55 82 99999-0007 por favor", "[TELEFONE]"),
        ("Liga no 82999990000 por favor", "[TELEFONE]"),
        ("Liga no 99999-0000 por favor", "[TELEFONE]"),
        ("tel 3221-4567", "[TELEFONE]"),
        ("fixo da loja: 8232214567", "[TELEFONE]"),
        # Truques: dígitos largos e caractere invisível no meio do CPF
        ("CPF ５２９.９８２.２４７-２５", "[CPF]"),
        ("CPF 529​.982.247-25", "[CPF]"),
    ],
)
def test_esconde_dado_pessoal(texto, marcador):
    resultado = mascarar(texto)
    assert marcador in resultado.texto
    assert not re.search(r"\d{4}", resultado.texto), resultado.texto


@pytest.mark.parametrize(
    "texto",
    [
        "Pedido 458812 chegou incompleto",
        "Pedido 4588-1234 veio errado",
        "Protocolo 20261103558 sem resposta",
        # 10 e 11 dígitos sem DDD válido: protocolo, não telefone.
        "Protocolo 2026110355",
        "Protocolo 20961103558",
        "Paguei R$ 189,90 no dia 15/11/2026",
        "Paguei R$ 1.234.567,89 em 3 vezes",
        "cartão final 4417 recusado",
        "número inválido 1234 5678 9012 3456",
        "CEP 57000-000",
        "me chama no zap, pedido 458812",
        "Usuário: empresa_alfa",
    ],
)
def test_nao_esconde_o_que_nao_e_dado_pessoal(texto):
    assert mascarar(texto).texto == texto


def test_conta_o_que_encontrou():
    resultado = mascarar("CPF 529.982.247-25, e-mail a@example.com e (82) 99999-0000")
    assert resultado.encontrados == {"CPF": 1, "EMAIL": 1, "TELEFONE": 1}


def test_texto_sem_dado_pessoal_fica_igual():
    texto = "O aplicativo fecha sozinho quando abro a aba de pedidos."
    resultado = mascarar(texto)
    assert resultado.texto == texto
    assert resultado.encontrados == {}


def test_limpar_texto_tira_invisiveis_e_controle():
    assert limpar_texto("a\x00b​c\nd\te") == "a bc\nd\te"
    assert limpar_texto("５２９") == "529"


def test_validadores():
    assert cpf_valido("529.982.247-25")
    assert not cpf_valido("529.982.247-26")
    assert not cpf_valido("111.111.111-11")
    assert cnpj_valido("11.222.333/0001-81")
    assert not cnpj_valido("11.222.333/0001-82")
    assert cnpj_valido("12.ABC.345/01DE-35")
    assert not cnpj_valido("12.ABC.345/01DE-36")
    assert luhn_valido("4111 1111 1111 1111")
    assert not luhn_valido("1234 5678 9012 3456")
    assert parece_telefone("82999990000")
    assert parece_telefone("8232214567")
    assert not parece_telefone("20261103558")
    assert not parece_telefone("2026110355")


def test_nenhum_dado_pessoal_do_conjunto_de_teste_chega_na_ia():
    """Cada chamado de teste lista os dados pessoais que contém.

    Depois do mascaramento, nenhum deles pode sobrar no texto, e os números
    que não são dado pessoal (como protocolo) precisam continuar lá.
    """
    chamados = [json.loads(linha) for linha in CHAMADOS_TESTE.read_text("utf-8").splitlines()]
    com_dado_pessoal = 0
    for chamado in chamados:
        texto_mascarado = mascarar(chamado["texto"]).texto
        for dado in chamado.get("dados_pessoais", []):
            com_dado_pessoal += 1
            if "@" in dado:
                assert dado not in texto_mascarado, chamado["id"]
            else:
                assert so_digitos(dado) not in so_digitos(texto_mascarado), chamado["id"]
        for numero in chamado.get("nao_mascarar", []):
            assert numero in texto_mascarado, chamado["id"]
    assert com_dado_pessoal >= 9
