"""API de triagem de chamados (FastAPI)."""

import html
import logging
import mimetypes
import secrets
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app import banco
from app.atendimento import ResultadoAtendimento, ServicoAtendimento, criar_atendimento
from app.config import Configuracao
from app.esquemas import (
    AtendimentoDemo,
    AtendimentoDemoEntrada,
    AtendimentoEntrada,
    AtendimentoSaida,
    ChamadoDemo,
    ChamadoEntrada,
    ChamadoSaida,
    CustoAtendimento,
    CustoAtendimentoDemo,
    FonteDemo,
    FonteSaida,
    LojistaDemo,
    Metricas,
    TempoAtendimento,
    TempoAtendimentoDemo,
    TriagemDemo,
)
from app.ferramentas import LojistaDesconhecido
from app.limite import LimiteDeUso
from app.servico import ServicoTriagem, criar_servico, para_demo

log = logging.getLogger(__name__)

PASTA_PAGINAS = Path(__file__).parent / "paginas"
PASTA_ESTATICA = Path(__file__).parent / "estatico"
# Algumas imagens Linux enxutas não conhecem o tipo da fonte .woff2.
mimetypes.add_type("font/woff2", ".woff2")

# A página só carrega arquivos do próprio servidor: nada de terceiros, nem fonte.
CABECALHOS_DA_PAGINA = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
        "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}

DESCRICAO = """
Recebe o texto de um chamado de atendimento, esconde os dados pessoais (LGPD),
classifica com IA e devolve categoria, prioridade, sentimento, resumo, número do
pedido, resposta sugerida, fila de destino e se precisa de revisão humana.

Se a IA falhar, um plano B por palavras-chave classifica o chamado e manda para
revisão humana. O serviço não para.
"""


def get_servico(request: Request) -> ServicoTriagem:
    return request.app.state.servico


def get_sessao(request: Request) -> Iterator[Session]:
    with request.app.state.fabrica_sessao() as sessao:
        yield sessao


