"""Avaliador das expectativas do golden set (sem rede; recebe a resposta da Algolia já decodificada).

Uma expectativa é uma propriedade semântica verificável no próprio hit ou contra o catálogo local
(`data/algolia/registros.json`, os records que o conector indexou). Nunca vem do ranking atual do índice: o
esperado não pode sair da fonte que se quer testar.

Tipos de expectativa (campo `tipo`):

- `nb_hits`: `nbHits` comparado a um número fixo (`igual`, `min`, `max`).
- `nb_hits_catalogo`: `nbHits` comparado (`igual` ou `min`) à contagem de records do catálogo que atendem à
  `regra`. Use `igual` só quando a regra reproduz a busca sem ambiguidade (consulta vazia com filtro), e `min`
  quando a busca textual pode trazer a mais (descrição que cita a palavra).
- `recall_catalogo`: todo record do catálogo que atende à `regra` aparece nos hits devolvidos (a consulta
  precisa de `hitsPerPage` suficiente; se a página não cobre `nbHits`, falha dizendo isso).
- `todos` / `algum` / `nenhum`: a `condicao` vale para todos, algum ou nenhum dos `primeiros` N hits (todos os
  devolvidos se N faltar). `todos` e `algum` **falham com zero hits**: um verde vazio não prova nada
  (`permitir_vazio: true` para aceitar).
- `ordenado`: o `campo` está em ordem `asc` (não decrescente) ou `desc` (não crescente) nos hits devolvidos.
- `invariante`: regra entre campos do mesmo hit (`estoque_coerente`, `promocao_coerente`,
  `tamanhos_na_grade`).

Condição: `{"campo": "categorias.lvl2", "op": "termina_com", "valor": "Tênis"}`, ou composição com
`{"qualquer": [...]}`, `{"todas": [...]}` e `{"nao": {...}}`. O campo `_pesquisavel` é o texto dos
`searchableAttributes` do índice (de `ingest/config/indice.json`), concatenado.
"""

import json
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

INDICE_JSON = Path(__file__).resolve().parent.parent / "ingest" / "config" / "indice.json"
_AUSENTE = object()


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento: "Tênis" e "tenis" viram a mesma coisa."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def _atributos_pesquisaveis(caminho: Path = INDICE_JSON) -> list[str]:
    settings = json.loads(caminho.read_text(encoding="utf-8"))
    return [re.sub(r"^unordered\((.*)\)$", r"\1", a) for a in settings["searchableAttributes"]]


ATRIBUTOS_PESQUISAVEIS = _atributos_pesquisaveis()


def valor_campo(hit: dict, campo: str):
    if campo == "_pesquisavel":
        partes = [valor_campo(hit, a) for a in ATRIBUTOS_PESQUISAVEIS]
        return " ".join(str(p) for p in partes if p is not _AUSENTE and p is not None)
    atual = hit
    for parte in campo.split("."):
        if not isinstance(atual, dict) or parte not in atual:
            return _AUSENTE
        atual = atual[parte]
    return atual


def _palavras(valor) -> set[str]:
    textos = valor if isinstance(valor, list) else [valor]
    return {p for t in textos if isinstance(t, str) for p in re.findall(r"[a-z0-9]+", normalizar(t))}


def _como_lista(valor) -> list:
    return valor if isinstance(valor, list) else [valor]


def _op_contem_palavra(atual, esperado) -> bool:
    palavras = _palavras(atual)
    return any(normalizar(e) in palavras for e in _como_lista(esperado))


def _numero(atual) -> float | None:
    return atual if isinstance(atual, int | float) and not isinstance(atual, bool) else None


OPERADORES: dict[str, Callable[[object, object], bool]] = {
    "igual": lambda a, v: a == v,
    "em": lambda a, v: a in v,
    "comeca_com": lambda a, v: isinstance(a, str) and a.startswith(v),
    "termina_com": lambda a, v: isinstance(a, str) and a.endswith(v),
    "inclui": lambda a, v: isinstance(a, list) and v in a,
    "contem_palavra": _op_contem_palavra,
    "menor_igual": lambda a, v: _numero(a) is not None and a <= v,
    "maior_igual": lambda a, v: _numero(a) is not None and a >= v,
    "presente": lambda a, v: True,
}


