"""As ferramentas do agente: consultam os dados do lojista da sessão.

Regras de segurança:
- O lojista vem da sessão, nunca do texto. As ferramentas não têm parâmetro de lojista:
  a IA não escolhe de quem é o dado.
- A IA não recebe CPF, CNPJ, número de conta, e-mail nem telefone. A saída tem só os
  campos de uma lista fechada; o resto do cadastro nunca sai deste módulo.

Os dados são inventados (dados/lojistas.json). Os dias são contados a partir de hoje, para
a demonstração não envelhecer.
"""

import json
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.datas import (
    data_prevista,
    dias_uteis_entre,
    ha_quanto_tempo,
    momento_por_extenso,
    por_extenso,
)

ARQUIVO_LOJISTAS = Path(__file__).resolve().parent.parent / "dados" / "lojistas.json"
MAX_CHAMADAS_DE_FERRAMENTA = 3

# Formato estrito, sem parâmetro nenhum: a ferramenta sempre olha o lojista da sessão.
_SEM_PARAMETROS: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}

FERRAMENTAS_DE_DADOS: list[dict[str, Any]] = [
    {
        "name": "consultar_recebimentos",
        "description": (
            "Lista as vendas recentes do lojista desta conversa: valor bruto, taxa, valor "
            "líquido, data prevista para cair e situação (a_receber, pago, em_analise, "
            "retido_contestacao, cancelada). Também diz o plano do lojista e a data de hoje. "
            "Use quando a pergunta for sobre o dinheiro das vendas dele."
        ),
        "strict": True,
        "input_schema": _SEM_PARAMETROS,
    },
    {
        "name": "status_maquininha",
        "description": (
            "Lista as maquininhas do lojista desta conversa, com a situação de cada uma "
            "(ligada, sem_conexao, bloqueada) e a última conexão. Use quando a pergunta for "
            "sobre uma maquininha dele."
        ),
        "strict": True,
        "input_schema": _SEM_PARAMETROS,
    },
]
NOMES_DAS_FERRAMENTAS = frozenset(f["name"] for f in FERRAMENTAS_DE_DADOS)

# A lista fechada do que pode sair para a IA.
CAMPOS_DA_VENDA = (
    "venda",
    "data_venda",
    "forma",
    "parcelas",
    "valor_bruto",
    "taxa_percentual",
    "valor_liquido",
    "data_prevista",
    "situacao",
    "quando",
    "prazo_documentos",
    "dias_ate_o_prazo_documentos",
    "observacao",
)
CAMPOS_DA_MAQUININHA = (
    "apelido",
    "modelo",
    "situacao",
    "ultima_conexao",
    "ultima_conexao_ha",
    "observacao",
)


class LojistaDesconhecido(KeyError):
    """O lojista da sessão não está nos dados."""


def _quando(situacao: str, prevista: date, hoje: date) -> str:
    """A situação da data, já calculada: a IA só repete."""
    if situacao == "pago":
        return f"caiu na {por_extenso(prevista)}"
    if situacao == "retido_contestacao":
        return "bloqueado até a decisão da contestação"
    if situacao == "cancelada":
        return "venda cancelada: não gera pagamento"
    if situacao == "em_analise":
        return f"em análise; se for liberada, cai na {por_extenso(prevista)}"
    if prevista <= hoje:
        return "cai hoje, até as 18h"
    uteis = dias_uteis_entre(hoje, prevista)
    if uteis == 1:
        return f"cai no próximo dia útil: {por_extenso(prevista)}"
    return f"cai na {por_extenso(prevista)}, daqui a {(prevista - hoje).days} dias"


class DadosLojistas:
    def __init__(
        self,
        caminho: Path = ARQUIVO_LOJISTAS,
        agora: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._lojistas: dict[str, dict[str, Any]] = json.loads(caminho.read_text("utf-8"))[
            "lojistas"
        ]
        self._agora = agora

    def hoje(self) -> date:
        return self._agora().date()

    def existe(self, lojista_id: str) -> bool:
        return lojista_id in self._lojistas

    def vitrine(self) -> list[dict[str, str]]:
        """As lojas para a página de demonstração escolher: só o id, o nome e o plano.
        Documento, conta, e-mail e telefone nunca saem daqui."""
        return [
            {"id": id_, "nome": dados["nome_fantasia"], "plano": dados["plano"]}
            for id_, dados in self._lojistas.items()
        ]

    def _lojista(self, lojista_id: str) -> dict[str, Any]:
        try:
            return self._lojistas[lojista_id]
        except KeyError as erro:
            raise LojistaDesconhecido(lojista_id) from erro

    def consultar_recebimentos(self, lojista_id: str) -> dict[str, Any]:
        lojista = self._lojista(lojista_id)
        hoje = self._agora().date()
        vendas = []
        for bruta in lojista["vendas"]:
            venda = dict(bruta)
            vendida = hoje + timedelta(days=bruta["venda_em_dias"])
            prevista = data_prevista(lojista["plano"], bruta["forma"], vendida)
            venda["data_venda"] = por_extenso(vendida)
            venda["data_prevista"] = por_extenso(prevista)
            venda["quando"] = _quando(bruta["situacao"], prevista, hoje)
            venda["valor_liquido"] = round(
                bruta["valor_bruto"] * (1 - bruta["taxa_percentual"] / 100), 2
            )
            if "prazo_documentos_em_dias" in bruta:
                prazo = hoje + timedelta(days=bruta["prazo_documentos_em_dias"])
                venda["prazo_documentos"] = por_extenso(prazo)
                venda["dias_ate_o_prazo_documentos"] = bruta["prazo_documentos_em_dias"]
            vendas.append({campo: venda[campo] for campo in CAMPOS_DA_VENDA if campo in venda})
        return {
            "hoje": por_extenso(hoje),
            "plano": lojista["plano"],
            "valores_em": "reais",
            "vendas": vendas,
        }

    def status_maquininha(self, lojista_id: str) -> dict[str, Any]:
        lojista = self._lojista(lojista_id)
        agora = self._agora()
        maquininhas = []
        for bruta in lojista["maquininhas"]:
            maquininha = dict(bruta)
            momento = agora - timedelta(minutes=bruta["ultima_conexao_em_minutos"])
            maquininha["ultima_conexao"] = momento_por_extenso(momento)
            maquininha["ultima_conexao_ha"] = ha_quanto_tempo(bruta["ultima_conexao_em_minutos"])
            maquininhas.append(
                {campo: maquininha[campo] for campo in CAMPOS_DA_MAQUININHA if campo in maquininha}
            )
        return {"agora": momento_por_extenso(agora), "maquininhas": maquininhas}

    def executar(self, nome: str, lojista_id: str) -> dict[str, Any]:
        """Roda a ferramenta pedida pela IA para o lojista da sessão."""
        if nome == "consultar_recebimentos":
            return self.consultar_recebimentos(lojista_id)
        if nome == "status_maquininha":
            return self.status_maquininha(lojista_id)
        raise ValueError(f"ferramenta desconhecida: {nome}")
