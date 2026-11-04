"""Página de demonstração e rota pública /demo/triagem."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.banco import ChamadoRegistro
from tests.falsos import ClienteFalso, entrada_valida

TEXTO_COM_CPF = "Fui cobrado duas vezes pelo pedido 458812. Meu CPF é 529.982.247-25."


def test_pagina_abre_com_politica_de_seguranca(abrir_api):
    resposta = abrir_api().get("/")
    assert resposta.status_code == 200
    assert "Triagem de chamados com IA" in resposta.text
    politica = resposta.headers["content-security-policy"]
    assert "default-src 'self'" in politica
    assert "frame-ancestors 'none'" in politica
    # Sem endereço público configurado, não há prévia de link.
    assert "og:url" not in resposta.text


def test_pagina_com_endereco_publico_tem_previa_do_link(abrir_api):
    resposta = abrir_api(url_publica="https://triagem.exemplo.com/").get("/")
    assert '<meta property="og:url" content="https://triagem.exemplo.com/">' in resposta.text


def test_endereco_publico_nao_injeta_html_na_pagina(abrir_api):
    resposta = abrir_api(url_publica='https://x.com/"><script>alert(1)</script>').get("/")
    assert "<script>alert(1)</script>" not in resposta.text


def test_arquivos_da_pagina_sao_servidos(abrir_api):
    api = abrir_api()
    assert api.get("/estatico/demo.css").status_code == 200
    assert api.get("/estatico/demo.js").status_code == 200
    fonte = api.get("/estatico/fontes/atkinson-hyperlegible-latin-400-normal.woff2")
    assert fonte.status_code == 200
    assert fonte.headers["content-type"] == "font/woff2"


def test_triagem_de_demonstracao_responde_e_nao_grava_nada(abrir_api, motor):
    api = abrir_api(chave_api="segredo-de-teste")
    # Aberta ao público: não precisa da chave X-API-Key.
    resposta = api.post("/demo/triagem", json={"texto": TEXTO_COM_CPF, "canal": "email"})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["origem"] == "ia"
    assert corpo["fila"] == "Financeiro"
    assert corpo["texto_mascarado"].endswith("Meu CPF é [CPF].")
    assert "529.982.247-25" not in resposta.text
    with Session(motor) as sessao:
        assert sessao.scalar(select(func.count()).select_from(ChamadoRegistro)) == 0


def test_demonstracao_tem_limite_por_pessoa(abrir_api):
    api = abrir_api(demo_limite_por_hora=2)
    for _ in range(2):
        assert api.post("/demo/triagem", json={"texto": "oi"}).status_code == 200
    bloqueada = api.post("/demo/triagem", json={"texto": "oi"})
    assert bloqueada.status_code == 429
    assert "limite" in bloqueada.json()["detail"]


def test_demonstracao_tem_limite_por_dia(abrir_api):
    api = abrir_api(demo_limite_por_hora=100, demo_limite_por_dia=1)
    assert api.post("/demo/triagem", json={"texto": "oi"}).status_code == 200
    bloqueada = api.post("/demo/triagem", json={"texto": "oi"})
    assert bloqueada.status_code == 429
    assert "hoje" in bloqueada.json()["detail"]


def test_demonstracao_desligada_nao_responde(abrir_api):
    api = abrir_api(demo_ativa=False)
    assert api.post("/demo/triagem", json={"texto": "oi"}).status_code == 404


def test_demonstracao_aceita_no_maximo_mil_caracteres(abrir_api):
    api = abrir_api()
    assert api.post("/demo/triagem", json={"texto": "a" * 1001}).status_code == 422
    assert api.post("/demo/triagem", json={"texto": "a" * 1000}).status_code == 200


def test_demonstracao_mostra_quando_vai_para_revisao(abrir_api):
    api = abrir_api(cliente_ia=ClienteFalso(entrada_valida(prioridade="urgente")))
    corpo = api.post("/demo/triagem", json={"texto": TEXTO_COM_CPF}).json()
    assert corpo["prioridade"] == "urgente"
    assert corpo["revisao_humana"] is True
    assert corpo["motivos_revisao"]
