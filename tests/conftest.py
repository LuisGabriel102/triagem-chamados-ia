import os
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from app.banco import Base, criar_motor
from app.classificador import ClassificadorClaude
from app.config import Configuracao
from app.main import criar_app
from app.servico import ServicoTriagem
from tests.falsos import ClienteFalso

# Sem DATABASE_URL_TESTE, os testes usam SQLite em memória. No CI, rodam também no PostgreSQL.
URL_BANCO_TESTE = os.environ.get("DATABASE_URL_TESTE", "sqlite://")

# Os testes apagam e recriam as tabelas. Trava para nunca rodar num banco de verdade.
if not URL_BANCO_TESTE.startswith("sqlite") and "test" not in URL_BANCO_TESTE:
    raise RuntimeError("DATABASE_URL_TESTE precisa apontar para um banco de teste.")


@pytest.fixture
def motor() -> Iterator[Engine]:
    motor = criar_motor(URL_BANCO_TESTE)
    Base.metadata.drop_all(motor)
    yield motor
    Base.metadata.drop_all(motor)
    motor.dispose()


@pytest.fixture
def abrir_api(motor: Engine) -> Iterator[Callable[..., TestClient]]:
    """Abre a API com um cliente falso da Anthropic (ou sem IA) e o banco de teste."""
    abertos: list[TestClient] = []

    def _abrir(
        cliente_ia: ClienteFalso | None = None,
        chave_api: str | None = None,
        sem_ia: bool = False,
        **ajustes: object,
    ) -> TestClient:
        classificador = None
        if not sem_ia:
            classificador = ClassificadorClaude(cliente_ia or ClienteFalso(), "claude-haiku-5-5")
        config = Configuracao(
            _env_file=None, anthropic_api_key=None, chave_api_app=chave_api, **ajustes
        )
        app = criar_app(config=config, servico=ServicoTriagem(classificador), motor=motor)
        cliente = TestClient(app)
        cliente.__enter__()
        abertos.append(cliente)
        return cliente

    yield _abrir
    for cliente in abertos:
        cliente.__exit__(None, None, None)
