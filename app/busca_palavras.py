"""Busca por palavras: BM25 em Python puro, sem dependência nova.

O português é tratado antes da conta:
- minúsculas e comparação sem acento ("Cartão" e "cartao" são a mesma palavra);
- palavras vazias fora ("de", "o", "pra", "vc"...), inclusive as do jeito informal;
- uma redução simples de plural ("vendas" vira "venda", "cartões" vira "cartao"),
  para a pergunta no singular achar o artigo no plural.

A busca por palavras não entende sinônimo nem erro de digitação: "maqininha" não acha
"maquininha". Isso fica com a busca por sentido (app/busca_sentido.py).
"""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable

# Escritas sem acento, do jeito que saem de normalizar().
_LISTA_PALAVRAS_VAZIAS = """
a o as os um uma uns umas ao aos
de do da dos das em no na nos nas num numa por pelo pela pelos pelas
para pra pro pras pros com sem sob sobre ate apos entre
e ou mas nem se que quem qual quais como quando onde porque pq oq q
eu tu ele ela nos vos eles elas me mim te ti lhe lhes
meu minha meus minhas seu sua seus suas teu tua nosso nossa nossos nossas
voce voces vc vcs ce isso isto aquilo esse essa esses essas este esta estes estas
aquele aquela aqueles aquelas ja nao sim muito muita mais menos tambem tb tbm so
ser sou era foi fui sao estar estou estava ta to tava ter tem tenho tinha
ha vai vou fazer faz faco fiz pode posso consigo quero queria preciso
oi ola ai aqui ali la entao tipo ne ok gente coisa ainda
"""
PALAVRAS_VAZIAS = frozenset(_LISTA_PALAVRAS_VAZIAS.split())

_TOKEN = re.compile(r"[a-z0-9]+")


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento: "Cartão" vira "cartao"."""
    decomposto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def reduzir_plural(palavra: str) -> str:
    """Tira o plural mais comum. Não é um radicalizador completo, e nem precisa ser:
    pergunta e artigo passam pela mesma regra, então o importante é ser consistente."""
    if len(palavra) <= 3 or not palavra.endswith("s"):
        return palavra
    if palavra.endswith("oes"):  # cartoes -> cartao
        return palavra[:-3] + "ao"
    if palavra.endswith("ais"):  # reais -> real, mensais -> mensal
        return palavra[:-3] + "al"
    if palavra.endswith("eis") and len(palavra) > 4:  # uteis -> util
        return palavra[:-3] + "il"
    if palavra.endswith("ns"):  # itens -> item
        return palavra[:-2] + "m"
    if palavra.endswith(("res", "zes", "ses")) and len(palavra) > 4:  # valores -> valor
        return palavra[:-2]
    if palavra.endswith(("is", "us", "ss")):  # depois, bonus: ficam
        return palavra
    return palavra[:-1]  # vendas -> venda


def tokenizar(texto: str) -> list[str]:
    """Quebra o texto em palavras normalizadas, sem as vazias e sem as de uma letra."""
    tokens = []
    for palavra in _TOKEN.findall(normalizar(texto)):
        if len(palavra) < 2 or palavra in PALAVRAS_VAZIAS:
            continue
        tokens.append(reduzir_plural(palavra))
    return tokens


class BuscaPalavras:
    """Okapi BM25 com os parâmetros de costume (k1 = 1,5 e b = 0,75).

    A nota de cada documento soma, para cada palavra da pergunta (sem repetir), o peso da
    palavra (raras pesam mais) vezes quanto ela aparece no documento, com desconto para
    documento comprido.
    """

    def __init__(self, documentos: Iterable[tuple[str, str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._frequencias: dict[str, Counter[str]] = {}
        self._tamanhos: dict[str, int] = {}
        for id_documento, texto in documentos:
            tokens = tokenizar(texto)
            self._frequencias[id_documento] = Counter(tokens)
            self._tamanhos[id_documento] = len(tokens)
        if not self._frequencias:
            raise ValueError("a busca por palavras precisa de pelo menos um documento")
        total = len(self._frequencias)
        self._tamanho_medio = sum(self._tamanhos.values()) / total
        em_quantos: Counter[str] = Counter()
        for frequencias in self._frequencias.values():
            em_quantos.update(frequencias.keys())
        self._peso = {
            palavra: math.log(1 + (total - n + 0.5) / (n + 0.5))
            for palavra, n in em_quantos.items()
        }

    def notas(self, pergunta: str) -> list[tuple[str, float]]:
        """Os documentos com alguma palavra da pergunta, da maior nota para a menor.

        Empate fica na ordem do id, para o resultado não mudar de uma rodada para outra.
        """
        palavras = [p for p in dict.fromkeys(tokenizar(pergunta)) if p in self._peso]
        resultado = []
        for id_documento, frequencias in self._frequencias.items():
            desconto = 1 - self.b + self.b * self._tamanhos[id_documento] / self._tamanho_medio
            nota = 0.0
            for palavra in palavras:
                vezes = frequencias.get(palavra, 0)
                if vezes:
                    nota += (
                        self._peso[palavra] * vezes * (self.k1 + 1) / (vezes + self.k1 * desconto)
                    )
            if nota > 0:
                resultado.append((id_documento, nota))
        resultado.sort(key=lambda par: (-par[1], par[0]))
        return resultado
