"""Conserto 1: a descrição do negócio é um parâmetro da triagem; o padrão é o de antes."""

import hashlib

from app.atendimento import criar_atendimento
from app.base_conhecimento import descricao_do_negocio
from app.classificador import (
    NEGOCIO_PADRAO,
    PROMPT_SISTEMA,
    PROMPT_SISTEMA_GEMINI,
    ClassificadorClaude,
    montar_prompt_sistema,
)
from app.classificador_gemini import ClassificadorGemini
from app.config import Configuracao
from tests.falsos import ClienteFalso, ClienteGeminiFalso

# A impressão digital dos prompts de antes do conserto (13/11/2026). Se mudar, a triagem de
# /chamados e a avaliação dos 40 chamados deixam de comparar com os números de 04/11.
PROMPT_CLAUDE_ANTIGO = "c5f7b03aba3fc6e3b7f53d215ee767c174de5d198bcb5d34e4db1d463c7836cc"
PROMPT_GEMINI_ANTIGO = "039c136bfb40c94d3eba0ad26d6a0153cf8f0168cab706d078bc36fbc52a6ef3"


def _digital(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def test_o_prompt_padrao_e_o_mesmo_de_antes():
    assert _digital(PROMPT_SISTEMA) == PROMPT_CLAUDE_ANTIGO
    assert _digital(PROMPT_SISTEMA_GEMINI) == PROMPT_GEMINI_ANTIGO
    assert montar_prompt_sistema() == PROMPT_SISTEMA
    assert NEGOCIO_PADRAO in PROMPT_SISTEMA


def test_descricao_da_tapiri_vem_do_empresa_md():
    descricao = descricao_do_negocio()
    assert descricao.startswith("A Tapiri vende maquininhas de cartão")
    assert "Plano Na Hora" in descricao and "Pix" in descricao
    assert "**" not in descricao
    assert "inventad" not in descricao


def test_classificador_claude_manda_o_negocio_escolhido():
    cliente = ClienteFalso()
    ClassificadorClaude(cliente, "claude-haiku-5-5", negocio=descricao_do_negocio()).classificar(
        "A maquininha não liga.", "chat"
    )
    prompt = cliente.chamadas[0]["system"][0]["text"]
    assert "A Tapiri vende maquininhas" in prompt
    assert NEGOCIO_PADRAO not in prompt
    # As regras de categoria e prioridade são as mesmas.
    assert prompt.endswith(PROMPT_SISTEMA.split("registrar_triagem.\n", 1)[1])


def test_classificador_gemini_manda_o_negocio_escolhido():
    cliente = ClienteGeminiFalso()
    ClassificadorGemini(cliente, "gemini-3.5-flash-lite", negocio="Vende bicicletas.").classificar(
        "A corrente quebrou.", "chat"
    )
    instrucao = cliente.chamadas[0]["config"].system_instruction
    assert "Vende bicicletas. Leia o chamado e responda só com a triagem" in instrucao


def test_sem_negocio_o_classificador_usa_o_padrao():
    cliente = ClienteFalso()
    ClassificadorClaude(cliente, "claude-haiku-5-5").classificar("oi", "chat")
    assert cliente.chamadas[0]["system"][0]["text"] == PROMPT_SISTEMA


def test_o_atendimento_tria_com_o_negocio_da_tapiri():
    # A chave é falsa: montar o cliente da Anthropic não chama a rede.
    config = Configuracao(_env_file=None, anthropic_api_key="chave-falsa", gemini_api_key=None)
    atendimento = criar_atendimento(config)
    prompt = atendimento._triagem._classificador.prompt_sistema
    assert "A Tapiri vende maquininhas" in prompt
    assert NEGOCIO_PADRAO not in prompt
