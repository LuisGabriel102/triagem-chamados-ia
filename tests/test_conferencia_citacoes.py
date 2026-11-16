"""A conferência por citação (16/11/2026). Nada chama API de verdade."""

from datetime import date, datetime
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.agente import AgenteClaude
from app.atendimento import AVISO_PESSOA, RESPOSTA_ESPERA, ServicoAtendimento, criar_conferente
from app.base_conhecimento import carregar_artigos
from app.busca import Busca
from app.classificador import ClassificadorClaude
from app.conferencia import ConferenteClaude, ErroConferencia
from app.conferencia_citacoes import (
    PROMPT_CITACOES,
    ConferenteCitacoes,
    frases_com_prova,
    ler_pedacos,
)
from app.config import Configuracao
from app.esquemas import Canal
from app.ferramentas import DadosLojistas
from app.servico import ServicoTriagem
from tests.falsos import (
    ClienteAgenteFalso,
    ClienteCitacoesFalso,
    ClienteFalso,
    entrada_valida,
    resposta_agente,
)

ARTIGOS = carregar_artigos()
POR_ID = {artigo.id: artigo for artigo in ARTIGOS}
AGORA = datetime(2026, 11, 13, 10, 0)
HOJE = date(2026, 11, 13)
BOBINA = "a bobina acabou, onde compro mais papel pra impressora?"
REQUISICAO = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
# O rascunho do agente, com uma frase inventada no meio (como a a59 da etapa 3).
RASCUNHO = (
    "A bobina é térmica, de 57 mm. Dá para transferir o saldo para outra conta. "
    "Compre no app, em Loja › Bobinas."
)
CITADA_1 = ("A bobina é térmica, de 57 mm.", "bobina de papel térmico de 57 mm de largura")
CITADA_2 = (" Compre no app, em Loja › Bobinas.", "Você compra no app, em Loja > Bobinas")


def _pedaco(texto, trecho):
    citacoes = [SimpleNamespace(cited_text=trecho)] if trecho else None
    return SimpleNamespace(type="text", text=texto, citations=citacoes)


# --- A decisão do código, frase por frase ---


def test_frase_sem_trecho_citado_sai():
    pedacos = ler_pedacos(
        [
            _pedaco(*CITADA_1),
            _pedaco(" Dá para transferir o saldo para outra conta.", None),
            _pedaco(*CITADA_2),
        ]
    )
    _, frases, _, manter, por_numero = frases_com_prova(pedacos)
    assert [frases[i] for i in sorted(manter)] == [
        "A bobina é térmica, de 57 mm.",
        "Compre no app, em Loja › Bobinas.",
    ]
    assert por_numero == []


def test_numero_fora_da_citacao_derruba_a_frase():
    # O começo é citado, mas o "em 3 dias úteis" veio de fora: os números vêm das fontes.
    pedacos = ler_pedacos(
        [
            _pedaco("O kit chega", "entrega em até 5 dias úteis"),
            _pedaco(" em 3 dias úteis.", None),
        ]
    )
    _, frases, _, manter, por_numero = frases_com_prova(pedacos)
    assert manter == set()
    assert por_numero == [0]


def test_ligacao_sem_numero_entre_citacoes_fica():
    # "Você pode" e ", e" sem citação são só ligação: a frase tem prova.
    pedacos = ler_pedacos(
        [
            _pedaco("Você pode ", None),
            _pedaco("cancelar em até 90 dias", "em até 90 dias depois de feita"),
            _pedaco(", e ", None),
            _pedaco("a taxa do mesmo dia volta.", "A taxa da venda cancelada no mesmo dia"),
        ]
    )
    _, _, _, manter, _ = frases_com_prova(pedacos)
    assert manter == {0}


def test_lista_numerada_fica_e_e_renumerada():
    conferente = ConferenteCitacoes(
        ClienteCitacoesFalso(
            ("Para trocar:\n\n1. ", None),
            ("Abra a tampa puxando a trava de cima.", "Abra a tampa da impressora"),
            ("\n2. Passe cola no papel.", None),
            ("\n3. ", None),
            ("Feche a tampa.", "feche a tampa"),
        ),
        "claude-haiku-5-5",
    )
    resultado = conferente.conferir(BOBINA, "rascunho", [POR_ID["bobina"]], {}, HOJE)
    # "Para trocar:" não tem citação e sai; a lista é renumerada sem o passo inventado.
    assert resultado.texto == "1. Abra a tampa puxando a trava de cima.\n2. Feche a tampa."
    assert resultado.removidas == ["Para trocar:", "Passe cola no papel."]
    assert resultado.citacoes == ["Abra a tampa da impressora", "feche a tampa"]


# --- O pedido à API ---


def test_pedido_leva_documentos_com_citacao_e_nada_de_formato_estrito():
    cliente = ClienteCitacoesFalso(CITADA_1)
    conferente = ConferenteCitacoes(cliente, "claude-haiku-5-5")
    consultas = {"consultar_recebimentos": {"plano": "Plano Mensal"}}
    conferente.conferir("minha <pergunta>", "rascunho <b>", [POR_ID["bobina"]], consultas, HOJE)
    pedido = cliente.chamadas[0]
    # Citações não andam junto com formato estrito: sem ferramentas e sem output_config.format.
    assert "tools" not in pedido
    assert "format" not in pedido["output_config"]
    assert "temperature" not in pedido
    assert pedido["thinking"] == {"type": "disabled"}
    assert pedido["system"][0]["text"] == PROMPT_CITACOES
    conteudo = pedido["messages"][0]["content"]
    documentos = [b for b in conteudo if b["type"] == "document"]
    assert [d["title"] for d in documentos] == [
        POR_ID["bobina"].titulo,
        "Dados da conta do lojista",
        "Data de hoje e prazos",
    ]
    assert all(d["citations"] == {"enabled": True} for d in documentos)
    assert "Plano Mensal" in documentos[1]["source"]["data"]
    assert "13/11/2026" in documentos[2]["source"]["data"]
    texto = conteudo[-1]["text"]
    # O texto de fora não consegue fechar a marcação.
    assert "‹pergunta›" in texto
    assert "rascunho ‹b›" in texto


