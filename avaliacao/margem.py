"""A margem de erro de uma taxa medida em poucas perguntas.

Por que existe: "11 de 21" parece um número firme, mas 21 perguntas são uma amostra pequena.
Com outras 21 perguntas do mesmo tipo, o resultado podia ser bem diferente. A margem mostra
essa faixa ao lado do número, para ninguém ler 52% como se fosse exato.

O método é o intervalo de Wilson, com 95% de confiança. Ele foi escolhido no lugar da conta
mais simples (p ± 1,96·√(p(1-p)/n)) porque a conta simples falha justo nos nossos casos:
- com 0 ou com todos certos (0/7, 8/8), ela dá uma faixa de largura zero, como se fosse certeza;
- com taxas pequenas (2/40), ela dá um limite de baixo negativo.
O Wilson fica sempre entre 0% e 100% e é o recomendado para amostras pequenas.

Uma ressalva que vale para a leitura: a prova rodou 3 vezes, mas são as mesmas perguntas.
Repetir a rodada mede a variação da IA, não a das perguntas. Por isso a margem usa o número de
perguntas (21, 40), nunca o de rodadas vezes perguntas.
"""

from math import sqrt

# 1,96 é o valor da curva normal para 95% de confiança (2,5% de cada lado).
Z_95 = 1.96


def intervalo_wilson(parte: int, todo: int, z: float = Z_95) -> tuple[float, float]:
    """A faixa (de, até), entre 0 e 1, onde a taxa verdadeira deve estar com 95% de confiança."""
    if todo <= 0:
        raise ValueError("o total precisa ser maior que zero")
    if not 0 <= parte <= todo:
        raise ValueError("a parte precisa estar entre 0 e o total")
    p = parte / todo
    z2 = z * z
    denominador = 1 + z2 / todo
    centro = (p + z2 / (2 * todo)) / denominador
    meia_largura = z * sqrt(p * (1 - p) / todo + z2 / (4 * todo * todo)) / denominador
    # O arredondamento do ponto flutuante pode passar um fio de 0 ou de 1.
    return max(0.0, centro - meia_largura), min(1.0, centro + meia_largura)


def faixa_em_texto(parte: int, todo: int) -> str:
    """A faixa em porcentagem inteira, para relatório: "de 32% a 72%"."""
    de, ate = intervalo_wilson(parte, todo)
    return f"de {de:.0%} a {ate:.0%}"