def condicao_ok(hit: dict, cond: dict) -> bool:
    if "qualquer" in cond:
        return any(condicao_ok(hit, c) for c in cond["qualquer"])
    if "todas" in cond:
        return all(condicao_ok(hit, c) for c in cond["todas"])
    if "nao" in cond:
        return not condicao_ok(hit, cond["nao"])
    op = cond["op"]
    if op not in OPERADORES:
        raise ValueError(f"operador desconhecido: {op}")
    atual = valor_campo(hit, cond["campo"])
    if atual is _AUSENTE:
        return False
    return OPERADORES[op](atual, cond.get("valor"))


def descrever_condicao(cond: dict) -> str:
    if "qualquer" in cond:
        return "(" + " ou ".join(descrever_condicao(c) for c in cond["qualquer"]) + ")"
    if "todas" in cond:
        if not cond["todas"]:
            return "(todo o catálogo)"
        return "(" + " e ".join(descrever_condicao(c) for c in cond["todas"]) + ")"
    if "nao" in cond:
        return f"não {descrever_condicao(cond['nao'])}"
    valor = "" if cond["op"] == "presente" else f" {json.dumps(cond.get('valor'), ensure_ascii=False)}"
    return f"{cond['campo']} {cond['op']}{valor}"


def _rotulo(hit: dict) -> str:
    return f"{hit.get('objectID', '?')} «{hit.get('nome', '?')}»"


def _exemplos(hits: list[dict], limite: int = 3) -> str:
    amostra = "; ".join(_rotulo(h) for h in hits[:limite])
    return amostra + (f" (+{len(hits) - limite})" if len(hits) > limite else "")


INVARIANTES: dict[str, tuple[str, Callable[[dict], bool]]] = {
    "estoque_coerente": (
        "em_estoque == (tamanhos_disponiveis não vazio)",
        lambda h: h["em_estoque"] == bool(h["tamanhos_disponiveis"]),
    ),
    "promocao_coerente": (
        "em_promocao == (preco < preco_de)",
        lambda h: h["em_promocao"] == (h["preco"] < h["preco_de"]),
    ),
    "tamanhos_na_grade": (
        "tamanhos_disponiveis ⊆ grade",
        lambda h: set(h["tamanhos_disponiveis"]) <= set(h["grade"]),
    ),
}


def contar_catalogo(catalogo: list[dict], regra: dict) -> list[dict]:
    return [r for r in catalogo if condicao_ok(r, regra)]


