import json

from google.genai import errors as erros_google

from app.classificador import ClassificadorClaude
from app.config import Configuracao
from app.servico import ServicoTriagem
from avaliacao import avaliar as modulo
from avaliacao import comparar
from tests.falsos import ClienteFalso, ClienteGeminiFalso, entrada_valida


def _config_gemini(**ajustes):
    """Configuração de teste: ignora o .env e aponta para um projeto fictício."""
    valores = {"anthropic_api_key": None, "google_cloud_project": "projeto-teste"}
    valores.update(ajustes)
    return lambda: Configuracao(_env_file=None, **valores)


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


def test_gemini_grava_um_arquivo_por_modelo_sem_apagar_o_do_claude(monkeypatch, tmp_path):
    monkeypatch.setattr(modulo, "Configuracao", _config_gemini())
    monkeypatch.setattr("app.classificador_gemini.genai.Client", lambda **_: ClienteGeminiFalso())
    argumentos = ["--modo", "ia", "--provedor", "gemini", "--modelo", "gemini-3.8-flash"]
    assert modulo.main([*argumentos, "--saida", str(tmp_path)]) == 0
    detalhes = json.loads((tmp_path / "ia_gemini-3.8-flash.json").read_text("utf-8"))
    assert detalhes["provedor"] == "gemini"
    assert detalhes["modelo"] == "gemini-3.8-flash"
    assert detalhes["resumo"]["total_chamados"] == 40
    assert detalhes["resumo"]["quedas_para_o_plano_b"] == 0
    assert detalhes["resumo"]["dados_que_sobraram"] == 0
    texto = (tmp_path / "ia_gemini-3.8-flash.md").read_text("utf-8")
    assert "`gemini-3.8-flash` (Gemini, no Vertex AI)" in texto
    assert "Preço usado no custo" in texto
    assert not (tmp_path / "ia.json").exists()


def test_para_na_primeira_falha_sem_gastar_nem_gravar(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(modulo, "Configuracao", _config_gemini())
    erro = erros_google.ClientError(404, {"error": {"message": "x", "status": "NOT_FOUND"}})
    cliente = ClienteGeminiFalso(erro=erro)
    monkeypatch.setattr("app.classificador_gemini.genai.Client", lambda **_: cliente)
    assert modulo.main(["--modo", "ia", "--provedor", "gemini", "--saida", str(tmp_path)]) == 1
    assert "A primeira chamada à IA falhou" in capsys.readouterr().err
    assert len(cliente.chamadas) == 1
    assert not list(tmp_path.iterdir())


def test_modelo_sem_preco_nem_comeca(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(modulo, "Configuracao", _config_gemini())
    argumentos = ["--modo", "ia", "--provedor", "gemini", "--modelo", "gemini-9-ultra"]
    assert modulo.main([*argumentos, "--saida", str(tmp_path)]) == 1
    assert "tabela de preços" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


def test_gemini_sem_projeto_avisa_e_para(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(modulo, "Configuracao", _config_gemini(google_cloud_project=""))
    assert modulo.main(["--modo", "ia", "--provedor", "gemini", "--saida", str(tmp_path)]) == 1
    assert "GOOGLE_CLOUD_PROJECT" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


def _resumo(**ajustes):
    resumo = {
        "total_chamados": 40,
        "acertos": {"categoria": 40, "prioridade": 38, "sentimento": 38, "numero_pedido": 40},
        "todos_os_campos_certos": 36,
        "urgentes": 7,
        "urgentes_reconhecidos": 7,
        "enviados_para_revisao": 13,
        "quedas_para_o_plano_b": 0,
        "custo_medio_usd": 0.000241,
        "tempo_medio_ms": 2600.0,
    }
    resumo.update(ajustes)
    return resumo


def test_comparacao_junta_os_modelos_numa_tabela(tmp_path):
    # Rodada antiga do Claude, sem o campo "provedor".
    claude = {"modelo": "claude-haiku-5-5", "quando": "04/11/2026", "resumo": _resumo()}
    gemini = {
        "provedor": "gemini",
        "modelo": "gemini-3.5-flash-lite",
        "quando": "12/11/2026",
        "resumo": _resumo(custo_medio_usd=0.0018, tempo_medio_ms=1900.0),
    }
    (tmp_path / "ia_gemini-3.5-flash-lite.json").write_text(json.dumps(gemini), "utf-8")
    (tmp_path / "ia.json").write_text(json.dumps(claude), "utf-8")
    assert comparar.main(["--pasta", str(tmp_path)]) == 0
    texto = (tmp_path / "comparacao.md").read_text("utf-8")
    linhas = [linha for linha in texto.splitlines() if linha.startswith("| `")]
    assert linhas[0].startswith("| `claude-haiku-5-5` | 100% | 95% |")
    assert "| 7 de 7 |" in linhas[0]
    assert "US$ 0,000241" in linhas[0]
    assert "2,6 s" in linhas[0]
    assert linhas[1].startswith("| `gemini-3.5-flash-lite`")
    assert "US$ 0,001800" in linhas[1]


def test_comparacao_precisa_de_duas_avaliacoes(tmp_path, capsys):
    assert comparar.main(["--pasta", str(tmp_path)]) == 1
    assert "pelo menos duas" in capsys.readouterr().err
