"""Dublês dos testes. Nenhum teste chama a API real da Anthropic nem a do Google."""

import copy
import hashlib
import json
from types import SimpleNamespace
from typing import Any

import httpx
from google.genai import types

from app.busca_palavras import tokenizar
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


class ClienteEmbeddingFalso:
    """Imita o cliente do Google nos embeddings: `cliente.models.embed_content(...)`.

    Devolve um vetor fixo do tamanho pedido e guarda o que recebeu.
    """

    def __init__(self, erro: Exception | None = None, dimensoes: int | None = None) -> None:
        self.chamadas: list[dict[str, Any]] = []
        self.models = self
        self._erro = erro
        self._dimensoes = dimensoes

    def embed_content(self, **kwargs: Any) -> SimpleNamespace:
        self.chamadas.append(kwargs)
        if self._erro is not None:
            raise self._erro
        tamanho = self._dimensoes or kwargs["config"].output_dimensionality
        valores = [3.0, 4.0] + [0.0] * (tamanho - 2)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=valores)])


class GeradorVetoresFalso:
    """Gera vetores sem chamar o Google: cada palavra da pergunta cai numa posição fixa.

    Textos com as mesmas palavras ficam parecidos, como num embedding de verdade (só que
    sem entender sinônimo). Guarda tudo o que recebeu, para os testes conferirem.
    """

    def __init__(
        self, modelo: str = "modelo-falso", dimensoes: int = 1024, erro: Exception | None = None
    ) -> None:
        self.modelo = modelo
        self.dimensoes = dimensoes
        self.documentos: list[str] = []
        self.perguntas: list[str] = []
        self._erro = erro

    def _vetor(self, texto: str) -> list[float]:
        vetor = [0.0] * self.dimensoes
        for palavra in tokenizar(texto):
            posicao = int(hashlib.md5(palavra.encode("utf-8")).hexdigest(), 16) % self.dimensoes
            vetor[posicao] += 1.0
        return vetor

    def vetor_documento(self, titulo: str, texto: str) -> list[float]:
        self.documentos.append(titulo)
        if self._erro is not None:
            raise self._erro
        return self._vetor(f"{titulo} {texto}")

    def vetor_pergunta(self, texto: str) -> list[float]:
        self.perguntas.append(texto)
        if self._erro is not None:
            raise self._erro
        return self._vetor(texto)


def resposta_agente(**alteracoes: Any) -> dict[str, Any]:
    """Uma resposta válida do agente, do jeito que a IA devolve por responder_lojista."""
    dados: dict[str, Any] = {
        "resposta": "A bobina térmica de 57 mm se compra no app, em Loja › Bobinas.",
        "artigos_usados": ["bobina"],
        "precisa_pessoa": False,
        "motivo": None,
        "confianca": 0.92,
    }
    dados.update(alteracoes)
    return dados


class ClienteAgenteFalso:
    """Imita o cliente da Anthropic no agente. Cada chamada devolve a próxima jogada:
    ("consulta", "consultar_recebimentos") ou ("resposta", {...}). A última se repete.

    Guarda uma cópia de cada pedido, para os testes conferirem o que a IA recebeu.
    """

    def __init__(
        self,
        *jogadas: tuple[str, Any],
        erro: Exception | None = None,
        stop_reason: str = "tool_use",
    ) -> None:
        self.chamadas: list[dict[str, Any]] = []
        self.messages = self
        self._jogadas = list(jogadas) or [("resposta", resposta_agente())]
        self._erro = erro
        self._stop_reason = stop_reason

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.chamadas.append(copy.deepcopy(kwargs))
        if self._erro is not None:
            raise self._erro
        tipo, valor = self._jogadas[min(len(self.chamadas), len(self._jogadas)) - 1]
        if tipo == "consulta":
            bloco = SimpleNamespace(
                type="tool_use", id=f"toolu_{len(self.chamadas)}", name=valor, input={}
            )
        else:
            bloco = SimpleNamespace(
                type="tool_use",
                id=f"toolu_{len(self.chamadas)}",
                name="responder_lojista",
                input=valor,
            )
        return SimpleNamespace(
            content=[bloco],
            usage=SimpleNamespace(
                input_tokens=900,
                output_tokens=120,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=1100,
            ),
            model="claude-haiku-5-5",
            stop_reason=self._stop_reason,
        )

    def todo_o_texto_enviado(self) -> str:
        """Tudo o que a IA leu em todas as chamadas, para procurar dado que não devia estar."""
        return json.dumps(self.chamadas, ensure_ascii=False, default=lambda o: vars(o))
