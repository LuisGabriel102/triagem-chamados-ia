"""O kit da calibração do juiz: o sorteio, a página sem veredito e a comparação."""

import json

import pytest

from avaliacao import calibrar_juiz as cj


def _linha(id_, certa, rodada="dev_v2_mudanca3", resposta="Resposta."):
    return {
        "id": id_,
        "rodada": rodada,
        "juiz": {"certa": certa, "julgou": True, "pelo_juiz": True},
        "resposta": resposta,
    }


def test_sorteio_metade_e_metade_sem_repetir_pergunta():
    linhas = [_linha(f"a{i:02d}", i % 3 != 0) for i in range(60)]
    # A mesma pergunta em outra rodada da mesma prova não pode entrar duas vezes.
    linhas += [_linha(f"a{i:02d}", i % 3 != 0, rodada="dev_v2_outra") for i in range(60)]
    escolhidas = cj.sortear(linhas, por_lado=10)
    assert len(escolhidas) == 20
    assert sum(x["juiz"]["certa"] for x in escolhidas) == 10
    assert len({x["id"] for x in escolhidas}) == 20


def test_sorteio_e_sempre_o_mesmo():
    linhas = [_linha(f"a{i:02d}", i % 2 == 0) for i in range(40)]
    primeira = [x["id"] for x in cj.sortear(linhas, por_lado=5)]
    segunda = [x["id"] for x in cj.sortear(linhas, por_lado=5)]
    assert primeira == segunda


def _caso(numero, resposta="Resposta <b>com</b> sinal & coisa."):
    return {
        "caso": f"c{numero:02d}",
        "pergunta": "Pergunta <script>alert(1)</script>",
        "gabarito": {"fato_esperado": "x"},
        "artigos": [{"id": "pix", "titulo": "Pix", "texto": "Texto do artigo."}],
        "dados_da_loja": {"status_maquininha": []},
        "resposta": resposta,
        "nota_mensagem_fixa": False,
    }


def test_pagina_escapa_o_texto_e_nao_traz_veredito():
    pagina = cj.montar_pagina([_caso(1)])
    assert "<script>alert(1)</script>" not in pagina
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in pagina
    assert "&lt;b&gt;com&lt;/b&gt;" in pagina
    # Nada do juiz entra na página.
    assert "juiz aprovou" not in pagina.lower()
    assert '"certa"' not in pagina
    for criterio in cj.CRITERIOS:
        assert f'name="c01-{criterio}"' in pagina


def test_kappa_de_cohen():
    # Concordância perfeita com os dois lados presentes: kappa 1.
    assert cj.kappa_de_cohen([(True, True), (False, False)]) == pytest.approx(1.0)
    # Exemplo de livro: 20 pares, 15 iguais.
    pares = [(True, True)] * 10 + [(False, False)] * 5 + [(True, False)] * 3 + [(False, True)] * 2
    # observada 0,75; esperada 0,65·0,60 + 0,35·0,40 = 0,53; kappa = 0,22/0,47.
    assert cj.kappa_de_cohen(pares) == pytest.approx(0.22 / 0.47)
    # Todos iguais e todos "sim": o acaso explica tudo, não dá para calcular.
    assert cj.kappa_de_cohen([(True, True)] * 5) is None
    assert cj.kappa_de_cohen([]) is None


def test_comparar_e_relatorio():
    vereditos = [
        {
            "caso": "c01",
            "rodada": "prova2_1",
            "id": "q01",
            "juiz": {
                "correta": True,
                "completa": True,
                "fiel_a_fonte": True,
                "sem_inventar": True,
                "certa": True,
                "comentario": "Tudo certo.",
            },
        },
        {
            "caso": "c02",
            "rodada": "prova2_1",
            "id": "q02",
            "juiz": {
                "correta": True,
                "completa": False,
                "fiel_a_fonte": True,
                "sem_inventar": True,
                "certa": False,
                "comentario": "Faltou a data.",
            },
        },
        {"caso": "c03", "rodada": "prova2_1", "id": "q03", "juiz": {"certa": True}},
    ]
    sim = dict.fromkeys(cj.CRITERIOS, True)
    marcacoes = {
        "c01": {**sim, "sem_inventar": False, "comentario": "Inventou um prazo."},
        "c02": {**sim, "completa": False, "comentario": ""},
        "c03": {**sim, "correta": None},  # incompleto: fica de fora
    }
    r = cj.comparar(vereditos, marcacoes)
    assert r["marcados"] == 2
    assert r["incompletos"] == ["c03"]
    assert r["certa"]["iguais"] == 1
    assert r["certa"]["juiz_sim_pessoa_nao"] == 1
    assert [x["caso"] for x in r["discordancias"]] == ["c01"]
    texto = cj.relatorio(r)
    assert "Inventou um prazo." in texto
    assert "Tudo certo." in texto
    assert "c03" in texto


def test_kit_gravado_bate_com_os_resultados():
    """O casos.json versionado tem 30 casos, 15 de cada lado, e a página não tem veredito."""
    vereditos = json.loads((cj.PASTA / "casos.json").read_text("utf-8"))
    assert len(vereditos) == 30
    assert sum(v["juiz"]["certa"] for v in vereditos) == 15
    pagina = (cj.PASTA / "marcar.html").read_text("utf-8")
    for v in vereditos:
        assert v["juiz"]["comentario"] not in pagina
