"""Busca por sentido: a pergunta e os artigos viram vetores (embeddings do Gemini), e a
nota de cada artigo é a similaridade de cosseno com a pergunta.

Modelo: gemini-embedding-2, o indicado para texto na documentação do Google
(aistudio.google.com/docs/embeddings, conferida em 13/11/2026). Ele não aceita o campo
task_type: o tipo de tarefa vai escrito no próprio texto, do jeito que a documentação manda.
- pergunta: "task: search result | query: <pergunta>"
- artigo:   "title: <título> | text: <texto>"
O gemini-embedding-001, ainda disponível, recebe o tipo no task_type (RETRIEVAL_QUERY e
RETRIEVAL_DOCUMENT). Os dois aceitam 768 dimensões.

Funciona de dois jeitos: com a chave do Google AI Studio (GEMINI_API_KEY) ou pelo Vertex AI
(GOOGLE_CLOUD_PROJECT, com o login do gcloud no computador).

Cada artigo é um trecho só, porque os artigos são curtos. Os vetores dos artigos ficam em
base/indice.json, gerado por scripts/indexar_base.py, que só refaz o artigo que mudou. A
pergunta vira vetor na hora.

Com 30 artigos, a conta roda na memória (IndiceMemoria). O pgvector entra na etapa 4 com a
mesma interface (IndiceVetores).
"""

import hashlib
import json
import logging
import math
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

# O SDK do Google faz as chamadas com o httpx2: queda de rede chega como erro dele.
import httpx2
from google import genai
from google.auth.exceptions import GoogleAuthError
from google.genai import errors as erros_google
from google.genai import types

from app.base_conhecimento import PASTA_BASE, Artigo
from app.config import Configuracao

log = logging.getLogger(__name__)

MODELO_PADRAO = "gemini-embedding-2"
DIMENSOES_PADRAO = 768
ARQUIVO_INDICE = PASTA_BASE / "indice.json"
# Muda quando o jeito de montar o texto enviado muda: força refazer todos os vetores.
VERSAO_FORMATO = 1
COMANDO_INDEXAR = "python scripts/indexar_base.py"


class ErroSentido(Exception):
    """A busca por sentido não pôde rodar: falha do Google, índice ausente ou velho."""


class Vetor(list[float]):
    """Um vetor que também diz quantos tokens o Google cobrou para gerá-lo (0 se não disse).

    É uma lista comum: quem não liga para os tokens nem percebe a diferença.
    """

    tokens: int = 0


class GeradorVetores(Protocol):
    """Quem transforma texto em vetor. Nos testes, um gerador falso faz esse papel."""

    modelo: str
    dimensoes: int

    def vetor_documento(self, titulo: str, texto: str) -> list[float]: ...

    def vetor_pergunta(self, texto: str) -> list[float]: ...


class IndiceVetores(Protocol):
    """Onde ficam os vetores dos artigos. Hoje, na memória; na etapa 4, no pgvector."""

    def buscar(self, vetor: Sequence[float], quantos: int | None = None) -> list[tuple[str, float]]:
        """Os artigos mais parecidos com o vetor, da maior similaridade para a menor."""
        ...


def normalizar_vetor(vetor: Sequence[float]) -> list[float]:
    """Deixa o vetor com tamanho 1: assim o produto escalar já é o cosseno."""
    tamanho = math.sqrt(sum(x * x for x in vetor))
    if tamanho == 0:
        return [0.0] * len(vetor)
    return [x / tamanho for x in vetor]


class IndiceMemoria:
    """Similaridade de cosseno na memória. Com 30 artigos, é instantâneo."""

    def __init__(self, vetores: Mapping[str, Sequence[float]]) -> None:
        self._vetores = {id_artigo: normalizar_vetor(v) for id_artigo, v in vetores.items()}

    def buscar(self, vetor: Sequence[float], quantos: int | None = None) -> list[tuple[str, float]]:
        consulta = normalizar_vetor(vetor)
        notas = [
            (id_artigo, sum(a * b for a, b in zip(consulta, guardado, strict=True)))
            for id_artigo, guardado in self._vetores.items()
        ]
        notas.sort(key=lambda par: (-par[1], par[0]))
        return notas[:quantos] if quantos is not None else notas


