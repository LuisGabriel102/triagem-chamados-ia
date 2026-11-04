"""Banco de dados. Guarda o texto mascarado e a triagem, nunca o texto original."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from app.esquemas import Metricas
from app.servico import ResultadoTriagem


class Base(DeclarativeBase):
    pass


class ChamadoRegistro(Base):
    __tablename__ = "chamados"

    id: Mapped[int] = mapped_column(primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    canal: Mapped[str] = mapped_column(String(20))
    texto_mascarado: Mapped[str] = mapped_column(Text)
    # Quantos dados pessoais de cada tipo foram escondidos. Nunca o dado em si.
    dados_pessoais_encontrados: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    categoria: Mapped[str] = mapped_column(String(30), index=True)
    prioridade: Mapped[str] = mapped_column(String(10), index=True)
    sentimento: Mapped[str] = mapped_column(String(10))
    resumo: Mapped[str] = mapped_column(Text)
    numero_pedido: Mapped[str | None] = mapped_column(String(40))
    resposta_sugerida: Mapped[str] = mapped_column(Text)
    confianca: Mapped[float | None]
    justificativa: Mapped[str] = mapped_column(Text)
    fila: Mapped[str] = mapped_column(String(40))
    origem: Mapped[str] = mapped_column(String(10))
    revisao_humana: Mapped[bool] = mapped_column(index=True)
    motivos_revisao: Mapped[list[Any]] = mapped_column(JSON, default=list)
    modelo: Mapped[str | None] = mapped_column(String(60))
    tokens_entrada: Mapped[int] = mapped_column(default=0)
    tokens_saida: Mapped[int] = mapped_column(default=0)
    tokens_cache_escrita: Mapped[int] = mapped_column(default=0)
    tokens_cache_leitura: Mapped[int] = mapped_column(default=0)
    custo_usd: Mapped[float] = mapped_column(default=0.0)
    tempo_ms: Mapped[int] = mapped_column(default=0)


def criar_motor(url: str) -> Engine:
    if url.startswith("sqlite"):
        opcoes: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # Banco em memória: uma conexão só, senão cada conexão vê um banco vazio.
            opcoes["poolclass"] = StaticPool
        return create_engine(url, **opcoes)
    return create_engine(url, pool_pre_ping=True)


def criar_tabelas(motor: Engine) -> None:
    Base.metadata.create_all(motor)


def salvar(sessao: Session, resultado: ResultadoTriagem) -> ChamadoRegistro:
    triagem = resultado.triagem
    registro = ChamadoRegistro(
        canal=resultado.canal.value,
        texto_mascarado=resultado.texto_mascarado,
        dados_pessoais_encontrados=dict(resultado.dados_pessoais_encontrados),
        categoria=triagem.categoria.value,
        prioridade=triagem.prioridade.value,
        sentimento=triagem.sentimento.value,
        resumo=triagem.resumo,
        numero_pedido=triagem.numero_pedido,
        resposta_sugerida=triagem.resposta_sugerida,
        confianca=triagem.confianca,
        justificativa=triagem.justificativa,
        fila=resultado.fila,
        origem=resultado.origem.value,
        revisao_humana=resultado.revisao_humana,
        motivos_revisao=list(resultado.motivos_revisao),
        modelo=resultado.modelo,
        tokens_entrada=resultado.uso.tokens_entrada,
        tokens_saida=resultado.uso.tokens_saida,
        tokens_cache_escrita=resultado.uso.tokens_cache_escrita,
        tokens_cache_leitura=resultado.uso.tokens_cache_leitura,
        custo_usd=resultado.custo_usd,
        tempo_ms=resultado.tempo_ms,
    )
    sessao.add(registro)
    sessao.commit()
    sessao.refresh(registro)
    return registro


def buscar(sessao: Session, chamado_id: int) -> ChamadoRegistro | None:
    return sessao.get(ChamadoRegistro, chamado_id)


def listar(
    sessao: Session, revisao_humana: bool | None = None, limite: int = 50
) -> list[ChamadoRegistro]:
    consulta = select(ChamadoRegistro).order_by(ChamadoRegistro.id.desc()).limit(limite)
    if revisao_humana is not None:
        consulta = consulta.where(ChamadoRegistro.revisao_humana.is_(revisao_humana))
    return list(sessao.scalars(consulta))


def calcular_metricas(sessao: Session) -> Metricas:
    def contar_por(coluna: Any) -> dict[str, int]:
        linhas = sessao.execute(select(coluna, func.count()).group_by(coluna)).all()
        return {str(valor): quantidade for valor, quantidade in linhas}

    total = sessao.scalar(select(func.count()).select_from(ChamadoRegistro)) or 0
    em_revisao = (
        sessao.scalar(
            select(func.count())
            .select_from(ChamadoRegistro)
            .where(ChamadoRegistro.revisao_humana.is_(True))
        )
        or 0
    )
    custo_total = float(sessao.scalar(select(func.sum(ChamadoRegistro.custo_usd))) or 0.0)
    tempo_medio = float(sessao.scalar(select(func.avg(ChamadoRegistro.tempo_ms))) or 0.0)
    return Metricas(
        total_chamados=total,
        por_categoria=contar_por(ChamadoRegistro.categoria),
        por_prioridade=contar_por(ChamadoRegistro.prioridade),
        por_origem=contar_por(ChamadoRegistro.origem),
        em_revisao_humana=em_revisao,
        taxa_revisao_humana=round(em_revisao / total, 4) if total else 0.0,
        custo_total_usd=round(custo_total, 6),
        custo_medio_usd=round(custo_total / total, 8) if total else 0.0,
        tempo_medio_ms=round(tempo_medio, 1),
    )
