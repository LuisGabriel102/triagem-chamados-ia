import pytest

from app.busca_palavras import BuscaPalavras, normalizar, reduzir_plural, tokenizar

DOCUMENTOS = [
    ("bobina", "Bobina de papel térmico: como trocar a bobina da impressora."),
    ("pix", "Pix na maquininha: o cliente lê o QR code e o Pix cai na hora."),
    ("estorno", "Estorno: o dinheiro volta para o cliente depois do cancelamento."),
    ("prazos", "Prazos: o débito cai em 1 dia útil e o crédito em 30 dias."),
]


def test_normaliza_sem_acento_e_minusculas():
    assert normalizar("Cartão CRÉDITO Útil") == "cartao credito util"


@pytest.mark.parametrize(
    ("palavra", "esperado"),
    [
        ("vendas", "venda"),
        ("cartoes", "cartao"),
        ("reais", "real"),
        ("uteis", "util"),
        ("itens", "item"),
        ("valores", "valor"),
        ("meses", "mes"),
        ("depois", "depois"),
        ("pix", "pix"),
        ("mes", "mes"),
    ],
)
def test_reduz_plural(palavra, esperado):
    assert reduzir_plural(palavra) == esperado


def test_tokeniza_sem_palavras_vazias_nem_informais():
    assert tokenizar("Oi, vc sabe pra quando cai o dinheiro das vendas?") == [
        "sabe",
        "cai",
        "dinheiro",
        "venda",
    ]


def test_singular_e_plural_e_com_ou_sem_acento_sao_a_mesma_palavra():
    assert tokenizar("Os cartões das vendas") == tokenizar("cartao da venda")


def test_ordena_pelo_documento_mais_parecido():
    busca = BuscaPalavras(DOCUMENTOS)
    notas = busca.notas("como troca a bubina, ja comprei a BOBINA nova")
    assert notas[0][0] == "bobina"
    assert [id_ for id_, _ in busca.notas("o estorno do cliente")][0] == "estorno"
    assert busca.notas("quanto tempo o débito demora pra cair")[0][0] == "prazos"


def test_palavra_rara_pesa_mais_que_palavra_comum():
    # "cliente" está em dois documentos; "estorno", em um só.
    busca = BuscaPalavras(DOCUMENTOS)
    notas = dict(busca.notas("cliente estorno"))
    assert notas["estorno"] > notas["pix"]


def test_pergunta_sem_palavra_conhecida_nao_acha_nada():
    busca = BuscaPalavras(DOCUMENTOS)
    assert busca.notas("previsão do tempo amanhã") == []
    assert busca.notas("") == []


def test_notas_positivas_e_em_ordem_decrescente():
    busca = BuscaPalavras(DOCUMENTOS)
    notas = [nota for _, nota in busca.notas("cliente pix dinheiro cai")]
    assert notas == sorted(notas, reverse=True)
    assert all(nota > 0 for nota in notas)


def test_documento_comprido_tem_desconto():
    curto = ("curto", "estorno")
    comprido = ("comprido", "estorno " + "palavra qualquer " * 30)
    notas = dict(BuscaPalavras([curto, comprido]).notas("estorno"))
    assert notas["curto"] > notas["comprido"]


def test_sem_documentos_da_erro():
    with pytest.raises(ValueError):
        BuscaPalavras([])