def avaliar_expectativa(exp: dict, resultado: dict, catalogo: list[dict] | None) -> tuple[bool, str]:
    """Devolve (passou, explicação). A explicação diz o que foi conferido e, na falha, quem violou."""
    tipo = exp["tipo"]
    hits = resultado.get("hits", [])
    nb = resultado.get("nbHits", 0)

    if tipo == "nb_hits":
        problemas = []
        if "igual" in exp and nb != exp["igual"]:
            problemas.append(f"esperado == {exp['igual']}")
        if "min" in exp and nb < exp["min"]:
            problemas.append(f"esperado >= {exp['min']}")
        if "max" in exp and nb > exp["max"]:
            problemas.append(f"esperado <= {exp['max']}")
        if not problemas:
            return True, f"nbHits = {nb}"
        return False, f"nbHits = {nb}, " + " e ".join(problemas)

    if tipo in ("nb_hits_catalogo", "recall_catalogo"):
        if catalogo is None:
            raise ValueError(f"expectativa {tipo} precisa do catálogo local")
        alvo = contar_catalogo(catalogo, exp["regra"])
        regra = descrever_condicao(exp["regra"])
        if tipo == "nb_hits_catalogo":
            comparacao = exp.get("comparacao", "igual")
            ok = nb == len(alvo) if comparacao == "igual" else nb >= len(alvo)
            sinal = "==" if comparacao == "igual" else ">="
            texto = f"nbHits = {nb}, esperado {sinal} {len(alvo)} (catálogo: {regra})"
            return ok, texto
        if not alvo:
            return False, f"regra sem nenhum record no catálogo, recall não testa nada: {regra}"
        if nb < len(alvo):
            return False, (
                f"nbHits = {nb}, menos que os {len(alvo)} records do catálogo com {regra}: "
                f"faltam pelo menos {len(alvo) - nb}"
            )
        if len(hits) < nb:
            return False, (
                f"a página trouxe {len(hits)} de {nb} hits; aumente hitsPerPage para conferir o recall"
            )
        devolvidos = {h.get("objectID") for h in hits}
        faltando = [r for r in alvo if r["objectID"] not in devolvidos]
        if not faltando:
            return True, f"os {len(alvo)} records do catálogo com {regra} estão nos hits"
        return False, (
            f"faltam {len(faltando)} de {len(alvo)} records do catálogo com {regra}: {_exemplos(faltando)}"
        )

    if tipo in ("todos", "algum", "nenhum"):
        janela = hits[: exp["primeiros"]] if "primeiros" in exp else hits
        escopo = f"{len(janela)} primeiros hits" if "primeiros" in exp else f"{len(janela)} hits devolvidos"
        cond = descrever_condicao(exp["condicao"])
        if not janela and tipo != "nenhum" and not exp.get("permitir_vazio"):
            return False, f"nenhum hit para conferir ({tipo}: {cond})"
        violam = [h for h in janela if not condicao_ok(h, exp["condicao"])]
        atendem = [h for h in janela if condicao_ok(h, exp["condicao"])]
        if tipo == "todos":
            if not violam:
                return True, f"todos os {escopo} têm {cond}"
            return False, f"{len(violam)} dos {escopo} sem {cond}: {_exemplos(violam)}"
        if tipo == "algum":
            if atendem:
                return True, f"{len(atendem)} dos {escopo} têm {cond}"
            return False, f"nenhum dos {escopo} tem {cond}: {_exemplos(janela)}"
        if not atendem:
            return True, f"nenhum dos {escopo} tem {cond}"
        return False, f"{len(atendem)} dos {escopo} têm {cond}: {_exemplos(atendem)}"

    if tipo == "ordenado":
        campo, sentido = exp["campo"], exp.get("sentido", "asc")
        if len(hits) < 2:
            return False, f"menos de 2 hits ({len(hits)}), ordem não testável"
        valores = [valor_campo(h, campo) for h in hits]
        for i in range(1, len(valores)):
            anterior, atual = valores[i - 1], valores[i]
            if _numero(anterior) is None or _numero(atual) is None:
                return False, f"{campo} ausente ou não numérico no hit {i}: {_rotulo(hits[i])}"
            fora = atual < anterior if sentido == "asc" else atual > anterior
            if fora:
                return False, (
                    f"{campo} fora da ordem {sentido} na posição {i + 1}: {anterior} → {atual} "
                    f"({_rotulo(hits[i])})"
                )
        return True, f"{len(hits)} hits em ordem {sentido} de {campo}"

    if tipo == "invariante":
        nome = exp["nome"]
        if nome not in INVARIANTES:
            raise ValueError(f"invariante desconhecida: {nome}")
        texto, regra = INVARIANTES[nome]
        if not hits:
            return False, f"nenhum hit para conferir a invariante {texto}"
        violam = []
        for h in hits:
            try:
                if not regra(h):
                    violam.append(h)
            except KeyError:
                violam.append(h)
        if not violam:
            return True, f"{texto} em {len(hits)} hits"
        return False, f"{len(violam)} hits violam {texto}: {_exemplos(violam)}"

    raise ValueError(f"tipo de expectativa desconhecido: {tipo}")


def avaliar_consulta(caso: dict, resultado: dict, catalogo: list[dict] | None) -> dict:
    detalhes = [(exp, *avaliar_expectativa(exp, resultado, catalogo)) for exp in caso["expectativas"]]
    return {
        "id": caso["id"],
        "passou": all(ok for _, ok, _ in detalhes),
        "nbHits": resultado.get("nbHits", 0),
        "detalhes": [{"tipo": exp["tipo"], "passou": ok, "explicacao": txt} for exp, ok, txt in detalhes],
    }