def test_sem_consulta_nao_vai_documento_de_dados():
    cliente = ClienteCitacoesFalso(CITADA_1)
    ConferenteCitacoes(cliente, "claude-haiku-5-5").conferir(
        BOBINA, "rascunho", [POR_ID["bobina"]], {}, HOJE
    )
    titulos = [b.get("title") for b in cliente.chamadas[0]["messages"][0]["content"]]
    assert "Dados da conta do lojista" not in titulos


@pytest.mark.parametrize("motivo", ["max_tokens", "refusal"])
def test_parada_vira_erro(motivo):
    conferente = ConferenteCitacoes(
        ClienteCitacoesFalso(CITADA_1, stop_reason=motivo), "claude-haiku-5-5"
    )
    with pytest.raises(ErroConferencia):
        conferente.conferir(BOBINA, "rascunho", [POR_ID["bobina"]], {}, HOJE)


def test_reescrita_vazia_vira_erro():
    conferente = ConferenteCitacoes(ClienteCitacoesFalso(), "claude-haiku-5-5")
    with pytest.raises(ErroConferencia):
        conferente.conferir(BOBINA, "rascunho", [POR_ID["bobina"]], {}, HOJE)


# --- No atendimento ---


def montar(citacoes, agente=None):
    dados = DadosLojistas(agora=lambda: AGORA)
    triagem = ServicoTriagem(
        ClassificadorClaude(
            ClienteFalso(
                entrada_valida(
                    categoria="suporte_tecnico",
                    prioridade="media",
                    numero_pedido=None,
                    confianca=0.95,
                )
            ),
            "claude-haiku-5-5",
        )
    )
    agente = agente or ClienteAgenteFalso(("resposta", resposta_agente(resposta=RASCUNHO)))
    servico = ServicoAtendimento(
        triagem,
        Busca(ARTIGOS, limiar_bm25=1.0),
        AgenteClaude(agente, dados, "claude-haiku-5-5"),
        dados,
        conferente=ConferenteCitacoes(citacoes, "claude-haiku-5-5"),
    )
    return servico, agente


def test_sai_sem_pessoa_so_com_o_que_tem_prova_e_sem_refazer():
    citacoes = ClienteCitacoesFalso(
        CITADA_1, (" Dá para transferir o saldo para outra conta.", None), CITADA_2
    )
    servico, agente = montar(citacoes)
    resultado = servico.atender(BOBINA, Canal.CHAT, "loja-001")
    assert not resultado.precisa_pessoa
    assert resultado.resposta == "A bobina é térmica, de 57 mm. Compre no app, em Loja › Bobinas."
    assert "transferir" not in resultado.resposta
    # O corte é do código: o agente não é chamado de novo.
    assert len(agente.chamadas) == 1
    assert len(citacoes.chamadas) == 1


def test_sobrou_pouco_vai_para_uma_pessoa_com_o_que_tem_prova():
    citacoes = ClienteCitacoesFalso(
        ("A bobina é térmica.", "papel térmico"),
        (" Dá para transferir o saldo para outra conta e pedir reembolso do kit.", None),
        (" O kit sai de graça para quem compra três.", None),
    )
    servico, _ = montar(citacoes)
    resultado = servico.atender(BOBINA, Canal.CHAT, "loja-001")
    assert resultado.precisa_pessoa
    assert resultado.resposta == f"A bobina é térmica.\n\n{AVISO_PESSOA}"
    assert resultado.motivos_pessoa == [
        "conferência por citação: 2 de 3 frase(s) sem trecho citado"
    ]


def test_nada_com_prova_vira_mensagem_de_espera():
    citacoes = ClienteCitacoesFalso(("Dá para transferir o saldo.", None))
    servico, _ = montar(citacoes)
    resultado = servico.atender(BOBINA, Canal.CHAT, "loja-001")
    assert resultado.precisa_pessoa
    assert RESPOSTA_ESPERA in resultado.resposta


def test_falha_da_api_vai_para_uma_pessoa():
    erro = anthropic.APIConnectionError(request=REQUISICAO)
    servico, _ = montar(ClienteCitacoesFalso(erro=erro))
    resultado = servico.atender(BOBINA, Canal.CHAT, "loja-001")
    assert resultado.precisa_pessoa
    assert any("falhou" in m for m in resultado.motivos_pessoa)


# --- A escolha da conferência ---


def test_padrao_continua_a_conferencia_frase_a_frase():
    assert Configuracao(_env_file=None).modo_conferencia == "frases"
    assert isinstance(criar_conferente(object(), Configuracao(_env_file=None)), ConferenteClaude)


def test_modo_citacoes_escolhe_a_conferencia_por_citacao():
    config = Configuracao(_env_file=None, modo_conferencia="citacoes")
    assert isinstance(criar_conferente(object(), config), ConferenteCitacoes)
