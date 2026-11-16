"""Datas em português, com o dia da semana, e dias úteis contados em Python.

A IA não faz conta de data: as ferramentas e a mensagem já levam as datas calculadas aqui,
do jeito que o lojista lê ("segunda, 16/11/2026"). Dia útil é de segunda a sexta. Feriado
fica de fora: os dados da demonstração são inventados.

As regras de prazo são as dos artigos (base/artigos/recebimentos-e-prazos.md).
"""

from datetime import date, datetime, timedelta

DIAS_DA_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


def por_extenso(dia: date) -> str:
    """Ex.: "segunda, 16/11/2026"."""
    return f"{DIAS_DA_SEMANA[dia.weekday()]}, {dia:%d/%m/%Y}"


def momento_por_extenso(momento: datetime) -> str:
    """Ex.: "quarta, 11/11/2026, 10:00"."""
    return f"{por_extenso(momento.date())}, {momento:%H:%M}"


def e_dia_util(dia: date) -> bool:
    return dia.weekday() < 5


def proximo_dia_util(dia: date) -> date:
    """O próprio dia, se for útil; senão, a segunda seguinte."""
    while not e_dia_util(dia):
        dia += timedelta(days=1)
    return dia


def somar_dias_uteis(dia: date, quantos: int) -> date:
    """Ex.: sexta + 1 dia útil = segunda."""
    for _ in range(quantos):
        dia = proximo_dia_util(dia + timedelta(days=1))
    return dia


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Quantos dias úteis há depois de `inicio` até `fim`, contando o próprio `fim`."""
    total, dia = 0, inicio
    while dia < fim:
        dia += timedelta(days=1)
        total += e_dia_util(dia)
    return total


def data_prevista(plano: str, forma: str, data_venda: date) -> date:
    """Quando o dinheiro de uma venda cai, pelas regras do plano.

    - Pix: na hora, nos dois planos.
    - Plano Mensal, crédito à vista e parcelado: 30 dias depois da venda (a 1ª parcela, no
      parcelado); se cair em fim de semana, no próximo dia útil.
    - O resto (débito nos dois planos; tudo no Plano Na Hora): 1 dia útil depois da venda.
    """
    if forma == "pix":
        return data_venda
    if plano == "Plano Mensal" and forma in ("credito", "parcelado"):
        return proximo_dia_util(data_venda + timedelta(days=30))
    return somar_dias_uteis(data_venda, 1)


def prazos_a_partir_de(hoje: date) -> dict[str, str]:
    """Os prazos dos artigos contados a partir de hoje, para perguntas como "se eu vender
    hoje, quando cai?". Assim a IA não precisa calcular."""
    trinta = hoje + timedelta(days=30)
    texto_trinta = por_extenso(proximo_dia_util(trinta))
    if not e_dia_util(trinta):
        texto_trinta += f" ({trinta:%d/%m} é {DIAS_DA_SEMANA[trinta.weekday()]})"
    return {"1 dia útil": por_extenso(somar_dias_uteis(hoje, 1)), "30 dias": texto_trinta}


def ha_quanto_tempo(minutos: int) -> str:
    """Ex.: "5 minutos", "25 horas", "2 dias"."""
    if minutos < 60:
        return f"{minutos} minuto{'s' if minutos != 1 else ''}"
    horas = minutos // 60
    if horas < 48:
        return f"{horas} hora{'s' if horas != 1 else ''}"
    dias = horas // 24
    return f"{dias} dias"
