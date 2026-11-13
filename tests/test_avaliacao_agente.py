"""A avaliação completa do agente, com clientes falsos: nada chama a Anthropic nem o Google."""

import json
from types import SimpleNamespace

from app.config import Configuracao
from avaliacao import avaliar_agente as modulo
from tests.falsos import (
    ClienteAgenteFalso,
    ClienteConferenciaFalso,
    ClienteFalso,
    entrada_valida,
    resposta_agente,
)


class JuizFalso:
    """Imita o juiz: devolve um julgamento em JSON, como o formato estruturado garante."""

    def __init__(self, **julgamento):
        self.messages = self
        self.chamadas = []
        self._julgamento = {
            "comentario": "Responde certo.",
            "correta": True,
            "completa": True,
            "fiel_a_fonte": True,
            "sem_inventar": True,
            "disse_que_nao_sabe": False,
        }
        self._julgamento.update(julgamento)

    def create(self, **kwargs):
        self.chamadas.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(self._julgamento))],
            stop_reason="end_turn",
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=200,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
        )


def _preparar(monkeypatch, juiz=None):
    config = Configuracao(
        _env_file=None,
        anthropic_api_key="chave-falsa",
        gemini_api_key=None,
        google_cloud_project="",
    )
    monkeypatch.setattr(modulo, "Configuracao", lambda: config)
    clientes = {
        "triagem": ClienteFalso(
            entrada_valida(categoria="suporte_tecnico", prioridade="media", numero_pedido=None)
        ),
        "agente": ClienteAgenteFalso(("resposta", resposta_agente(artigos_usados=["bobina"]))),
        "conferencia": ClienteConferenciaFalso(),
        "juiz": juiz or JuizFalso(),
    }
    monkeypatch.setattr(modulo, "criar_cliente_anthropic", lambda config, papel: clientes[papel])
    return clientes


def test_avaliacao_roda_inteira_com_clientes_falsos(monkeypatch, tmp_path):
    clientes = _preparar(monkeypatch)
    assert modulo.main(["--saida", str(tmp_path), "--limite", "12"]) == 0
    dados = json.loads((tmp_path / "agente.json").read_text("utf-8"))
    resumo = dados["resumo"]
    assert resumo["perguntas"] == 12
    assert resumo["dados_enviados_ia"] == 0
    assert resumo["dados_enviados_embeddings"] == 0
    assert set(dados["contexto"]["amostra_para_conferir"]) <= {x["id"] for x in dados["linhas"]}
    texto = (tmp_path / "agente.md").read_text("utf-8")
    assert "Ressalva" in texto and "agente separado" in texto
    assert "Tabela curta para o README" in texto
    # O juiz: Claude Sonnet 5.5, saída estruturada, sem temperature.
    pedido = clientes["juiz"].chamadas[0]
    assert pedido["model"] == "claude-sonnet-5-5"
    assert "temperature" not in pedido
    assert pedido["output_config"]["format"]["type"] == "json_schema"


def test_mensagem_fixa_nao_vai_ao_juiz():
    linha = {"gabarito": {"artigos": []}, "resposta_fixa": True}
    assert modulo.julgamento_da_resposta_fixa(linha)["certa"] is True
    linha = {"gabarito": {"artigos": ["bobina"]}, "resposta_fixa": True}
    julgamento = modulo.julgamento_da_resposta_fixa(linha)
    assert julgamento["certa"] is False  # devia responder e não respondeu
    assert julgamento["disse_que_nao_sabe"] is True


def test_juiz_que_recusa_fica_como_nao_julgou():
    class Recusa(JuizFalso):
        def create(self, **kwargs):
            resposta = super().create(**kwargs)
            resposta.stop_reason = "refusal"
            return resposta

    julgamento = modulo.julgar(Recusa(), "pedido")
    assert julgamento["julgou"] is False
    assert julgamento["motivo"] == "o juiz recusou"


def _linha(**valores):
    linha = {
        "id": "x",
        "grupo": "responde",
        "gabarito": {"artigos": ["bobina"], "chamar_pessoa": False, "fila": "Suporte"},
        "precisa_pessoa": False,
        "resposta_fixa": False,
        "fontes": ["bobina"],
        "fila": "Suporte",
        "juiz": {"julgou": True, "pelo_juiz": True, "certa": True, "sem_inventar": True},
        "dados_pessoais": 0,
        "dados_enviados_ia": 0,
        "dados_enviados_embeddings": 0,
        "custo_usd": 0.001,
        "tempo_ms": 3000,
    }
    linha.update(valores)
    return linha


