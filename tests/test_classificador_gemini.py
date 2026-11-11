from types import SimpleNamespace

import httpx2
import pytest
from google.auth.exceptions import DefaultCredentialsError
from google.genai import errors as erros_google
from google.genai import types

from app.classificador import (
    FERRAMENTA_TRIAGEM,
    PROMPT_SISTEMA,
    PROMPT_SISTEMA_GEMINI,
    ErroClassificador,
    Uso,
    criar_classificador,
)
from app.classificador_gemini import ESQUEMA_GEMINI, ClassificadorGemini, ler_uso_gemini
from app.config import Configuracao
from app.esquemas import Categoria, Origem, Prioridade, Sentimento, Triagem
from app.servico import ServicoTriagem
from tests.falsos import ClienteGeminiFalso, entrada_valida

MODELO = "gemini-3.5-flash-lite"


def classificar(cliente: ClienteGeminiFalso, texto: str = "Fui cobrado duas vezes.", **ajustes):
    return ClassificadorGemini(cliente, modelo=MODELO, **ajustes).classificar(texto, "email")


def test_devolve_a_triagem_e_os_tokens_gastos():
    resultado = classificar(ClienteGeminiFalso())
    assert resultado.triagem.categoria is Categoria.FINANCEIRO
    assert resultado.triagem.numero_pedido == "458812"
    # O raciocínio é cobrado como saída: 250 da resposta + 120 do raciocínio.
    assert resultado.uso == Uso(tokens_entrada=1500, tokens_saida=370)
    assert resultado.modelo == MODELO


def test_tokens_do_cache_saem_da_entrada():
    uso = SimpleNamespace(
        prompt_token_count=1500,
        cached_content_token_count=1300,
        candidates_token_count=200,
        thoughts_token_count=None,
    )
    assert ler_uso_gemini(uso) == Uso(
        tokens_entrada=200, tokens_saida=200, tokens_cache_leitura=1300
    )


def test_sem_contagem_de_tokens_fica_zero():
    assert ler_uso_gemini(None) == Uso()


def test_pedido_vai_com_esquema_raciocinio_baixo_e_sem_temperatura():
    cliente = ClienteGeminiFalso()
    classificar(cliente, "Fui cobrado duas vezes.")
    pedido = cliente.chamadas[0]
    assert pedido["model"] == MODELO
    config = pedido["config"]
    assert config.system_instruction == PROMPT_SISTEMA_GEMINI
    assert config.response_mime_type == "application/json"
    assert config.response_schema is ESQUEMA_GEMINI
    assert config.thinking_config.thinking_level is types.ThinkingLevel.LOW
    assert config.temperature is None
    assert "<chamado>\nFui cobrado duas vezes.\n</chamado>" in pedido["contents"]


def test_nivel_de_raciocinio_vem_da_configuracao():
    cliente = ClienteGeminiFalso()
    classificar(cliente, raciocinio="high")
    nivel = cliente.chamadas[0]["config"].thinking_config.thinking_level
    assert nivel is types.ThinkingLevel.HIGH


def test_esquema_sai_da_mesma_fonte_da_ferramenta_do_claude():
    formato = FERRAMENTA_TRIAGEM["input_schema"]
    assert list(ESQUEMA_GEMINI.properties) == list(formato["properties"])
    # A justificativa vem primeiro: o modelo explica antes de decidir.
    assert ESQUEMA_GEMINI.property_ordering == list(formato["properties"])
    assert ESQUEMA_GEMINI.property_ordering[0] == "justificativa"
    assert set(ESQUEMA_GEMINI.required) == set(Triagem.model_fields)
    campos = ESQUEMA_GEMINI.properties
    assert campos["numero_pedido"].nullable is True
    assert campos["resumo"].nullable is None
    assert campos["categoria"].enum == [c.value for c in Categoria]
    assert campos["prioridade"].enum == [p.value for p in Prioridade]
    assert campos["sentimento"].enum == [s.value for s in Sentimento]
    assert campos["confianca"].type is types.Type.NUMBER


def test_prompt_do_gemini_tem_as_mesmas_regras_do_claude():
    frase_claude = "registre a triagem com a ferramenta registrar_triagem."
    frase_gemini = "responda só com a triagem, no formato JSON pedido."
    assert frase_claude in PROMPT_SISTEMA
    assert PROMPT_SISTEMA.replace(frase_claude, frase_gemini) == PROMPT_SISTEMA_GEMINI
    assert "ferramenta" not in PROMPT_SISTEMA_GEMINI


def test_resposta_cortada_e_recusada_e_guarda_os_tokens():
    with pytest.raises(ErroClassificador, match="cortada") as erro:
        classificar(ClienteGeminiFalso(motivo=types.FinishReason.MAX_TOKENS))
    assert erro.value.uso.tokens_saida == 370
    assert erro.value.modelo == MODELO


@pytest.mark.parametrize("motivo", [types.FinishReason.SAFETY, types.FinishReason.OTHER, None])
def test_parada_sem_resposta_e_recusada(motivo):
    with pytest.raises(ErroClassificador, match="parou sem responder"):
        classificar(ClienteGeminiFalso(motivo=motivo))


def test_json_invalido_e_recusado_e_guarda_os_tokens():
    with pytest.raises(ErroClassificador, match="JSON válido") as erro:
        classificar(ClienteGeminiFalso(texto="{categoria: financeiro"))
    assert erro.value.uso.tokens_entrada == 1500


