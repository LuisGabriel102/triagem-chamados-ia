import anthropic
import httpx
import pytest

from app.classificador import ClassificadorClaude, Uso
from app.esquemas import Canal, Categoria, Origem
from app.servico import ServicoTriagem, calcular_custo
from tests.falsos import REQUISICAO_FALSA, ClienteFalso, entrada_valida

TEXTO_FINANCEIRO = "Fui cobrado duas vezes no pedido 458812."


def servico_com(cliente: ClienteFalso) -> ServicoTriagem:
    return ServicoTriagem(classificador=ClassificadorClaude(cliente, modelo="claude-haiku-5-5"))


def test_a_ia_so_recebe_o_texto_mascarado():
    cliente = ClienteFalso()
    resultado = servico_com(cliente).triar(
        "Meu CPF é 529.982.247-25 e o pedido 458812 veio errado.", Canal.EMAIL
    )
    mensagem = cliente.chamadas[0]["messages"][0]["content"]
    assert "[CPF]" in mensagem
    assert "529.982.247-25" not in mensagem
    assert "<canal>email</canal>" in mensagem
    assert resultado.dados_pessoais_encontrados == {"CPF": 1}


def test_caso_claro_com_confianca_alta_dispensa_revisao():
    resultado = servico_com(ClienteFalso()).triar(TEXTO_FINANCEIRO)
    assert resultado.origem is Origem.IA
    assert resultado.revisao_humana is False
    assert resultado.motivos_revisao == []
    assert resultado.fila == "Financeiro"
    assert resultado.custo_usd == pytest.approx(0.0002)


@pytest.mark.parametrize(
    ("alteracao", "trecho_do_motivo"),
    [
        ({"confianca": 0.6}, "confiança baixa"),
        ({"categoria": "outros"}, "categoria 'outros'"),
        ({"prioridade": "urgente"}, "prioridade urgente"),
    ],
)
def test_motivos_de_revisao_humana(alteracao, trecho_do_motivo):
    resultado = servico_com(ClienteFalso(entrada_valida(**alteracao))).triar(TEXTO_FINANCEIRO)
    assert resultado.revisao_humana is True
    assert any(trecho_do_motivo in motivo for motivo in resultado.motivos_revisao)


def test_sem_ia_usa_o_plano_b_e_pede_revisao():
    resultado = ServicoTriagem().triar("Quero cancelar minha assinatura.")
    assert resultado.origem is Origem.REGRAS
    assert resultado.triagem.categoria is Categoria.CANCELAMENTO
    assert resultado.revisao_humana is True
    assert resultado.custo_usd == 0
    assert "IA não configurada" in resultado.motivos_revisao[0]


@pytest.mark.parametrize(
    "erro",
    [
        anthropic.APIConnectionError(request=REQUISICAO_FALSA),
        anthropic.RateLimitError(
            "limite", response=httpx.Response(429, request=REQUISICAO_FALSA), body=None
        ),
        RuntimeError("defeito inesperado"),
    ],
)
def test_falha_da_ia_cai_no_plano_b(erro):
    resultado = servico_com(ClienteFalso(erro=erro)).triar("Quero cancelar minha assinatura.")
    assert resultado.origem is Origem.REGRAS
    assert resultado.triagem.categoria is Categoria.CANCELAMENTO
    assert resultado.revisao_humana is True
    assert "plano B" in resultado.motivos_revisao[0]


def test_numero_de_pedido_inventado_e_descartado():
    cliente = ClienteFalso(entrada_valida(numero_pedido="999999"))
    resultado = servico_com(cliente).triar("Fui cobrado duas vezes no mesmo mês.")
    assert resultado.triagem.numero_pedido is None
    assert resultado.revisao_humana is True
    assert "não aparece no texto" in resultado.motivos_revisao[0]


@pytest.mark.parametrize(
    "texto",
    [
        "Cobrança duplicada no pedido 458.812.",
        "Pedido 458812 2 itens faltando.",
        "Pedido: 458812, cobrado duas vezes.",
    ],
)
def test_numero_de_pedido_que_esta_no_texto_e_aceito(texto):
    resultado = servico_com(ClienteFalso()).triar(texto)
    assert resultado.triagem.numero_pedido == "458812"
    assert resultado.revisao_humana is False


def test_numero_de_pedido_dentro_de_outro_numero_nao_vale():
    cliente = ClienteFalso(entrada_valida(numero_pedido="4588"))
    resultado = servico_com(cliente).triar(TEXTO_FINANCEIRO)
    assert resultado.triagem.numero_pedido is None


def test_numero_de_pedido_longo_demais_vira_vazio():
    numero = "1" * 45
    cliente = ClienteFalso(entrada_valida(numero_pedido=numero))
    resultado = servico_com(cliente).triar(f"Pedido {numero} não chegou.")
    assert resultado.triagem.numero_pedido is None


def test_resposta_da_ia_tambem_passa_pelo_mascaramento():
    cpf = "CPF 529.982.247-25"
    cliente = ClienteFalso(
        entrada_valida(
            resumo=f"Cliente de {cpf} cobrado em dobro.",
            resposta_sugerida=f"Olá! Confirmamos o {cpf} no cadastro.",
            justificativa=f"Cobrança duplicada do {cpf}.",
        )
    )
    triagem = servico_com(cliente).triar(TEXTO_FINANCEIRO).triagem
    for campo in (triagem.resumo, triagem.resposta_sugerida, triagem.justificativa):
        assert "529.982.247-25" not in campo
        assert "[CPF]" in campo


def test_palavra_de_urgencia_que_a_ia_nao_confirmou_vai_para_revisao():
    # A IA (falsa) diz "alta", mas o texto fala em sistema fora do ar.
    resultado = servico_com(ClienteFalso()).triar("O sistema está fora do ar no pedido 458812.")
    assert resultado.revisao_humana is True
    assert any("indicam urgência" in motivo for motivo in resultado.motivos_revisao)


def test_falha_da_ia_que_foi_cobrada_entra_no_custo():
    cliente = ClienteFalso(entrada_valida(categoria="vendas"))
    resultado = servico_com(cliente).triar(TEXTO_FINANCEIRO)
    assert resultado.origem is Origem.REGRAS
    assert resultado.custo_usd == pytest.approx(0.0002)
    assert resultado.modelo == "claude-haiku-5-5"


def test_caractere_de_controle_nao_chega_ao_banco_nem_a_ia():
    cliente = ClienteFalso()
    resultado = servico_com(cliente).triar("Fui cobrado\x00 duas vezes no pedido 458812.")
    assert "\x00" not in resultado.texto_mascarado
    assert "\x00" not in cliente.chamadas[0]["messages"][0]["content"]


@pytest.mark.parametrize(
    ("uso", "esperado"),
    [
        (Uso(tokens_entrada=1000, tokens_saida=200), 0.0002),
        (Uso(tokens_cache_leitura=2000), 0.00002),
        (Uso(tokens_cache_escrita=1000), 0.000125),
        (Uso(), 0.0),
    ],
)
def test_calcular_custo(uso, esperado):
    assert calcular_custo(uso, preco_entrada=0.10, preco_saida=0.50) == pytest.approx(esperado)
