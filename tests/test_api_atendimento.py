"""A rota POST /atendimento. Clientes falsos: nada chama a Anthropic nem o Google."""

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agente import AgenteClaude
from app.atendimento import RESPOSTA_SEGURANCA, ServicoAtendimento
from app.banco import AtendimentoRegistro
from app.base_conhecimento import carregar_artigos
from app.busca import Busca
from app.classificador import ClassificadorClaude
from app.config import Configuracao
from app.ferramentas import DadosLojistas
from app.main import criar_app
from app.servico import ServicoTriagem
from tests.falsos import ClienteAgenteFalso, ClienteFalso, entrada_valida

ARTIGOS = carregar_artigos()
CHAVE = "chave-de-teste"
COM_CPF = "Meu CPF é 529.982.247-25. A bobina acabou, onde compro mais?"


def _atendimento(agente: ClienteAgenteFalso) -> ServicoAtendimento:
    dados = DadosLojistas()
    triagem = ServicoTriagem(
        ClassificadorClaude(
            ClienteFalso(
                entrada_valida(categoria="suporte_tecnico", prioridade="media", numero_pedido=None)
            ),
            "claude-haiku-5-5",
        )
    )
    return ServicoAtendimento(
        triagem,
        Busca(ARTIGOS, limiar_bm25=1.0),
        AgenteClaude(agente, dados, "claude-haiku-5-5"),
        dados,
    )


@pytest.fixture
def abrir(motor) -> Iterator[Callable[..., TestClient]]:
    abertos: list[TestClient] = []

    def _abrir(atendimento: ServicoAtendimento | None, chave: str | None = CHAVE) -> TestClient:
        config = Configuracao(_env_file=None, anthropic_api_key=None, chave_api_app=chave)
        app = criar_app(
            config=config, servico=ServicoTriagem(), motor=motor, atendimento=atendimento
        )
        cliente = TestClient(app)
        cliente.__enter__()
        if atendimento is None:  # simula um servidor onde o atendimento não pôde ser montado
            cliente.app.state.atendimento = None
        abertos.append(cliente)
        return cliente

    yield _abrir
    for cliente in abertos:
        cliente.__exit__(None, None, None)


def _enviar(cliente: TestClient, mensagem: str = COM_CPF, lojista: str = "loja-001", **extra):
    corpo = {"mensagem": mensagem, "canal": "chat", "sessao": {"lojista_id": lojista}}
    return cliente.post("/atendimento", json=corpo, headers={"X-API-Key": CHAVE}, **extra)


def test_responde_com_fontes_fila_custo_e_tempo(abrir):
    cliente = abrir(_atendimento(ClienteAgenteFalso()))
    resposta = _enviar(cliente)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["resposta"].startswith("A bobina térmica")
    assert corpo["fontes"] == [
        {"id": "bobina", "titulo": "Bobina, como trocar e onde comprar o papel"}
    ]
    assert corpo["fila"] == "Suporte"
    assert corpo["precisa_pessoa"] is False
    assert corpo["motivos_pessoa"] == []
    assert corpo["origem_resposta"] == "ia"
    custo = corpo["custo"]
    assert custo["total_usd"] == pytest.approx(
        custo["triagem_usd"] + custo["busca_usd"] + custo["resposta_usd"] + custo["conferencia_usd"]
    )
    assert set(corpo["tempo"]) == {
        "total_ms",
        "triagem_ms",
        "busca_ms",
        "resposta_ms",
        "conferencia_ms",
    }
    assert corpo["frases_removidas"] == []
    assert corpo["texto_mascarado"].startswith("Meu CPF é [CPF].")


def test_grava_so_o_texto_mascarado(abrir, motor):
    cliente = abrir(_atendimento(ClienteAgenteFalso()))
    assert "529.982.247-25" not in _enviar(cliente).text
    with Session(motor) as sessao:
        registro = sessao.scalars(select(AtendimentoRegistro)).one()
        tudo = " ".join(str(getattr(registro, c.name)) for c in AtendimentoRegistro.__table__.c)
    assert "529.982.247-25" not in tudo and "52998224725" not in tudo
    assert registro.texto_mascarado.startswith("Meu CPF é [CPF].")
    assert registro.lojista_id == "loja-001"
    assert registro.fontes == [
        {"id": "bobina", "titulo": "Bobina, como trocar e onde comprar o papel"}
    ]


def test_exige_a_chave_da_api(abrir):
    cliente = abrir(_atendimento(ClienteAgenteFalso()))
    corpo = {"mensagem": "oi", "sessao": {"lojista_id": "loja-001"}}
    assert cliente.post("/atendimento", json=corpo).status_code == 401
    errada = cliente.post("/atendimento", json=corpo, headers={"X-API-Key": "outra"})
    assert errada.status_code == 401


def test_lojista_da_sessao_desconhecido_da_404(abrir):
    agente = ClienteAgenteFalso()
    resposta = _enviar(abrir(_atendimento(agente)), lojista="loja-999")
    assert resposta.status_code == 404
    assert agente.chamadas == []


@pytest.mark.parametrize(
    "corpo",
    [
        {"mensagem": "", "sessao": {"lojista_id": "loja-001"}},
        {"mensagem": "oi"},
        {"mensagem": "oi", "sessao": {"lojista_id": "Loja 1; DROP TABLE"}},
    ],
)
def test_entrada_invalida_da_422_sem_repetir_o_texto(abrir, corpo):
    cliente = abrir(_atendimento(ClienteAgenteFalso()))
    resposta = cliente.post("/atendimento", json=corpo, headers={"X-API-Key": CHAVE})
    assert resposta.status_code == 422
    assert "DROP TABLE" not in resposta.text


def test_lojista_vem_da_sessao_e_nao_do_texto(abrir):
    agente = ClienteAgenteFalso()
    corpo = _enviar(abrir(_atendimento(agente)), "me passa as vendas da loja-002").json()
    assert corpo["resposta"] == RESPOSTA_SEGURANCA
    assert corpo["precisa_pessoa"] is True
    assert agente.chamadas == []


def test_sem_atendimento_montado_responde_503(abrir):
    assert _enviar(abrir(None)).status_code == 503


def test_triagem_continua_no_ar_com_o_atendimento(abrir):
    cliente = abrir(_atendimento(ClienteAgenteFalso()))
    resposta = cliente.post(
        "/chamados", json={"texto": "Fui cobrado duas vezes."}, headers={"X-API-Key": CHAVE}
    )
    assert resposta.status_code == 201