def verificar_chave(request: Request, x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Exige o cabeçalho X-API-Key quando CHAVE_API_APP estiver configurada."""
    configurada = request.app.state.config.chave_api_app
    esperada = configurada.get_secret_value() if configurada else ""
    if not esperada:
        return
    if x_api_key is None or not secrets.compare_digest(
        x_api_key.encode("utf-8"), esperada.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API inválida ou ausente. Envie o cabeçalho X-API-Key.",
        )


async def erro_de_validacao(request: Request, erro: RequestValidationError) -> JSONResponse:
    """Responde 422 sem repetir o que foi enviado: o texto pode ter dado pessoal."""
    detalhes = [
        {chave: valor for chave, valor in item.items() if chave not in ("input", "ctx", "url")}
        for item in erro.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(detalhes)})


Servico = Annotated[ServicoTriagem, Depends(get_servico)]
Sessao = Annotated[Session, Depends(get_sessao)]

rotas_abertas = APIRouter()
rotas_protegidas = APIRouter(dependencies=[Depends(verificar_chave)])


@lru_cache(maxsize=1)
def _modelo_da_pagina() -> str:
    return (PASTA_PAGINAS / "demo.html").read_text(encoding="utf-8")


def montar_pagina(url_publica: str) -> str:
    """Página de demonstração. Com o endereço público, inclui a prévia para redes sociais."""
    meta = ""
    url = html.escape(url_publica.strip().rstrip("/"), quote=True)
    if url.startswith("https://") or url.startswith("http://"):
        meta = f'<meta property="og:url" content="{url}/">'
        if (PASTA_ESTATICA / "previa.png").exists():
            meta += (
                f'\n<meta property="og:image" content="{url}/estatico/previa.png">'
                '\n<meta name="twitter:card" content="summary_large_image">'
            )
    return _modelo_da_pagina().replace("<!--META_PUBLICA-->", meta)


@rotas_abertas.get("/", include_in_schema=False)
def inicio(request: Request) -> Response:
    config = request.app.state.config
    if not config.demo_ativa:
        return RedirectResponse(url="/docs")
    return HTMLResponse(montar_pagina(config.url_publica), headers=CABECALHOS_DA_PAGINA)


def _turnos(entrada: AtendimentoEntrada | AtendimentoDemoEntrada) -> list[tuple[str, str]]:
    """O histórico da conversa como (papel, texto), do mais antigo ao mais novo."""
    return [(turno.papel, turno.texto) for turno in entrada.historico]


def _demo_ligada(request: Request) -> None:
    if not request.app.state.config.demo_ativa:
        raise HTTPException(status_code=404, detail="A demonstração está desligada.")


def _conferir_limite(request: Request, limite: LimiteDeUso) -> None:
    """Limite por endereço (por hora) e da demonstração inteira (por dia)."""
    pessoa = request.client.host if request.client else "desconhecido"
    bloqueio = limite.verificar(pessoa)
    if bloqueio:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=bloqueio)


def _atendimento_no_ar(request: Request) -> ServicoAtendimento:
    atendimento: ServicoAtendimento | None = request.app.state.atendimento
    if atendimento is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O atendimento não está disponível neste servidor.",
        )
    return atendimento


@rotas_abertas.post(
    "/demo/triagem",
    response_model=TriagemDemo,
    summary="Triagem de demonstração: aberta, não grava nada e tem limite de uso",
)
def triagem_demo(entrada: ChamadoDemo, request: Request, servico: Servico) -> TriagemDemo:
    _demo_ligada(request)
    _conferir_limite(request, request.app.state.limite_demo)
    return para_demo(servico.triar(entrada.texto, entrada.canal))


@rotas_abertas.get(
    "/demo/lojistas",
    response_model=list[LojistaDemo],
    summary="As lojas inventadas que a página de demonstração pode escolher",
)
def lojistas_demo(request: Request) -> list[LojistaDemo]:
    _demo_ligada(request)
    return [LojistaDemo(**loja) for loja in _atendimento_no_ar(request).lojistas()]


def para_atendimento_demo(resultado: ResultadoAtendimento) -> AtendimentoDemo:
    return AtendimentoDemo(
        resposta=resultado.resposta,
        fontes=[FonteDemo(id=a.id, titulo=a.titulo, texto=a.texto) for a in resultado.fontes],
        fila=resultado.fila,
        precisa_pessoa=resultado.precisa_pessoa,
        motivos_pessoa=resultado.motivos_pessoa,
        origem_resposta=resultado.origem_resposta,
        categoria=resultado.categoria,
        prioridade=resultado.prioridade,
        texto_mascarado=resultado.texto_mascarado,
        dados_pessoais_encontrados=resultado.dados_pessoais_encontrados,
        frases_removidas=[*resultado.frases_removidas, *resultado.frases_removidas_refeita],
        refeita=resultado.refeita,
        modo_busca=resultado.modo_busca,
        ferramentas_usadas=resultado.ferramentas_usadas,
        avisos=resultado.avisos,
        modelo=resultado.modelo_resposta,
        custo=CustoAtendimentoDemo(
            total_usd=resultado.custo_usd,
            triagem_usd=resultado.custo_triagem_usd,
            busca_usd=resultado.custo_busca_usd,
            resposta_usd=resultado.custo_resposta_usd,
            conferencia_usd=resultado.custo_conferencia_usd,
            refeita_usd=resultado.custo_refeita_usd,
        ),
        tempo=TempoAtendimentoDemo(
            total_ms=resultado.tempo_ms,
            triagem_ms=resultado.tempo_triagem_ms,
            busca_ms=resultado.tempo_busca_ms,
            resposta_ms=resultado.tempo_resposta_ms,
            conferencia_ms=resultado.tempo_conferencia_ms,
            refeita_ms=resultado.tempo_refeita_ms,
        ),
    )


@rotas_abertas.post(
    "/demo/atendimento",
    response_model=AtendimentoDemo,
    summary="Atendimento de demonstração: aberto, não grava nada e tem limite de uso",
)
def atendimento_demo(entrada: AtendimentoDemoEntrada, request: Request) -> AtendimentoDemo:
    _demo_ligada(request)
    atendimento = _atendimento_no_ar(request)
    if not atendimento.existe_lojista(entrada.sessao.lojista_id):
        raise HTTPException(status_code=404, detail="Lojista da sessão não encontrado.")
    _conferir_limite(request, request.app.state.limite_atendimento_demo)
    resultado = atendimento.atender(
        entrada.mensagem, entrada.canal, entrada.sessao.lojista_id, _turnos(entrada)
    )
    return para_atendimento_demo(resultado)


@rotas_abertas.get("/saude", summary="Diz se a API está no ar e se a IA está configurada")
def saude(servico: Servico) -> dict[str, object]:
    return {"status": "ok", "ia_configurada": servico.ia_configurada, "modelo": servico.modelo}


@rotas_protegidas.post(
    "/chamados",
    status_code=status.HTTP_201_CREATED,
    response_model=ChamadoSaida,
    summary="Faz a triagem de um chamado e guarda o resultado",
)
def criar_chamado(entrada: ChamadoEntrada, servico: Servico, sessao: Sessao) -> object:
    resultado = servico.triar(entrada.texto, entrada.canal)
    return banco.salvar(sessao, resultado)


@rotas_protegidas.get(
    "/chamados/{chamado_id}", response_model=ChamadoSaida, summary="Busca um chamado triado"
)
def obter_chamado(chamado_id: int, sessao: Sessao) -> object:
    registro = banco.buscar(sessao, chamado_id)
    if registro is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chamado não encontrado.")
    return registro


@rotas_protegidas.get(
    "/chamados",
    response_model=list[ChamadoSaida],
    summary="Lista os chamados mais recentes, com filtro de revisão humana",
)
def listar_chamados(
    sessao: Sessao,
    revisao_humana: bool | None = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
) -> object:
    return banco.listar(sessao, revisao_humana=revisao_humana, limite=limite)


def para_atendimento_saida(registro: banco.AtendimentoRegistro) -> AtendimentoSaida:
    return AtendimentoSaida(
        id=registro.id,
        criado_em=registro.criado_em,
        resposta=registro.resposta,
        fontes=[FonteSaida(**fonte) for fonte in registro.fontes],
        fila=registro.fila,
        precisa_pessoa=registro.precisa_pessoa,
        motivos_pessoa=registro.motivos_pessoa,
        origem_resposta=registro.origem_resposta,
        categoria=registro.categoria,
        prioridade=registro.prioridade,
        ferramentas_usadas=registro.ferramentas_usadas,
        avisos=registro.avisos,
        texto_mascarado=registro.texto_mascarado,
        frases_removidas=registro.frases_removidas,
        custo=CustoAtendimento(
            total_usd=registro.custo_usd,
            triagem_usd=registro.custo_triagem_usd,
            busca_usd=registro.custo_busca_usd,
            resposta_usd=registro.custo_resposta_usd,
            conferencia_usd=registro.custo_conferencia_usd,
        ),
        tempo=TempoAtendimento(
            total_ms=registro.tempo_ms,
            triagem_ms=registro.tempo_triagem_ms,
            busca_ms=registro.tempo_busca_ms,
            resposta_ms=registro.tempo_resposta_ms,
            conferencia_ms=registro.tempo_conferencia_ms,
        ),
    )


@rotas_protegidas.post(
    "/atendimento",
    response_model=AtendimentoSaida,
    summary="Responde uma mensagem do lojista com a base de conhecimento e chama uma pessoa "
    "quando precisa",
)
def atender(entrada: AtendimentoEntrada, request: Request, sessao: Sessao) -> AtendimentoSaida:
    atendimento = _atendimento_no_ar(request)
    try:
        resultado = atendimento.atender(
            entrada.mensagem, entrada.canal, entrada.sessao.lojista_id, _turnos(entrada)
        )
    except LojistaDesconhecido as erro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lojista da sessão não encontrado."
        ) from erro
    return para_atendimento_saida(banco.salvar_atendimento(sessao, resultado))


@rotas_protegidas.get(
    "/metricas", response_model=Metricas, summary="Totais, revisão humana, custo e tempo"
)
def metricas(sessao: Sessao) -> Metricas:
    return banco.calcular_metricas(sessao)


def criar_app(
    config: Configuracao | None = None,
    servico: ServicoTriagem | None = None,
    motor: Engine | None = None,
    atendimento: ServicoAtendimento | None = None,
) -> FastAPI:
    """Monta a API. Os testes passam peças prontas; em produção tudo vem do .env."""

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        cfg = config or Configuracao()
        mot = motor or banco.criar_motor(cfg.database_url)
        banco.criar_tabelas(mot)
        app.state.config = cfg
        app.state.servico = servico or criar_servico(cfg)
        app.state.fabrica_sessao = sessionmaker(mot, expire_on_commit=False)
        app.state.limite_demo = LimiteDeUso(cfg.demo_limite_por_hora, cfg.demo_limite_por_dia)
        # O atendimento da página tem o mesmo limite, com a conta separada: quem testou a
        # triagem ainda pode testar o atendimento.
        app.state.limite_atendimento_demo = LimiteDeUso(
            cfg.demo_limite_por_hora, cfg.demo_limite_por_dia
        )
        app.state.atendimento = atendimento
        if atendimento is None:
            # Sem a base ou os dados (por exemplo, numa imagem antiga), a triagem segue no ar
            # e só a rota /atendimento responde 503.
            try:
                app.state.atendimento = criar_atendimento(cfg)
            except Exception:
                log.exception("Atendimento desligado: não deu para montar a busca e o agente.")
        if not app.state.servico.ia_configurada:
            falta = "GOOGLE_CLOUD_PROJECT" if cfg.provedor_ia == "gemini" else "ANTHROPIC_API_KEY"
            log.warning("%s vazia: os chamados serão classificados só por regras.", falta)
        if not (cfg.chave_api_app and cfg.chave_api_app.get_secret_value()):
            log.warning("CHAVE_API_APP vazia: a API está aberta. Use assim só no seu computador.")
        yield
        if motor is None:
            mot.dispose()

    app = FastAPI(
        title="Triagem de Chamados com IA",
        version="0.1.0",
        description=DESCRICAO,
        lifespan=ciclo_de_vida,
    )
    app.add_exception_handler(RequestValidationError, erro_de_validacao)
    app.mount("/estatico", StaticFiles(directory=PASTA_ESTATICA), name="estatico")
    app.include_router(rotas_abertas)
    app.include_router(rotas_protegidas)
    return app


app = criar_app()
