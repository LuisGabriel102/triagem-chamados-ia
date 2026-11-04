"""Limite de uso da demonstração pública.

A página aberta usa a chave da Anthropic de quem publicou. Para a conta não
estourar, cada pessoa (endereço IP) tem um limite por hora e a demonstração
inteira tem um limite por dia. Fica na memória: basta para um servidor só.
"""

import threading
import time
from collections import deque
from collections.abc import Callable

UMA_HORA = 3600
MAXIMO_DE_PESSOAS_NA_MEMORIA = 10_000


class LimiteDeUso:
    def __init__(
        self, por_hora: int, por_dia: int, relogio: Callable[[], float] = time.time
    ) -> None:
        self._por_hora = por_hora
        self._por_dia = por_dia
        self._relogio = relogio
        self._trava = threading.Lock()
        self._pedidos_por_pessoa: dict[str, deque[float]] = {}
        self._dia: str | None = None
        self._usados_no_dia = 0

    def verificar(self, pessoa: str) -> str | None:
        """Registra o uso e devolve None, ou devolve o motivo do bloqueio."""
        agora = self._relogio()
        dia = time.strftime("%Y-%m-%d", time.gmtime(agora))
        with self._trava:
            if dia != self._dia:
                self._dia, self._usados_no_dia = dia, 0
            if self._usados_no_dia >= self._por_dia:
                return "A demonstração chegou ao limite de hoje. Tente de novo amanhã."
            self._esquecer_pedidos_antigos(agora)
            pedidos = self._pedidos_por_pessoa.setdefault(pessoa, deque())
            if len(pedidos) >= self._por_hora:
                return "Você chegou ao limite de testes desta hora. Tente de novo mais tarde."
            pedidos.append(agora)
            self._usados_no_dia += 1
            return None

    def _esquecer_pedidos_antigos(self, agora: float) -> None:
        for pessoa in list(self._pedidos_por_pessoa):
            pedidos = self._pedidos_por_pessoa[pessoa]
            while pedidos and agora - pedidos[0] >= UMA_HORA:
                pedidos.popleft()
            if not pedidos:
                del self._pedidos_por_pessoa[pessoa]
        # Proteção contra muitos endereços diferentes enchendo a memória.
        if len(self._pedidos_por_pessoa) > MAXIMO_DE_PESSOAS_NA_MEMORIA:
            self._pedidos_por_pessoa.clear()
