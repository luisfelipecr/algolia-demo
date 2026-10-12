"""Memória de tradução versionada (inglês → pt-BR) para nomes e descrições de produto.

A tradução foi feita uma vez, fora do build, e mora em `catalog/traducoes/pt-BR.json`: cada entrada guarda o
texto em inglês e o português, com a chave igual ao hash do inglês. O build só lê; se aparecer um texto sem
tradução, ele falha em vez de deixar inglês passar para o índice.
"""

import hashlib
import json
from pathlib import Path

MEMORIA = Path(__file__).parent / "traducoes" / "pt-BR.json"


class TraducaoFaltando(KeyError):
    """Há texto de origem sem entrada na memória de tradução."""


def chave(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


class Memoria:
    def __init__(self, entradas: dict[str, dict[str, str]]):
        self.entradas = entradas

    @classmethod
    def carregar(cls, caminho: Path = MEMORIA) -> "Memoria":
        if not caminho.exists():
            return cls({})
        return cls(json.loads(caminho.read_text(encoding="utf-8")))

    def salvar(self, caminho: Path = MEMORIA) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        ordenado = dict(sorted(self.entradas.items(), key=lambda kv: (kv[1]["en"], kv[0])))
        texto = json.dumps(ordenado, ensure_ascii=False, indent=1)
        caminho.write_text(texto + "\n", encoding="utf-8")

    def traduzir(self, texto: str) -> str:
        if not texto:
            return ""
        entrada = self.entradas.get(chave(texto))
        if entrada is None:
            raise TraducaoFaltando(texto)
        return entrada["pt"]

    def pendentes(self, textos: set[str]) -> list[str]:
        return sorted(t for t in textos if t and chave(t) not in self.entradas)

    def adicionar(self, en: str, pt: str) -> None:
        self.entradas[chave(en)] = {"en": en, "pt": pt}
