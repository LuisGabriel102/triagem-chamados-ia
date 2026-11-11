"""Dublês dos testes. Nenhum teste chama a API real da Anthropic nem a do Google."""

import json
from types import SimpleNamespace
from typing import Any

import httpx
from google.genai import types

from app.classificador import NOME_FERRAMENTA

REQUISICAO_FALSA = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def entrada_valida(**alteracoes: Any) -> dict[str, Any]:
    """Uma triagem válida, do jeito que a IA devolve pela ferramenta."""
    dados: dict[str, Any] = {
        "justificativa": "Cobrança duplicada já lançada na fatura do cliente.",
        "categoria": "financeiro",
        "prioridade": "alta",
        "sentimento": "neutro",
        "resumo": "Cliente cobrado duas vezes pelo mesmo pedido.",
        "numero_pedido": "458812",
        "resposta_sugerida": "Olá! Vamos verificar a cobrança e retornamos por este canal.",
        "confianca": 0.93,
    }
    dados.update(alteracoes)
    return dados


class ClienteFalso:
    """Imita o cliente da Anthropic: devolve respostas prontas e guarda o que recebeu.

    Com várias entradas, cada chamada usa a próxima (a última se repete).
    """

    def __init__(
        self,
        *entradas: dict[str, Any],
        erro: Exception | None = None,
        conteudo: list[Any] | None = None,
        uso: Any = None,
        stop_reason: str = "tool_use",
    ) -> None:
        self.chamadas: list[dict[str, Any]] = []
        self.messages = self
        self._entradas = list(entradas) or [entrada_valida()]
        self._erro = erro
        self._conteudo = conteudo
        self._uso = uso or SimpleNamespace(
            input_tokens=1000,
            output_tokens=200,
            cache_creation_input_tokens=None,
            cache_read_input_tokens=None,
        )
        self._stop_reason = stop_reason

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.chamadas.append(kwargs)
        if self._erro is not None:
            raise self._erro
        entrada = self._entradas[min(len(self.chamadas), len(self._entradas)) - 1]
        conteudo = self._conteudo
        if conteudo is None:
            conteudo = [
                SimpleNamespace(
                    type="tool_use", id="toolu_teste", name=NOME_FERRAMENTA, input=entrada
                )
            ]
        return SimpleNamespace(
            content=conteudo,
            usage=self._uso,
            model="claude-haiku-5-5",
            stop_reason=self._stop_reason,
        )


class ClienteGeminiFalso:
    """Imita o cliente do Google (google-genai): `cliente.models.generate_content(...)`.

    Devolve a triagem em JSON, como o Gemini faz com o esquema. Guarda o que recebeu.
    Com várias entradas, cada chamada usa a próxima (a última se repete).
    """

    def __init__(
        self,
        *entradas: dict[str, Any],
        erro: Exception | None = None,
        texto: str | None = None,
        uso: Any = None,
        motivo: Any = types.FinishReason.STOP,
        modelo: str | None = None,
    ) -> None:
        self.chamadas: list[dict[str, Any]] = []
        self.models = self
        self._entradas = list(entradas) or [entrada_valida()]
        self._erro = erro
        self._texto = texto
        self._uso = uso or SimpleNamespace(
            prompt_token_count=1500,
            cached_content_token_count=None,
            candidates_token_count=250,
            thoughts_token_count=120,
        )
        self._motivo = motivo
        self._modelo = modelo

    def generate_content(self, **kwargs: Any) -> SimpleNamespace:
        self.chamadas.append(kwargs)
        if self._erro is not None:
            raise self._erro
        entrada = self._entradas[min(len(self.chamadas), len(self._entradas)) - 1]
        texto = self._texto if self._texto is not None else json.dumps(entrada, ensure_ascii=False)
        return SimpleNamespace(
            text=texto,
            candidates=[SimpleNamespace(finish_reason=self._motivo)],
            usage_metadata=self._uso,
            model_version=self._modelo or kwargs["model"],
        )
