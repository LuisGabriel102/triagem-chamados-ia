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
    "prazo_documentos",
    "observacao",
)
CAMPOS_DA_MAQUININHA = ("apelido", "modelo", "situacao", "ultima_conexao", "observacao")


class LojistaDesconhecido(KeyError):
    """O lojista da sessão não está nos dados."""


def proximo_dia_util(dia: date) -> date:
    """Sábado e domingo passam para segunda (feriado não entra nos dados inventados)."""
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    return dia


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

    def existe(self, lojista_id: str) -> bool:
        return lojista_id in self._lojistas

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
            venda["data_venda"] = (hoje + timedelta(days=bruta["venda_em_dias"])).isoformat()
            prevista = hoje + timedelta(days=bruta["previsto_em_dias"])
            venda["data_prevista"] = proximo_dia_util(prevista).isoformat()
            venda["valor_liquido"] = round(
                bruta["valor_bruto"] * (1 - bruta["taxa_percentual"] / 100), 2
            )
            if "prazo_documentos_em_dias" in bruta:
                prazo = hoje + timedelta(days=bruta["prazo_documentos_em_dias"])
                venda["prazo_documentos"] = prazo.isoformat()
            vendas.append({campo: venda[campo] for campo in CAMPOS_DA_VENDA if campo in venda})
        return {
            "hoje": hoje.isoformat(),
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
            maquininha["ultima_conexao"] = momento.strftime("%Y-%m-%d %H:%M")
            maquininhas.append(
                {campo: maquininha[campo] for campo in CAMPOS_DA_MAQUININHA if campo in maquininha}
            )
        return {"agora": agora.strftime("%Y-%m-%d %H:%M"), "maquininhas": maquininhas}

    def executar(self, nome: str, lojista_id: str) -> dict[str, Any]:
        """Roda a ferramenta pedida pela IA para o lojista da sessão."""
        if nome == "consultar_recebimentos":
            return self.consultar_recebimentos(lojista_id)
        if nome == "status_maquininha":
            return self.status_maquininha(lojista_id)
        raise ValueError(f"ferramenta desconhecida: {nome}")