def usa_prefixo_de_tarefa(modelo: str) -> bool:
    """O gemini-embedding-2 recebe a tarefa no texto; os anteriores, no task_type."""
    return modelo.startswith("gemini-embedding-2")


class GeradorGemini:
    """Embeddings do Gemini pelo SDK google-genai. Um texto por chamada, um vetor por texto."""

    def __init__(
        self, cliente: Any, modelo: str = MODELO_PADRAO, dimensoes: int = DIMENSOES_PADRAO
    ) -> None:
        self._cliente = cliente
        self.modelo = modelo
        self.dimensoes = dimensoes

    def vetor_documento(self, titulo: str, texto: str) -> list[float]:
        if usa_prefixo_de_tarefa(self.modelo):
            return self._pedir(
                f"title: {titulo} | text: {texto}",
                types.EmbedContentConfig(output_dimensionality=self.dimensoes),
            )
        return self._pedir(
            texto,
            types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT", title=titulo, output_dimensionality=self.dimensoes
            ),
        )

    def vetor_pergunta(self, texto: str) -> list[float]:
        if usa_prefixo_de_tarefa(self.modelo):
            return self._pedir(
                f"task: search result | query: {texto}",
                types.EmbedContentConfig(output_dimensionality=self.dimensoes),
            )
        return self._pedir(
            texto,
            types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY", output_dimensionality=self.dimensoes
            ),
        )

    def _pedir(self, conteudo: str, configuracao: types.EmbedContentConfig) -> list[float]:
        try:
            resposta = self._cliente.models.embed_content(
                model=self.modelo, contents=conteudo, config=configuracao
            )
        except GoogleAuthError as erro:
            raise ErroSentido(
                "sem login no Google Cloud (rode: gcloud auth application-default login)"
            ) from erro
        except (erros_google.APIError, httpx2.HTTPError) as erro:
            # O texto do Google vai só para o log. No resultado fica o tipo e o código.
            log.warning("Erro na chamada de embeddings do Google: %s", erro)
            codigo = getattr(erro, "code", None)
            detalhe = f"{type(erro).__name__} {codigo}" if codigo else type(erro).__name__
            raise ErroSentido(f"falha na API do Google ({detalhe})") from erro
        except Exception as erro:
            # Erro que não era esperado (do SDK ou da rede). A busca não pode parar por isso:
            # segue só por palavras, e o detalhe completo fica no log.
            log.exception("Erro inesperado na chamada de embeddings do Google")
            raise ErroSentido(
                f"erro inesperado na chamada ao Google ({type(erro).__name__})"
            ) from erro
        try:
            valores = [float(x) for x in resposta.embeddings[0].values]
        except (AttributeError, IndexError, TypeError) as erro:
            raise ErroSentido("o Google devolveu uma resposta sem vetor") from erro
        if len(valores) != self.dimensoes:
            raise ErroSentido(f"o Google devolveu {len(valores)} dimensões, e não {self.dimensoes}")
        # O gemini-embedding-001 com menos de 3072 dimensões vem sem normalizar.
        vetor = Vetor(normalizar_vetor(valores))
        uso = getattr(resposta, "usage_metadata", None)
        vetor.tokens = int(getattr(uso, "prompt_token_count", 0) or 0)
        return vetor


def _chave_gemini(config: Configuracao) -> str:
    return config.gemini_api_key.get_secret_value().strip() if config.gemini_api_key else ""


def acesso_ao_google(config: Configuracao) -> str | None:
    """Como os embeddings vão chegar ao Google, ou None se não há como."""
    if _chave_gemini(config):
        return "chave do Google AI Studio"
    if config.google_cloud_project.strip():
        return "Vertex AI"
    return None


def criar_gerador(config: Configuracao) -> GeradorGemini | None:
    """Monta o gerador do Gemini: pela chave do AI Studio ou, sem ela, pelo Vertex AI.

    Sem nenhum dos dois, devolve None, e a busca segue só por palavras.
    """
    chave = _chave_gemini(config)
    projeto = config.google_cloud_project.strip()
    if not chave and not projeto:
        return None
    opcoes = types.HttpOptions(
        timeout=int(config.timeout_llm_s * 1000),
        # Até 2 tentativas, só em erro passageiro: a busca está no caminho da conversa.
        retry_options=types.HttpRetryOptions(attempts=2),
    )
    if chave:
        cliente = genai.Client(enterprise=False, api_key=chave, http_options=opcoes)
    else:
        cliente = genai.Client(
            enterprise=True,
            project=projeto,
            location=config.google_cloud_location,
            http_options=opcoes,
        )
    return GeradorGemini(
        cliente, modelo=config.modelo_embedding, dimensoes=config.dimensoes_embedding
    )


