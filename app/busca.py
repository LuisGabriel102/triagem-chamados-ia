"""A busca do atendimento: junta a busca por palavras e a por sentido e devolve os 3
artigos mais parecidos com a pergunta, ou "nada encontrado".

Passo a passo de uma busca:
1. A pergunta passa pelo mascaramento (LGPD) antes de tudo. Só o texto mascarado vira
   vetor: CPF, CNPJ, cartão, e-mail e telefone nunca vão para o Google.
2. Busca por palavras (BM25) e, se houver acesso ao Google, busca por sentido (cosseno).
3. Fusão dos dois rankings pela posição (RRF, k = 60): cada artigo soma 1 / (60 + posição)
   em cada lista. Assim não é preciso pôr a nota do BM25 e o cosseno na mesma escala.
4. Limiar: se nem o artigo mais parecido for parecido o bastante, a resposta é "nada
   encontrado". É isso que vai fazer o agente (etapa 2) dizer "não sei" e chamar uma
   pessoa. Com a busca por sentido, vale a maior similaridade; sem ela, a maior nota do BM25.
5. Se o Google falhar, a busca segue só por palavras e avisa no resultado.

Como os limiares foram escolhidos: docs/ATENDIMENTO.md.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.base_conhecimento import PASTA_BASE, Artigo, carregar_artigos
from app.busca_palavras import BuscaPalavras
from app.busca_sentido import (
    ErroSentido,
    GeradorVetores,
    IndiceVetores,
    carregar_indice_memoria,
    criar_gerador,
)
from app.config import Configuracao
from app.mascaramento import mascarar

QUANTOS_ARTIGOS = 3
K_RRF = 60
# Os limiares de "nada encontrado", gravados pela calibração. Não são segredo.
ARQUIVO_LIMIARES = PASTA_BASE / "limiares.json"
# Os marcadores do mascaramento não são palavras da pergunta: saem antes do BM25.
_MARCADOR = re.compile(r"\[(?:CPF|CNPJ|CARTAO|EMAIL|TELEFONE)\]")

Modo = Literal["hibrida", "palavras", "sentido"]
Criterio = Literal["similaridade", "nota_bm25"]

SO_PALAVRAS = "Resultado só da busca por palavras."
SEM_ACESSO = (
    "Busca por sentido desligada: falta a GEMINI_API_KEY ou o GOOGLE_CLOUD_PROJECT. " + SO_PALAVRAS
)
SEM_LIMIAR_SIMILARIDADE = (
    "O limiar da similaridade ainda não foi calibrado para este modelo (base/limiares.json): "
    "a decisão de 'nada encontrado' usou a nota do BM25."
)


@dataclass(frozen=True)
class Limiares:
    """Os limiares em uso e de onde cada um veio (para o relatório e para o log)."""

    bm25: float
    similaridade: float | None
    origem_bm25: str
    origem_similaridade: str


def ler_limiares(caminho: Path = ARQUIVO_LIMIARES) -> dict[str, Any]:
    """O conteúdo de base/limiares.json, ou {} se ele não existe ou está estragado."""
    try:
        dados = json.loads(caminho.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def escolher_limiares(
    config: Configuracao,
    modelo: str | None = None,
    dimensoes: int | None = None,
    caminho: Path = ARQUIVO_LIMIARES,
) -> Limiares:
    """A variável de ambiente, se existir, sobrescreve; senão vale base/limiares.json.

    O limiar da similaridade só vale para o modelo e as dimensões com que foi calibrado.
    """
    arquivo = ler_limiares(caminho)
    bm25 = arquivo.get("bm25") if isinstance(arquivo.get("bm25"), dict) else {}
    sentido = arquivo.get("similaridade") if isinstance(arquivo.get("similaridade"), dict) else {}

    if config.limiar_bm25 is not None:
        limiar_bm25, origem_bm25 = config.limiar_bm25, "LIMIAR_BM25 do ambiente"
    elif "limiar" in bm25:
        limiar_bm25 = float(bm25["limiar"])
        origem_bm25 = f"base/limiares.json, calibrado em {bm25.get('calibrado_em', '?')}"
    else:
        limiar_bm25, origem_bm25 = 0.0, "nenhum: base/limiares.json sem o limiar do BM25"

    limiar_sentido: float | None = None
    if config.limiar_similaridade is not None:
        limiar_sentido, origem_sentido = (
            config.limiar_similaridade,
            "LIMIAR_SIMILARIDADE do ambiente",
        )
    elif "limiar" not in sentido:
        origem_sentido = "não calibrado"
    elif sentido.get("modelo") == modelo and sentido.get("dimensoes") == dimensoes:
        limiar_sentido = float(sentido["limiar"])
        origem_sentido = (
            f"base/limiares.json ({modelo}, {dimensoes} dimensões), "
            f"calibrado em {sentido.get('calibrado_em', '?')}"
        )
    else:
        origem_sentido = (
            f"o de base/limiares.json é de outro modelo ({sentido.get('modelo')}, "
            f"{sentido.get('dimensoes')} dimensões): recalibre"
        )
    return Limiares(limiar_bm25, limiar_sentido, origem_bm25, origem_sentido)


@dataclass(frozen=True)
class Achado:
    artigo: Artigo
    nota_fusao: float
    nota_bm25: float | None  # None: o artigo não tem nenhuma palavra da pergunta
    similaridade: float | None  # None: a busca por sentido não rodou


@dataclass(frozen=True)
class ResultadoBusca:
    pergunta_mascarada: str
    modo: Modo  # o que de fato rodou (pode ser "palavras" mesmo pedindo "hibrida")
    candidatos: list[Achado]  # os mais parecidos, antes do limiar
    nada_encontrado: bool
    criterio: Criterio
    melhor_nota: float  # a nota comparada com o limiar
    limiar: float
    avisos: list[str] = field(default_factory=list)
    # Tokens que o Google cobrou para transformar a pergunta em vetor (0 sem a busca por sentido).
    tokens_embedding: int = 0

    @property
    def achados(self) -> list[Achado]:
        """O que o agente pode usar para responder: vazio quando nada foi encontrado."""
        return [] if self.nada_encontrado else self.candidatos


def fundir_rankings(*rankings: Sequence[str], k: int = K_RRF) -> list[tuple[str, float]]:
    """Fusão pela posição (RRF): cada artigo soma 1 / (k + posição) em cada ranking."""
    notas: dict[str, float] = {}
    for ranking in rankings:
        for posicao, id_artigo in enumerate(ranking, start=1):
            notas[id_artigo] = notas.get(id_artigo, 0.0) + 1 / (k + posicao)
    return sorted(notas.items(), key=lambda par: (-par[1], par[0]))


def escolher_limiar(com_resposta: Sequence[float], sem_resposta: Sequence[float]) -> float:
    """O limiar que melhor separa as perguntas com resposta das sem resposta.

    Recebe a melhor nota de cada pergunta. Testa a menor nota, os pontos do meio entre
    notas vizinhas e um ponto acima da maior. Fica o que tem a maior média entre o acerto
    das com resposta (nota >= limiar) e o das sem resposta (nota < limiar). Se vários
    empatam, fica o do meio deles.
    """
    if not com_resposta or not sem_resposta:
        raise ValueError("a calibração precisa de perguntas com e sem resposta")
    notas = sorted(set(com_resposta) | set(sem_resposta))
    candidatos = [notas[0]]
    candidatos += [(a + b) / 2 for a, b in zip(notas, notas[1:], strict=False)]
    candidatos.append(notas[-1] + 1e-6)

    def acerto(limiar: float) -> float:
        passam = sum(nota >= limiar for nota in com_resposta) / len(com_resposta)
        barradas = sum(nota < limiar for nota in sem_resposta) / len(sem_resposta)
        return (passam + barradas) / 2

    melhor = max(acerto(limiar) for limiar in candidatos)
    empatados = [limiar for limiar in candidatos if acerto(limiar) == melhor]
    return empatados[len(empatados) // 2]


class Busca:
    def __init__(
        self,
        artigos: Sequence[Artigo],
        gerador: GeradorVetores | None = None,
        indice: IndiceVetores | None = None,
        limiar_bm25: float = 0.0,
        limiar_similaridade: float | None = None,
        motivo_sem_sentido: str = SEM_ACESSO,
        quantos: int = QUANTOS_ARTIGOS,
    ) -> None:
        self._artigos = {artigo.id: artigo for artigo in artigos}
        # O título entra duas vezes: palavra do título pesa mais que palavra do corpo.
        self._palavras = BuscaPalavras(
            (a.id, f"{a.titulo}\n{a.titulo}\n{a.texto}") for a in artigos
        )
        self._gerador = gerador
        self._indice = indice
        self.limiar_bm25 = limiar_bm25
        self.limiar_similaridade = limiar_similaridade
        self._motivo_sem_sentido = motivo_sem_sentido
        self.quantos = quantos

    @property
    def sentido_disponivel(self) -> bool:
        return self._gerador is not None and self._indice is not None

    def buscar(self, pergunta: str, modo: Modo = "hibrida") -> ResultadoBusca:
        mascarada = mascarar(pergunta).texto
        notas_bm25 = self._palavras.notas(_MARCADOR.sub(" ", mascarada))
        avisos: list[str] = []

        similaridades: list[tuple[str, float]] | None = None
        tokens_embedding = 0
        if modo != "palavras":
            if self._gerador is None or self._indice is None:
                avisos.append(self._motivo_sem_sentido)
            else:
                try:
                    # Só o texto mascarado vai para o Google.
                    vetor = self._gerador.vetor_pergunta(mascarada)
                    tokens_embedding = int(getattr(vetor, "tokens", 0) or 0)
                    similaridades = self._indice.buscar(vetor)
                except ErroSentido as erro:
                    avisos.append(f"A busca por sentido falhou: {erro}. {SO_PALAVRAS}")

        ranking_bm25 = [id_artigo for id_artigo, _ in notas_bm25]
        efetivo: Modo
        if similaridades is None:
            efetivo, rankings = "palavras", [ranking_bm25]
        else:
            ranking_sentido = [id_artigo for id_artigo, _ in similaridades]
            if modo == "sentido":
                efetivo, rankings = "sentido", [ranking_sentido]
            else:
                efetivo, rankings = "hibrida", [ranking_bm25, ranking_sentido]

        criterio: Criterio
        if similaridades is not None and self.limiar_similaridade is not None:
            criterio, limiar = "similaridade", self.limiar_similaridade
            melhor = similaridades[0][1] if similaridades else 0.0
        else:
            if similaridades is not None:
                avisos.append(SEM_LIMIAR_SIMILARIDADE)
            criterio, limiar = "nota_bm25", self.limiar_bm25
            melhor = notas_bm25[0][1] if notas_bm25 else 0.0

        bm25 = dict(notas_bm25)
        sentido = dict(similaridades or [])
        candidatos = [
            Achado(self._artigos[id_artigo], nota, bm25.get(id_artigo), sentido.get(id_artigo))
            for id_artigo, nota in fundir_rankings(*rankings)[: self.quantos]
        ]
        return ResultadoBusca(
            pergunta_mascarada=mascarada,
            modo=efetivo,
            candidatos=candidatos,
            nada_encontrado=not candidatos or melhor < limiar,
            criterio=criterio,
            melhor_nota=melhor,
            limiar=limiar,
            avisos=avisos,
            tokens_embedding=tokens_embedding,
        )


def criar_busca(config: Configuracao, artigos: Sequence[Artigo] | None = None) -> Busca:
    """Monta a busca com a base, o gerador do Google (se houver acesso) e o índice."""
    artigos = list(artigos) if artigos is not None else carregar_artigos()
    gerador = criar_gerador(config)
    indice = None
    motivo = SEM_ACESSO
    if gerador is not None:
        try:
            indice = carregar_indice_memoria(artigos, gerador.modelo, gerador.dimensoes)
        except ErroSentido as erro:
            motivo = f"Busca por sentido desligada: {erro}. {SO_PALAVRAS}"
    limiares = escolher_limiares(
        config,
        gerador.modelo if gerador else None,
        gerador.dimensoes if gerador else None,
    )
    return Busca(
        artigos,
        gerador=gerador,
        indice=indice,
        limiar_bm25=limiares.bm25,
        limiar_similaridade=limiares.similaridade,
        motivo_sem_sentido=motivo,
    )
