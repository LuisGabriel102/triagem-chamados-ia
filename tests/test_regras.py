import pytest

from app.esquemas import Categoria, Prioridade, Sentimento
from app.regras import classificar_por_regras, normalizar


def test_normalizar_tira_acento_e_maiuscula():
    assert normalizar("COBRANÇA Indevida") == "cobranca indevida"


@pytest.mark.parametrize(
    ("texto", "categoria"),
    [
        ("Quero cancelar porque o boleto veio errado.", Categoria.CANCELAMENTO),
        ("A segunda via do boleto não chegou.", Categoria.FINANCEIRO),
        ("O aplicativo dá erro ao abrir.", Categoria.SUPORTE_TECNICO),
        ("Quanto custa o plano anual?", Categoria.COMERCIAL),
        ("A encomenda chegou com defeito.", Categoria.RECLAMACAO),
        ("Bom dia!", Categoria.OUTROS),
    ],
)
def test_categoria(texto, categoria):
    assert classificar_por_regras(texto).categoria is categoria


@pytest.mark.parametrize(
    ("texto", "prioridade"),
    [
        ("O sistema está fora do ar!", Prioridade.URGENTE),
        ("Vou registrar reclamação no Procon.", Prioridade.URGENTE),
        ("Quero cancelar a assinatura.", Prioridade.ALTA),
        ("O aplicativo dá erro ao abrir.", Prioridade.ALTA),
        ("Como faço para trocar o e-mail da conta?", Prioridade.BAIXA),
        ("Quero uma proposta para 10 usuários.", Prioridade.MEDIA),
    ],
)
def test_prioridade(texto, prioridade):
    assert classificar_por_regras(texto).prioridade is prioridade


@pytest.mark.parametrize(
    ("texto", "sentimento"),
    [
        ("Atendimento péssimo, um absurdo.", Sentimento.NEGATIVO),
        ("Parabéns pelo excelente atendimento!", Sentimento.POSITIVO),
        ("Qual o prazo de entrega?", Sentimento.NEUTRO),
    ],
)
def test_sentimento(texto, sentimento):
    assert classificar_por_regras(texto).sentimento is sentimento


@pytest.mark.parametrize(
    ("texto", "numero"),
    [
        ("Meu pedido 458812 não chegou.", "458812"),
        ("Pedido nº 771203 com defeito.", "771203"),
        ("Sobre o pedido #552310", "552310"),
        ("Pedido: 458812", "458812"),
        ("pedido 458.812 veio errado", "458812"),
        ("Protocolo 20261103558 sem resposta.", None),
        ("Meu pedido não chegou.", None),
    ],
)
def test_numero_do_pedido(texto, numero):
    assert classificar_por_regras(texto).numero_pedido == numero


def test_regras_nao_inventam_confianca_e_explicam_a_decisao():
    triagem = classificar_por_regras("Quero cancelar a assinatura.")
    assert triagem.confianca is None
    assert "'cancel'" in triagem.justificativa
    assert triagem.resumo == "Quero cancelar a assinatura."


def test_resumo_longo_e_cortado():
    triagem = classificar_por_regras("palavra " * 60)
    assert len(triagem.resumo) <= 120
    assert triagem.resumo.endswith("...")
