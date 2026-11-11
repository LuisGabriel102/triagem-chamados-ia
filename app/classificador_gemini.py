"""Classificação do chamado com o Gemini, do Google, no Vertex AI.

Faz o mesmo papel do Claude (app/classificador.py): as mesmas regras no prompt, o mesmo
formato de resposta e as mesmas conferências depois, no serviço. Muda só o jeito de
garantir o formato: aqui a resposta vem em JSON, presa a um esquema (saída estruturada).

Não usa chave. O login é o do Google Cloud no computador:
    gcloud auth application-default login
"""

import json
import logging
from typing import Any

# O SDK do Google faz as chamadas com o httpx2: queda de rede chega como erro dele.
import httpx2
from google import genai
from google.auth.exceptions import GoogleAuthError
from google.genai import errors as erros_google
from google.genai import types
from pydantic import ValidationError

from app.classificador import (
    FERRAMENTA_TRIAGEM,
    PROMPT_SISTEMA_GEMINI,
    ErroClassificador,
    ResultadoIA,
    Uso,
    montar_mensagem,
)
from app.config import Configuracao
from app.esquemas import Triagem

log = logging.getLogger(__name__)

_TIPOS = {"string": types.Type.STRING, "number": types.Type.NUMBER}


def montar_esquema() -> types.Schema:
    """O formato da ferramenta do Claude, escrito do jeito que o Gemini aceita.

    Sai da mesma fonte (FERRAMENTA_TRIAGEM): mudou um, mudou o outro.
    - `["string", "null"]` vira texto com `nullable`.
    - `property_ordering` mantém a justificativa primeiro: o modelo explica antes de decidir.
    """
    formato = FERRAMENTA_TRIAGEM["input_schema"]
    propriedades: dict[str, types.Schema] = {}
    for nome, campo in formato["properties"].items():
        tipo = campo["type"]
        tipos = tipo if isinstance(tipo, list) else [tipo]
        principal = next(t for t in tipos if t != "null")
        propriedades[nome] = types.Schema(
            type=_TIPOS[principal],
            enum=campo.get("enum"),
            nullable=True if "null" in tipos else None,
            description=campo.get("description"),
        )
    return types.Schema(
        type=types.Type.OBJECT,
        properties=propriedades,
        required=list(formato["required"]),
        property_ordering=list(formato["properties"]),
    )


ESQUEMA_GEMINI = montar_esquema()


def ler_uso_gemini(uso: Any) -> Uso:
    """Converte a contagem do Gemini para o formato do serviço.

    No Gemini, os tokens do cache fazem parte dos tokens de entrada, e o raciocínio é
    cobrado como saída. No serviço, `tokens_entrada` não inclui o cache.
    """

    def inteiro(nome: str) -> int:
        return int(getattr(uso, nome, 0) or 0)

    entrada = inteiro("prompt_token_count")
    cache = min(inteiro("cached_content_token_count"), entrada)
    return Uso(
        tokens_entrada=entrada - cache,
        tokens_saida=inteiro("candidates_token_count") + inteiro("thoughts_token_count"),
        tokens_cache_leitura=cache,
    )


class ClassificadorGemini:
    def __init__(
        self, cliente: Any, modelo: str, raciocinio: str = "low", max_tokens: int = 4096
    ) -> None:
        self._cliente = cliente
        self.modelo = modelo
        # O limite de saída inclui o raciocínio; por isso é maior que o do Claude.
        self._max_tokens = max_tokens
        self._configuracao = types.GenerateContentConfig(
            system_instruction=PROMPT_SISTEMA_GEMINI,
            response_mime_type="application/json",
            response_schema=ESQUEMA_GEMINI,
            max_output_tokens=max_tokens,
            # "padrao" não manda o nível: vale o padrão do modelo.
            thinking_config=None
            if raciocinio == "padrao"
            else types.ThinkingConfig(thinking_level=types.ThinkingLevel[raciocinio.upper()]),
            # Sem temperatura: nos modelos Gemini 3, o Vertex AI ignora esse ajuste.
        )

    def classificar(self, texto: str, canal: str) -> ResultadoIA:
        try:
            resposta = self._cliente.models.generate_content(
                model=self.modelo,
                contents=montar_mensagem(texto, canal),
                config=self._configuracao,
            )
        except GoogleAuthError as erro:
            raise ErroClassificador(
                "sem login no Google Cloud (rode: gcloud auth application-default login)"
            ) from erro
        except (erros_google.APIError, httpx2.HTTPError) as erro:
            # O texto do Google vai só para o log (ajuda a achar o problema). No banco e
            # na resposta da API fica só o tipo e o código do erro.
            log.warning("Erro na chamada ao Gemini: %s", erro)
            codigo = getattr(erro, "code", None)
            detalhe = f"{type(erro).__name__} {codigo}" if codigo else type(erro).__name__
            raise ErroClassificador(f"falha na API do Google ({detalhe})") from erro

        # A partir daqui a chamada já foi cobrada: os tokens vão junto até no erro.
        uso = ler_uso_gemini(getattr(resposta, "usage_metadata", None))
        modelo = getattr(resposta, "model_version", None) or self.modelo
        candidatos = getattr(resposta, "candidates", None) or []
        motivo = getattr(candidatos[0], "finish_reason", None) if candidatos else None
        if motivo == types.FinishReason.MAX_TOKENS:
            raise ErroClassificador("resposta da IA cortada no limite de tokens", uso, modelo)
        if motivo != types.FinishReason.STOP:
            nome = getattr(motivo, "name", None) or "nenhum"
            raise ErroClassificador(f"a IA parou sem responder (motivo: {nome})", uso, modelo)
        try:
            dados = json.loads(resposta.text or "")
        except json.JSONDecodeError as erro:
            raise ErroClassificador("a IA não devolveu um JSON válido", uso, modelo) from erro
        try:
            triagem = Triagem.model_validate(dados)
        except ValidationError as erro:
            raise ErroClassificador("a IA devolveu campos fora do formato", uso, modelo) from erro

        return ResultadoIA(triagem=triagem, uso=uso, modelo=modelo)


def criar_classificador_gemini(config: Configuracao) -> ClassificadorGemini | None:
    """Monta o Gemini no Vertex AI. Sem projeto do Google Cloud, devolve None."""
    projeto = config.google_cloud_project.strip()
    if not projeto:
        return None
    cliente = genai.Client(
        enterprise=True,
        project=projeto,
        location=config.google_cloud_location,
        http_options=types.HttpOptions(
            timeout=int(config.timeout_llm_s * 1000),
            # Até 3 tentativas: a primeira e mais duas, só em erro passageiro (como 429 e 5xx).
            retry_options=types.HttpRetryOptions(attempts=3),
        ),
    )
    return ClassificadorGemini(
        cliente, modelo=config.modelo_gemini, raciocinio=config.raciocinio_gemini
    )
