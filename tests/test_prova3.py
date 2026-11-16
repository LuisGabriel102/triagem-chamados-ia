"""A prova 3 está bem formada. Nada aqui roda o atendimento nem chama IA."""

import json
from collections import Counter
from pathlib import Path

from app.base_conhecimento import carregar_artigos
from app.ferramentas import DadosLojistas
from app.mascaramento import mascarar

ARQUIVO = Path(__file__).parent.parent / "avaliacao" / "perguntas_prova3.jsonl"
PERGUNTAS = [json.loads(linha) for linha in ARQUIVO.read_text("utf-8").splitlines() if linha]


def test_quarenta_mensagens_com_a_mesma_divisao_das_provas_1_e_2():
    assert len(PERGUNTAS) == 40
    assert len({p["id"] for p in PERGUNTAS}) == 40
    assert Counter(p["grupo"] for p in PERGUNTAS) == {
        "responde": 25,
        "sem_resposta": 7,
        "tentativa": 4,
        "urgente": 4,
    }
    assert sum(bool(p["dados_pessoais"]) for p in PERGUNTAS) == 6


def test_gabarito_aponta_para_artigos_e_lojas_que_existem():
    artigos = {a.id for a in carregar_artigos()}
    dados = DadosLojistas()
    for p in PERGUNTAS:
        g = p["gabarito"]
        assert set(g["artigos"]) <= artigos, p["id"]
        assert dados.existe(g["lojista"]), p["id"]
        assert g["fila"] in {"Financeiro", "Suporte", "Vendas", "Triagem humana", "Retenção"}
        if p["grupo"] != "responde":
            assert g["chamar_pessoa"], p["id"]
        if not g["artigos"]:
            assert g["fato"] is None, p["id"]


def test_dados_pessoais_de_teste_saem_no_mascaramento():
    for p in PERGUNTAS:
        mascarada = mascarar(p["pergunta"]).texto
        for dado in p["dados_pessoais"]:
            assert dado in p["pergunta"], p["id"]
            assert dado not in mascarada, p["id"]
