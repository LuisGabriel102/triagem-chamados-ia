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
from app.config import Configuracao
from app.esquemas import ChamadoDemo, ChamadoEntrada, ChamadoSaida, Metricas, TriagemDemo
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


@rotas_abertas.post(
    "/demo/triagem",
    response_model=TriagemDemo,
    summary="Triagem de demonstração: aberta, não grava nada e tem limite de uso",
)
def triagem_demo(entrada: ChamadoDemo, request: Request, servico: Servico) -> TriagemDemo:
    if not request.app.state.config.demo_ativa:
        raise HTTPException(status_code=404, detail="A demonstração está desligada.")
    pessoa = request.client.host if request.client else "desconhecido"
    bloqueio = request.app.state.limite_demo.verificar(pessoa)
    if bloqueio:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=bloqueio)
    return para_demo(servico.triar(entrada.texto, entrada.canal))


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


@rotas_protegidas.get(
    "/metricas", response_model=Metricas, summary="Totais, revisão humana, custo e tempo"
)
def metricas(sessao: Sessao) -> Metricas:
    return banco.calcular_metricas(sessao)


def criar_app(
    config: Configuracao | None = None,
    servico: ServicoTriagem | None = None,
    motor: Engine | None = None,
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
        if not app.state.servico.ia_configurada:
            log.warning("ANTHROPIC_API_KEY vazia: os chamados serão classificados só por regras.")
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