def test_resumo_mede_cada_coisa_no_grupo_certo():
    linhas = [
        _linha(id="a"),
        _linha(id="b", precisa_pessoa=True, custo_usd=0.003, tempo_ms=9000),
        _linha(
            id="c",
            grupo="sem_resposta",
            gabarito={"artigos": [], "chamar_pessoa": True, "fila": "Vendas"},
            precisa_pessoa=True,
            resposta_fixa=True,
            fontes=[],
            juiz={"julgou": True, "certa": True, "disse_que_nao_sabe": True, "sem_inventar": True},
        ),
        _linha(
            id="d",
            grupo="urgente",
            gabarito={
                "artigos": ["maquininha-perdida-ou-roubada"],
                "chamar_pessoa": True,
                "fila": "Suporte",
            },
            precisa_pessoa=False,
        ),
    ]
    resumo = modulo.resumir(linhas)
    assert resumo["resolvido_sem_pessoa"] == {"parte": 1, "todo": 2, "taxa": 0.5}
    assert resumo["nao_sei_certo"]["parte"] == 1
    assert resumo["inventou_nas_sem_resposta"] == 0
    assert resumo["chamou_pessoa_quando_devia"] == {"parte": 0, "todo": 1, "taxa": 0.0}
    assert resumo["fonte_nas_respostas_com_instrucao"]["parte"] == 3
    assert resumo["custo_pior_usd"] == 0.003
    assert resumo["tempo_pior_ms"] == 9000
    assert resumo["tempo_medio_ms"] == 4500


def test_numero_principal_e_numero_perigoso():
    linhas = [
        _linha(id="a"),  # saiu sem pessoa e certa
        _linha(id="b", juiz={"julgou": True, "pelo_juiz": True, "certa": False}),  # errada
        _linha(id="c", juiz={"julgou": False, "motivo": "falha"}),  # não julgou: não conta
        _linha(
            id="d",
            grupo="urgente",
            gabarito={"artigos": ["bobina"], "chamar_pessoa": True, "fila": "Suporte"},
        ),  # devia chamar uma pessoa e saiu sem: errada, mesmo com o juiz dizendo certa
        _linha(id="e", precisa_pessoa=True, juiz={"julgou": True, "certa": False}),
    ]
    resumo = modulo.resumir(linhas)
    assert resumo["resolvido_sem_pessoa_e_certo"] == {"parte": 1, "todo": 4, "taxa": 0.25}
    assert resumo["resolvido_sem_pessoa_e_errado"] == {"parte": 2, "todo": 5, "taxa": 0.4}
    assert resumo["saiu_sem_pessoa"]["parte"] == 4


def test_medidas_da_conferencia():
    linhas = [
        _linha(
            id="a",
            conferida=True,
            frases_removidas=["Dá para transferir o saldo."],
            custo_conferencia_usd=0.0002,
            tempo_conferencia_ms=800,
            motivos_pessoa=[],
        ),
        _linha(
            id="b",
            conferida=True,
            precisa_pessoa=True,
            frases_removidas=["Uma.", "Outra."],
            custo_conferencia_usd=0.0004,
            tempo_conferencia_ms=1200,
            motivos_pessoa=["conferência frase a frase: 2 de 3 frases sem apoio, sobrou pouco"],
        ),
        _linha(id="c", motivos_pessoa=[]),
    ]
    resumo = modulo.resumir(linhas)
    assert resumo["conferidas"] == 2
    assert resumo["conferencia_tirou_frase"] == 2
    assert resumo["frases_removidas"] == 3
    assert resumo["conferencia_chamou_pessoa"] == 1
    assert resumo["custo_conferencia_medio_usd"] == 0.0003
    assert resumo["tempo_conferencia_medio_ms"] == 1000


def test_repeticoes_dao_mediana_menor_e_maior(monkeypatch, tmp_path):
    clientes = _preparar(monkeypatch)
    argumentos = ["--saida", str(tmp_path), "--repeticoes", "3", "--nome", "prova"]
    assert modulo.main(argumentos) == 0
    for numero in (1, 2, 3):
        assert (tmp_path / f"prova_{numero}.json").exists()
    resumo = json.loads((tmp_path / "prova_resumo.json").read_text("utf-8"))["resumo"]
    assert resumo["repeticoes"] == 3
    principal = resumo["resolvido_sem_pessoa_e_certo"]
    assert set(principal) == {"mediana", "menor", "maior", "todo", "valores"}
    assert len(principal["valores"]) == 3
    assert principal["menor"] <= principal["mediana"] <= principal["maior"]
    texto = (tmp_path / "prova_resumo.md").read_text("utf-8")
    assert "Resolvido sem uma pessoa E certo" in texto
    assert "Resolvido sem uma pessoa e errado" in texto
    # A conferência também passa pelo gravador: a conta de dados pessoais inclui ela.
    assert clientes["conferencia"].chamadas


def test_relatorio_poe_os_dois_numeros_no_topo(monkeypatch, tmp_path):
    _preparar(monkeypatch)
    assert modulo.main(["--saida", str(tmp_path), "--limite", "3"]) == 0
    texto = (tmp_path / "agente.md").read_text("utf-8")
    tabela = texto.split("| Medida | Resultado | O certo |", 1)[1].split("\n")
    assert "Resolvido sem uma pessoa E certo" in tabela[2]
    assert "Resolvido sem uma pessoa e errado" in tabela[3]
    assert "A conferência frase a frase" in texto
