import anthropic
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco import ChamadoRegistro
from tests.falsos import REQUISICAO_FALSA, ClienteFalso, entrada_valida

TEXTO_COM_CPF = "Fui cobrado duas vezes pelo pedido 458812. Meu CPF é 529.982.247-25."


def test_saude_fica_aberta_mesmo_com_chave(abrir_api):
    api = abrir_api(chave_api="segredo-de-teste")
    resposta = api.get("/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "ia_configurada": True, "modelo": "claude-haiku-5-5"}


def test_raiz_leva_para_a_documentacao_com_a_demonstracao_desligada(abrir_api):
    resposta = abrir_api(demo_ativa=False).get("/", follow_redirects=False)
    assert resposta.status_code == 307
    assert resposta.headers["location"] == "/docs"


def test_cria_chamado_com_triagem_da_ia(abrir_api):
    resposta = abrir_api().post("/chamados", json={"texto": TEXTO_COM_CPF, "canal": "email"})
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["origem"] == "ia"
    assert corpo["canal"] == "email"
    assert corpo["categoria"] == "financeiro"
    assert corpo["fila"] == "Financeiro"
    assert corpo["numero_pedido"] == "458812"
    assert corpo["texto_mascarado"] == (
        "Fui cobrado duas vezes pelo pedido 458812. Meu CPF é [CPF]."
    )
    assert corpo["dados_pessoais_encontrados"] == {"CPF": 1}
    assert corpo["revisao_humana"] is False
    assert corpo["custo_usd"] == pytest.approx(0.0002)
    assert corpo["criado_em"].endswith(("Z", "+00:00"))
    assert "529.982.247-25" not in resposta.text
    assert "52998224725" not in resposta.text


def test_banco_guarda_so_o_texto_mascarado(abrir_api, motor):
    abrir_api().post("/chamados", json={"texto": TEXTO_COM_CPF})
    with Session(motor) as sessao:
        registro = sessao.scalars(select(ChamadoRegistro)).one()
    tudo = " ".join(str(getattr(registro, c.name)) for c in ChamadoRegistro.__table__.columns)
    assert "529.982.247-25" not in tudo
    assert "52998224725" not in tudo
    assert "[CPF]" in registro.texto_mascarado


def test_busca_por_id(abrir_api):
    api = abrir_api()
    criado = api.post("/chamados", json={"texto": TEXTO_COM_CPF}).json()
    resposta = api.get(f"/chamados/{criado['id']}")
    assert resposta.status_code == 200
    assert resposta.json() == criado


def test_chamado_inexistente_da_404(abrir_api):
    resposta = abrir_api().get("/chamados/999999")
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Chamado não encontrado."


def test_lista_filtra_revisao_humana(abrir_api):
    cliente = ClienteFalso(entrada_valida(), entrada_valida(prioridade="urgente"))
    api = abrir_api(cliente_ia=cliente)
    api.post("/chamados", json={"texto": TEXTO_COM_CPF})
    api.post("/chamados", json={"texto": "O sistema caiu no pedido 458812 e não consigo vender."})

    todos = api.get("/chamados").json()
    em_revisao = api.get("/chamados", params={"revisao_humana": "true"}).json()
    sem_revisao = api.get("/chamados", params={"revisao_humana": "false"}).json()

    assert len(todos) == 2
    assert todos[0]["id"] > todos[1]["id"]
    assert [c["prioridade"] for c in em_revisao] == ["urgente"]
    assert [c["prioridade"] for c in sem_revisao] == ["alta"]


@pytest.mark.parametrize("limite", [0, 201])
def test_limite_fora_da_faixa_e_recusado(abrir_api, limite):
    assert abrir_api().get("/chamados", params={"limite": limite}).status_code == 422


@pytest.mark.parametrize(
    "corpo",
    [{}, {"texto": "   "}, {"texto": "a" * 4001}, {"texto": "oi", "canal": "pombo-correio"}],
)
def test_entrada_invalida_e_recusada(abrir_api, corpo):
    assert abrir_api().post("/chamados", json=corpo).status_code == 422


def test_erro_422_nao_devolve_o_texto_enviado(abrir_api):
    texto = "Meu CPF é 529.982.247-25. " + "a" * 4000
    resposta = abrir_api().post("/chamados", json={"texto": texto})
    assert resposta.status_code == 422
    assert "529.982.247-25" not in resposta.text
    assert resposta.json()["detail"][0]["loc"] == ["body", "texto"]


def test_caractere_de_controle_nao_derruba_o_banco(abrir_api):
    resposta = abrir_api().post(
        "/chamados", json={"texto": "Fui cobrado\u0000 duas vezes no pedido 458812."}
    )
    assert resposta.status_code == 201
    assert "\u0000" not in resposta.json()["texto_mascarado"]


def test_numero_de_pedido_enorme_nao_derruba_o_banco(abrir_api):
    numero = "1" * 45
    api = abrir_api(cliente_ia=ClienteFalso(entrada_valida(numero_pedido=numero)))
    resposta = api.post("/chamados", json={"texto": f"Pedido {numero} não chegou."})
    assert resposta.status_code == 201
    assert resposta.json()["numero_pedido"] is None


def test_chave_de_api_e_exigida_quando_configurada(abrir_api):
    api = abrir_api(chave_api="segredo-de-teste")
    assert api.post("/chamados", json={"texto": "oi"}).status_code == 401
    errada = api.post("/chamados", json={"texto": "oi"}, headers={"X-API-Key": "errada"})
    assert errada.status_code == 401
    assert api.get("/metricas").status_code == 401
    certa = api.post(
        "/chamados", json={"texto": TEXTO_COM_CPF}, headers={"X-API-Key": "segredo-de-teste"}
    )
    assert certa.status_code == 201


def test_ia_fora_do_ar_nao_derruba_a_api(abrir_api):
    erro = anthropic.APIConnectionError(request=REQUISICAO_FALSA)
    api = abrir_api(cliente_ia=ClienteFalso(erro=erro))
    resposta = api.post("/chamados", json={"texto": "Quero cancelar minha assinatura."})
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["origem"] == "regras"
    assert corpo["categoria"] == "cancelamento"
    assert corpo["fila"] == "Retenção"
    assert corpo["revisao_humana"] is True
    assert corpo["custo_usd"] == 0


def test_metricas(abrir_api):
    api = abrir_api()
    api.post("/chamados", json={"texto": TEXTO_COM_CPF})
    api.post("/chamados", json={"texto": TEXTO_COM_CPF})
    metricas = api.get("/metricas").json()
    assert metricas["total_chamados"] == 2
    assert metricas["por_categoria"] == {"financeiro": 2}
    assert metricas["por_origem"] == {"ia": 2}
    assert metricas["em_revisao_humana"] == 0
    assert metricas["custo_total_usd"] == pytest.approx(0.0004)
    assert metricas["custo_medio_usd"] == pytest.approx(0.0002)


def test_metricas_sem_chamados(abrir_api):
    metricas = abrir_api().get("/metricas").json()
    assert metricas["total_chamados"] == 0
    assert metricas["taxa_revisao_humana"] == 0
    assert metricas["custo_medio_usd"] == 0
