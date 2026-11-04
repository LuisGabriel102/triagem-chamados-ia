from app.limite import UMA_HORA, LimiteDeUso


class Relogio:
    def __init__(self) -> None:
        self.agora = 1_800_000_000.0  # um dia qualquer, meio da manhã em UTC

    def __call__(self) -> float:
        return self.agora


def test_limite_por_pessoa_na_hora_e_liberado_depois():
    relogio = Relogio()
    limite = LimiteDeUso(por_hora=2, por_dia=100, relogio=relogio)
    assert limite.verificar("1.1.1.1") is None
    assert limite.verificar("1.1.1.1") is None
    assert "desta hora" in limite.verificar("1.1.1.1")
    # Outra pessoa não é afetada.
    assert limite.verificar("2.2.2.2") is None
    # Uma hora depois, a primeira pessoa volta a poder testar.
    relogio.agora += UMA_HORA
    assert limite.verificar("1.1.1.1") is None


def test_limite_do_dia_vale_para_todo_mundo_e_zera_no_dia_seguinte():
    relogio = Relogio()
    limite = LimiteDeUso(por_hora=100, por_dia=3, relogio=relogio)
    for pessoa in ("a", "b", "c"):
        assert limite.verificar(pessoa) is None
    assert "limite de hoje" in limite.verificar("d")
    relogio.agora += 24 * UMA_HORA
    assert limite.verificar("d") is None


def test_pedido_bloqueado_nao_conta_como_uso():
    relogio = Relogio()
    limite = LimiteDeUso(por_hora=1, por_dia=2, relogio=relogio)
    assert limite.verificar("a") is None
    assert limite.verificar("a") is not None  # bloqueado pela hora
    assert limite.verificar("b") is None  # o bloqueio de "a" não gastou o limite do dia
