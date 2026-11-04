"""Formatos de dados da API e da triagem."""

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

TAMANHO_MAXIMO_TEXTO = 4000
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class Categoria(StrEnum):
    FINANCEIRO = "financeiro"
    SUPORTE_TECNICO = "suporte_tecnico"
    COMERCIAL = "comercial"
    CANCELAMENTO = "cancelamento"
    RECLAMACAO = "reclamacao"
    OUTROS = "outros"


class Prioridade(StrEnum):
    URGENTE = "urgente"
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class Sentimento(StrEnum):
    POSITIVO = "positivo"
    NEUTRO = "neutro"
    NEGATIVO = "negativo"


class Canal(StrEnum):
    EMAIL = "email"
    CHAT = "chat"
    WHATSAPP = "whatsapp"
    FORMULARIO = "formulario"
    OUTRO = "outro"


class Origem(StrEnum):
    """Quem classificou: a IA ou o plano B por regras."""

    IA = "ia"
    REGRAS = "regras"


FILA_POR_CATEGORIA: dict[Categoria, str] = {
    Categoria.FINANCEIRO: "Financeiro",
    Categoria.SUPORTE_TECNICO: "Suporte",
    Categoria.COMERCIAL: "Vendas",
    Categoria.CANCELAMENTO: "Retenção",
    Categoria.RECLAMACAO: "Ouvidoria",
    Categoria.OUTROS: "Triagem humana",
}


class Triagem(BaseModel):
    """O que a classificação decide sobre um chamado, venha da IA ou das regras."""

    categoria: Categoria
    prioridade: Prioridade
    sentimento: Sentimento
    resumo: str
    numero_pedido: str | None = None
    resposta_sugerida: str
    # Autoavaliação do modelo, de 0 a 1. Fica vazia quando quem classificou foram as regras.
    confianca: float | None = None
    justificativa: str

    @field_validator("confianca")
    @classmethod
    def _confianca_entre_0_e_1(cls, valor: float | None) -> float | None:
        # O formato estrito da ferramenta não aceita mínimo e máximo; o limite fica aqui.
        if valor is None:
            return None
        return min(max(float(valor), 0.0), 1.0)

    @field_validator("numero_pedido")
    @classmethod
    def _numero_pedido_so_digitos(cls, valor: str | None) -> str | None:
        # Pedido aqui é numérico: "#458.812" vira "458812". Vazio ou longo demais vira None.
        if valor is None:
            return None
        digitos = re.sub(r"\D", "", valor)
        return digitos if 1 <= len(digitos) <= 20 else None

    @field_validator("resumo", "resposta_sugerida", "justificativa")
    @classmethod
    def _sem_caractere_de_controle(cls, valor: str) -> str:
        return _CONTROLE.sub(" ", valor).strip()


TextoChamado = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=TAMANHO_MAXIMO_TEXTO),
]


class ChamadoEntrada(BaseModel):
    """O que o sistema de atendimento envia para a API."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "texto": "Fui cobrado duas vezes pelo pedido 458812. "
                    "Meu CPF é 529.982.247-25. Preciso do estorno.",
                    "canal": "email",
                }
            ]
        }
    )

    texto: TextoChamado
    canal: Canal = Canal.OUTRO


class ChamadoSaida(BaseModel):
    """Chamado triado, como fica guardado no banco. O texto original nunca é guardado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    criado_em: datetime
    canal: Canal
    texto_mascarado: str
    dados_pessoais_encontrados: dict[str, int]
    categoria: Categoria
    prioridade: Prioridade
    sentimento: Sentimento
    resumo: str
    numero_pedido: str | None
    resposta_sugerida: str
    confianca: float | None
    justificativa: str
    fila: str
    origem: Origem
    revisao_humana: bool
    motivos_revisao: list[str]
    modelo: str | None
    tokens_entrada: int
    tokens_saida: int
    tokens_cache_escrita: int
    tokens_cache_leitura: int
    custo_usd: float
    tempo_ms: int

    @field_validator("criado_em")
    @classmethod
    def _sempre_em_utc(cls, valor: datetime) -> datetime:
        # O SQLite devolve a data sem fuso e o PostgreSQL devolve com. A API responde em UTC.
        if valor.tzinfo is None:
            return valor.replace(tzinfo=UTC)
        return valor.astimezone(UTC)


class Metricas(BaseModel):
    total_chamados: int
    por_categoria: dict[str, int]
    por_prioridade: dict[str, int]
    por_origem: dict[str, int]
    em_revisao_humana: int
    taxa_revisao_humana: float
    custo_total_usd: float
    custo_medio_usd: float
    tempo_medio_ms: float
