"""Conversão da grade do dataset (vários sistemas) para a grade brasileira.

A origem aplica a grade-modelo inteira de cada sistema a todo produto (todo calçado EU vai de 34 a 46 com
meio número, inclusive o masculino; toda roupa numérica vai de 34 a 58). Por isso esta conversão é uma
**convenção da demo**, documentada, e não tabela de fabricante: converte para o número brasileiro, junta os
tamanhos que caem no mesmo número BR (o SKU convertido fica em estoque se algum dos originais estava) e corta
o que fica fora da faixa usual do varejo brasileiro.

Referências consultadas em 07/10/2026 (divergem entre si; ver README do catálogo): tabela de calçados da Nike
Brasil (US → BR), Schutz (IT → BR), guia de medidas da Levi's Brasil (jeans), Nike Brasil (letras).
"""

import math
from collections.abc import Callable

UNICO = "U"

LETRAS = {"XS": "PP", "S": "P", "M": "M", "L": "G", "XL": "GG", "XXL": "XGG"}  # XXS e XXXL saem
LETRAS_ORDEM = ["PP", "P", "M", "G", "GG", "XGG"]

# Tabela de calçados da Nike Brasil (US → BR); meio número BR arredonda para baixo
US_CALCADO = {
    "masculino": {5: 35.5, 6: 37, 7: 38, 7.5: 39, 8: 39.5, 8.5: 40, 9: 40.5, 9.5: 41, 10: 42, 10.5: 42.5,
                  11: 43, 11.5: 43.5, 12: 44, 12.5: 45, 13: 46},
    "feminino": {5: 33.5, 6: 35, 7: 36, 7.5: 37, 8: 37.5, 8.5: 38, 9: 39, 10: 40, 10.5: 41, 11: 41.5, 12: 43},
}  # fmt: skip
FAIXA_CALCADO = {"feminino": (33, 40), "masculino": (37, 44)}

# Guia de medidas da Levi's Brasil (masculino), aplicado aos dois gêneros
JEANS = {28: 36, 29: 37, 30: 38, 31: 39, 32: 40, 33: 42, 34: 44, 35: 45, 36: 46, 38: 48, 40: 50, 42: 52}

# Numeração própria de marcas italianas (Moncler, Majestic Filatures...): 0 = XS
ITALIANA_0_7 = {"0": "PP", "1": "P", "2": "M", "3": "G", "4": "GG", "5": "XGG"}


def _sistema(grade: list[str], categoria: str) -> str:
    g = set(grade)
    if g == {"one size"}:
        return "unico"
    if g & set(LETRAS) or "XXS" in g:
        return "letras"
    if "Shoes" in categoria:
        return "calcado_us" if "5.5" in g or max(map(float, g)) <= 13 else "calcado_eu"
    if "14.5" in g:
        return "colarinho"
    if g >= {"70", "75"}:
        return "cinto"
    if g >= {"24", "25"}:
        return "jeans"
    if g >= {"0", "1", "2"}:
        return "italiana_0_7"
    if g >= {"0", "2", "4"}:
        return "us_feminina"
    if g >= {"36", "37", "38"}:
        return "colarinho_cm"
    if g >= {"34", "36", "38"}:
        return "europeia"
    raise ValueError(f"grade sem sistema conhecido: {sorted(g)}")


def _fmt(n: float) -> str:
    return str(int(n))


def conversor(grade: list[str], categoria: str, genero: str) -> Callable[[str], str | None]:
    """Devolve a função tamanho de origem → tamanho BR (None = fora da faixa, o SKU sai do catálogo)."""
    sistema = _sistema(grade, categoria)

    def calcado(br: float) -> str | None:
        lo, hi = FAIXA_CALCADO[genero]
        br = math.floor(br)
        return _fmt(br) if lo <= br <= hi else None

    match sistema:
        case "unico":
            return lambda _t: UNICO
        case "letras":
            return LETRAS.get
        case "calcado_eu":
            desconto = 1 if genero == "feminino" else 2
            return lambda t: calcado(float(t) - desconto)
        case "calcado_us":
            tabela = US_CALCADO[genero]
            return lambda t: calcado(tabela[float(t)]) if float(t) in tabela else None
        case "colarinho":
            return lambda t: _fmt(round(float(t) * 2.54))
        case "colarinho_cm" | "cinto":
            return lambda t: t
        case "jeans":
            return lambda t: _fmt(JEANS[int(t)]) if int(t) in JEANS else None
        case "italiana_0_7":
            return ITALIANA_0_7.get
        case "us_feminina":
            return lambda t: _fmt(int(t) + 34) if int(t) + 34 <= 48 else None
        case "europeia":
            if genero == "feminino":
                return lambda t: _fmt(int(t) + 2) if int(t) + 2 <= 48 else None
            return lambda t: _fmt(int(t) - 8) if int(t) - 8 >= 36 else None
    raise AssertionError(sistema)


def ordem(tamanho: str) -> tuple[int, float]:
    """Chave de ordenação da grade BR: letras na ordem PP…XGG, números crescentes, U no fim."""
    if tamanho in LETRAS_ORDEM:
        return (0, LETRAS_ORDEM.index(tamanho))
    if tamanho == UNICO:
        return (2, 0)
    return (1, float(tamanho))