@pytest.mark.parametrize(
    "alteracao",
    [{"categoria": "vendas"}, {"prioridade": "altissima"}, {"sentimento": None}],
)
def test_campo_fora_do_formato_e_recusado(alteracao):
    with pytest.raises(ErroClassificador, match="fora do formato"):
        classificar(ClienteGeminiFalso(entrada_valida(**alteracao)))


@pytest.mark.parametrize(
    "erro",
    [
        erros_google.ClientError(
            429, {"error": {"message": "limite", "status": "RESOURCE_EXHAUSTED"}}
        ),
        erros_google.ServerError(
            503, {"error": {"message": "fora do ar", "status": "UNAVAILABLE"}}
        ),
        httpx2.ConnectError("sem rede"),
    ],
)
def test_falha_da_api_vira_erro_do_classificador_sem_tokens(erro):
    with pytest.raises(ErroClassificador, match="falha na API do Google") as capturado:
        classificar(ClienteGeminiFalso(erro=erro))
    assert capturado.value.uso == Uso()


def test_codigo_do_erro_aparece_na_mensagem():
    erro = erros_google.ClientError(404, {"error": {"message": "x", "status": "NOT_FOUND"}})
    with pytest.raises(ErroClassificador, match="ClientError 404"):
        classificar(ClienteGeminiFalso(erro=erro))


def test_sem_login_no_google_cloud_diz_o_que_fazer():
    with pytest.raises(ErroClassificador, match="gcloud auth application-default login"):
        classificar(ClienteGeminiFalso(erro=DefaultCredentialsError("sem credenciais")))


def test_o_claude_continua_sendo_o_padrao():
    config = Configuracao(_env_file=None, anthropic_api_key=None)
    assert config.provedor_ia == "anthropic"
    assert criar_classificador(config) is None


def test_gemini_sem_projeto_fica_desligado():
    config = Configuracao(_env_file=None, provedor_ia="gemini", google_cloud_project="  ")
    assert criar_classificador(config) is None


def test_gemini_com_projeto_monta_o_cliente_do_vertex(monkeypatch):
    recebido: dict = {}

    def cliente(**kwargs):
        recebido.update(kwargs)
        return ClienteGeminiFalso()

    monkeypatch.setattr("app.classificador_gemini.genai.Client", cliente)
    config = Configuracao(
        _env_file=None,
        provedor_ia="gemini",
        google_cloud_project="meu-projeto",
        modelo_gemini="gemini-3.8-flash",
        raciocinio_gemini="medium",
        timeout_llm_s=15,
    )
    classificador = criar_classificador(config)
    assert isinstance(classificador, ClassificadorGemini)
    assert classificador.modelo == "gemini-3.8-flash"
    assert recebido["enterprise"] is True
    assert recebido["project"] == "meu-projeto"
    assert recebido["location"] == "global"
    assert recebido["http_options"].timeout == 15000
    assert recebido["http_options"].retry_options.attempts == 3
    resultado = classificador.classificar("Quero cancelar.", "chat")
    assert resultado.modelo == "gemini-3.8-flash"


def test_servico_confere_a_resposta_do_gemini_como_a_do_claude():
    # O Gemini "inventa" um número de pedido que não está no texto: o serviço descarta.
    cliente = ClienteGeminiFalso(entrada_valida(numero_pedido="999999"))
    servico = ServicoTriagem(
        ClassificadorGemini(cliente, MODELO),
        preco_entrada=0.30,
        preco_saida=2.50,
        cache_leitura=0.10,
        cache_escrita=0.0,
    )
    resultado = servico.triar("Fui cobrado duas vezes no cartão.")
    assert resultado.origem is Origem.IA
    assert resultado.modelo == MODELO
    assert resultado.triagem.numero_pedido is None
    assert any("número de pedido descartado" in m for m in resultado.motivos_revisao)
    # 1500 tokens de entrada a US$ 0,30 e 370 de saída a US$ 2,50, por milhão.
    assert resultado.custo_usd == pytest.approx((1500 * 0.30 + 370 * 2.50) / 1_000_000)


def test_gemini_fora_do_ar_cai_no_plano_b():
    cliente = ClienteGeminiFalso(erro=httpx2.ConnectError("sem rede"))
    servico = ServicoTriagem(ClassificadorGemini(cliente, MODELO))
    resultado = servico.triar("O sistema caiu e não consigo vender nada!")
    assert resultado.origem is Origem.REGRAS
    assert resultado.revisao_humana
    assert resultado.custo_usd == 0.0


def test_raciocinio_padrao_nao_manda_o_nivel():
    cliente = ClienteGeminiFalso()
    classificar(cliente, raciocinio="padrao")
    assert cliente.chamadas[0]["config"].thinking_config is None


def test_detalhe_do_erro_vai_para_o_log_e_nao_para_a_mensagem(caplog):
    erro = erros_google.ClientError(
        400, {"error": {"message": "nível de raciocínio não aceito", "status": "INVALID_ARGUMENT"}}
    )
    with pytest.raises(ErroClassificador) as capturado:
        classificar(ClienteGeminiFalso(erro=erro))
    assert "nível de raciocínio não aceito" in caplog.text
    assert "nível de raciocínio" not in str(capturado.value)
