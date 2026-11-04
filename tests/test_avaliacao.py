import json

from app.classificador import ClassificadorClaude
from app.config import Configuracao
from app.servico import ServicoTriagem
from avaliacao import avaliar as modulo
from tests.falsos import ClienteFalso, entrada_valida


def test_avaliacao_do_plano_b_roda_inteira(tmp_path):
    assert modulo.main(["--modo", "regras", "--saida", str(tmp_path)]) == 0
    resumo = json.loads((tmp_path / "regras.json").read_text("utf-8"))["resumo"]
    assert resumo["total_chamados"] == 40
    assert resumo["dados_que_sobraram"] == 0
    # Tudo o que o plano B classifica vai para revisão humana.
    assert resumo["enviados_para_revisao"] == 40
    assert resumo["urgentes_sem_olhar_humano"] == 0
    assert (tmp_path / "regras.md").read_text("utf-8").startswith("# Avaliação: modo `regras`")


def test_resumo_conta_acertos_urgentes_e_liberados():
    chamados = [
        {
            "id": "a",
            "canal": "email",
            "texto": "Fui cobrado duas vezes.",
            "gabarito": {
                "categoria": "financeiro",
                "prioridade": "alta",
                "sentimento": "neutro",
                "numero_pedido": None,
            },
        },
        {
            "id": "b",
            "canal": "chat",
            "texto": "O sistema caiu, não consigo vender!",
            "gabarito": {
                "categoria": "suporte_tecnico",
                "prioridade": "urgente",
                "sentimento": "negativo",
                "numero_pedido": None,
            },
        },
    ]
    # A IA falsa responde "financeiro, alta, neutro" para os dois chamados.
    cliente = ClienteFalso(entrada_valida(numero_pedido=None))
    servico = ServicoTriagem(ClassificadorClaude(cliente, "claude-haiku-5-5"))
    resumo = modulo.resumir(modulo.avaliar(servico, chamados))
    assert resumo["acertos"] == {
        "categoria": 1,
        "prioridade": 1,
        "sentimento": 1,
        "numero_pedido": 2,
    }
    assert resumo["todos_os_campos_certos"] == 1
    assert resumo["urgentes"] == 1
    assert resumo["urgentes_reconhecidos"] == 0
    # O urgente que a IA errou passou sem revisão: é isso que a medida existe para mostrar.
    assert resumo["urgentes_sem_olhar_humano"] == 1
    assert resumo["liberados_sem_revisao"] == 2
    assert resumo["liberados_certos"] == 1
    assert resumo["trocas_de_categoria"] == {"suporte_tecnico → financeiro": 1}


def test_modo_ia_sem_chave_avisa_e_para(monkeypatch, tmp_path, capsys):
    # Garante que nenhuma chave real do .env seja usada neste teste.
    monkeypatch.setattr(
        modulo, "Configuracao", lambda: Configuracao(_env_file=None, anthropic_api_key=None)
    )
    assert modulo.main(["--modo", "ia", "--saida", str(tmp_path)]) == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())