# --- Cache dos vetores dos artigos (base/indice.json) ---


def impressao_digital(artigo: Artigo, modelo: str, dimensoes: int) -> str:
    """Muda se o título, o texto, o modelo ou as dimensões mudarem."""
    conteudo = json.dumps(
        [VERSAO_FORMATO, modelo, dimensoes, artigo.titulo, artigo.texto], ensure_ascii=False
    )
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


@dataclass
class RelatorioIndice:
    refeitos: list[str] = field(default_factory=list)
    aproveitados: list[str] = field(default_factory=list)
    removidos: list[str] = field(default_factory=list)


def ler_indice(caminho: Path = ARQUIVO_INDICE) -> dict[str, Any]:
    """O conteúdo do índice, ou {} se ele não existe ou está estragado."""
    try:
        dados = json.loads(caminho.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar_indice(caminho: Path, modelo: str, dimensoes: int, artigos: dict) -> None:
    dados = {"versao": VERSAO_FORMATO, "modelo": modelo, "dimensoes": dimensoes}
    dados["artigos"] = dict(sorted(artigos.items()))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(temporario, caminho)


def atualizar_indice(
    artigos: Iterable[Artigo], gerador: GeradorVetores, caminho: Path = ARQUIVO_INDICE
) -> RelatorioIndice:
    """Gera os vetores que faltam e grava o índice. Só refaz o artigo que mudou.

    Se o Google falhar no meio, o que já foi feito fica gravado e não é pago de novo.
    """
    artigos = list(artigos)
    guardados = ler_indice(caminho).get("artigos", {})
    if not isinstance(guardados, dict):
        guardados = {}
    ids = {artigo.id for artigo in artigos}
    relatorio = RelatorioIndice(removidos=sorted(set(guardados) - ids))
    novos: dict[str, dict] = {}
    try:
        for artigo in artigos:
            digital = impressao_digital(artigo, gerador.modelo, gerador.dimensoes)
            guardado = guardados.get(artigo.id)
            if isinstance(guardado, dict) and guardado.get("impressao") == digital:
                novos[artigo.id] = guardado
                relatorio.aproveitados.append(artigo.id)
                continue
            vetor = gerador.vetor_documento(artigo.titulo, artigo.texto)
            novos[artigo.id] = {"impressao": digital, "vetor": [round(x, 7) for x in vetor]}
            relatorio.refeitos.append(artigo.id)
    finally:
        # Na falha, os artigos que não chegaram a ser vistos ficam como estavam.
        restantes = {k: v for k, v in guardados.items() if k in ids and k not in novos}
        _gravar_indice(caminho, gerador.modelo, gerador.dimensoes, {**restantes, **novos})
    return relatorio


def carregar_indice_memoria(
    artigos: Iterable[Artigo], modelo: str, dimensoes: int, caminho: Path = ARQUIVO_INDICE
) -> IndiceMemoria:
    """Os vetores do índice, conferidos contra os artigos de agora.

    Índice ausente ou velho dá ErroSentido: a busca segue só por palavras e avisa.
    """
    guardados = ler_indice(caminho).get("artigos")
    if not isinstance(guardados, dict):
        raise ErroSentido(f"o índice dos artigos não existe (rode: {COMANDO_INDEXAR})")
    vetores = {}
    desatualizados = []
    for artigo in artigos:
        guardado = guardados.get(artigo.id)
        if (
            not isinstance(guardado, dict)
            or guardado.get("impressao") != impressao_digital(artigo, modelo, dimensoes)
            or len(guardado.get("vetor", [])) != dimensoes
        ):
            desatualizados.append(artigo.id)
            continue
        vetores[artigo.id] = guardado["vetor"]
    if desatualizados:
        raise ErroSentido(
            f"o índice está desatualizado em {len(desatualizados)} artigo(s) "
            f"(rode: {COMANDO_INDEXAR})"
        )
    return IndiceMemoria(vetores)
