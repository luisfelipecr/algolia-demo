"""Conector VTEX → Algolia: lê o catálogo, monta os records e sincroniza o índice com a configuração do repo.

    uv run python -m ingest.indexar                       # ensaio: monta os records e mostra o resumo
    uv run python -m ingest.indexar --aplicar             # escreve na Algolia (Write key do .env)
    uv run python -m ingest.indexar --idioma en --aplicar  # loja /en: produtos_en a partir de data/vtex/en/

Com `--aplicar`, a ordem é: settings do primário (com as replicas) → settings de cada replica → sinônimos →
Rules → records por `replace_all_objects` (índice temporário e troca atômica; a busca não fica vazia no meio).
Tudo sai de `ingest/config/` e do catálogo, então o índice é reconstruível a partir do repo.

Um índice por idioma (o padrão da Algolia para várias línguas): as settings de `ingest/config/indice.json`
com o que muda no idioma por cima (`ingest/config/<idioma>/indice.json`: `queryLanguages`, `ignorePlurals`,
`optionalWords`...), e sinônimos e Rules próprios na mesma pasta. O `objectID` de um record é o mesmo nas duas
línguas (vem do catálogo em pt, o idioma padrão da loja), para a loja trocar de idioma no mesmo produto.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from ingest.fonte_vtex import FonteArquivo, todos_os_produtos
from ingest.registro import media_do_catalogo, registros

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = Path(__file__).resolve().parent / "config"
LIMITE_RECORD = 10_000  # bytes, plano Free
RANKING_PADRAO = ["typo", "geo", "words", "filters", "proximity", "attribute", "exact", "custom"]
ESPERA_MAXIMA = 40  # tentativas de wait_for_task (backoff do client, cerca de 2 a 3 minutos)
ORDENACOES = {"preco_asc": "asc(preco)", "preco_desc": "desc(preco)"}


@dataclass(frozen=True)
class Idioma:
    indice: str
    mock: Path
    config: Path
    saida: str  # records do ensaio em data/algolia/, lidos pelo golden set


IDIOMAS = {
    "pt": Idioma("produtos_ptbr", RAIZ / "data" / "vtex", CONFIG, "registros.json"),
    "en": Idioma("produtos_en", RAIZ / "data" / "vtex" / "en", CONFIG / "en", "registros_en.json"),
}


def carregar_env(caminho: Path = RAIZ / ".env") -> None:
    """Lê KEY=VALUE do .env sem sobrescrever o ambiente. Nunca imprime valores."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, _, valor = linha.partition("=")
            os.environ.setdefault(chave.strip(), valor.strip().strip("'\""))


def _json(nome: str, pasta: Path = CONFIG):
    return json.loads((pasta / nome).read_text(encoding="utf-8"))


def montar_registros(fonte, ids_por_sku: dict[str, str] | None = None) -> list[dict]:
    """`ids_por_sku` (SKU → objectID do idioma padrão) fixa o mesmo objectID em outro idioma: a cor, que entra
    no objectID, vem traduzida ("azul" × "blue"), mas os SKUs são os mesmos."""
    avaliacoes = fonte.avaliacoes()
    media = media_do_catalogo(avaliacoes)
    saida = []
    for produto in todos_os_produtos(fonte):
        saida.extend(registros(produto, avaliacoes.get(produto["productId"]), media))
    if ids_por_sku is not None:
        for r in saida:
            ids = {ids_por_sku.get(s["id"]) for s in r["skus"]}
            if len(ids) != 1 or None in ids:
                raise ValueError(f"SKUs de {r['objectID']} não casam com um record do idioma padrão: {ids}")
            r["objectID"] = ids.pop()
    ids = [r["objectID"] for r in saida]
    if len(ids) != len(set(ids)):
        raise ValueError("objectID repetido")
    return saida


def tamanho(record: dict) -> int:
    return len(json.dumps(record, ensure_ascii=False).encode("utf-8"))


def ids_do_idioma_padrao(mock: Path = IDIOMAS["pt"].mock) -> dict[str, str]:
    return {s["id"]: r["objectID"] for r in montar_registros(FonteArquivo(mock)) for s in r["skus"]}


def configuracao(indice: str, idioma: str = "pt") -> tuple[dict, dict[str, dict]]:
    """Settings do primário (com `replicas`) e de cada replica (mesmas settings, ordenação na frente)."""
    pasta = IDIOMAS[idioma].config
    # a base é a do pt; o idioma sobrepõe o que muda (idioma da busca, palavras opcionais)
    base = {**_json("indice.json"), **(_json("indice.json", pasta) if pasta != CONFIG else {})}
    replicas = {f"{indice}_{sufixo}": criterio for sufixo, criterio in ORDENACOES.items()}
    primario = {**base, "replicas": list(replicas)}
    por_replica = {
        nome: {**base, "ranking": [criterio, *RANKING_PADRAO]} for nome, criterio in replicas.items()
    }
    return primario, por_replica


def contem(atual, desejado) -> bool:
    """O valor atual tem tudo o que o desejado pede (a API devolve campos a mais: padrões e metadados)."""
    if isinstance(desejado, dict):
        return isinstance(atual, dict) and all(contem(atual.get(k), v) for k, v in desejado.items())
    if isinstance(desejado, list):
        return (
            isinstance(atual, list)
            and len(atual) == len(desejado)
            and all(contem(a, d) for a, d in zip(atual, desejado, strict=True))
        )
    return atual == desejado


def mesmos_objetos(atuais: list[dict], desejados: list[dict]) -> bool:
    """Mesmo conjunto de objectIDs e cada objeto atual contém o desejado."""
    por_id = {o["objectID"]: o for o in atuais}
    return set(por_id) == {d["objectID"] for d in desejados} and all(
        contem(por_id[d["objectID"]], d) for d in desejados
    )


def aplicar(records: list[dict], indice: str, idioma: str = "pt") -> None:
    from algoliasearch.search.client import SearchClientSync

    client = SearchClientSync(os.environ["ALGOLIA_APP_ID"], os.environ["ALGOLIA_WRITE_API_KEY"])
    primario, por_replica = configuracao(indice, idioma)
    pasta = IDIOMAS[idioma].config

    def esperar(nome: str, resposta) -> None:
        try:
            client.wait_for_task(index_name=nome, task_id=resposta.task_id, max_retries=ESPERA_MAXIMA)
        except Exception as erro:  # o client levanta exceção genérica quando esgota as tentativas
            raise RuntimeError(
                f"task {resposta.task_id} de {nome} não publicou: a fila de indexação do app está parada? "
                "Ver logs de build (get_logs type=build) e o status no dashboard."
            ) from erro
        print(f"  ok: {nome}", flush=True)

    # Só aplica o que mudou: no Free, um set_settings num índice populado com replicas reconstrói tudo e pode
    # ficar dezenas de minutos na fila, mesmo com settings idênticas (observado em 08/10/2026).
    def settings_atuais(nome: str) -> dict:
        try:
            return json.loads(client.get_settings_with_http_info(nome).raw_data)
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:  # índice ainda não existe
                return {}
            raise

    for nome, settings in [(indice, primario), *por_replica.items()]:
        if contem(settings_atuais(nome), settings):
            print(f"  settings iguais: {nome}", flush=True)
        else:
            esperar(nome, client.set_settings(nome, settings))

    sinonimos = _json("sinonimos.json", pasta)
    atuais = json.loads(client.search_synonyms_with_http_info(indice, {"hitsPerPage": 1000}).raw_data)["hits"]
    if mesmos_objetos(atuais, sinonimos):
        print("  sinônimos iguais", flush=True)
    else:
        # sinônimos criados pelo copiloto (MCP) somem ao aplicar a configuração do repo: avisa alto
        do_copiloto = [s["objectID"] for s in atuais if s["objectID"].startswith("copiloto-")]
        if do_copiloto:
            print(
                f"  AVISO: {len(do_copiloto)} sinônimo(s) criados pelo copiloto serão removidos: "
                f"{', '.join(do_copiloto)}. Para manter, copie para ingest/config/sinonimos.json.",
                flush=True,
            )
        esperar(
            indice,
            client.save_synonyms(indice, sinonimos, forward_to_replicas=True, replace_existing_synonyms=True),
        )

    regras = _json("regras.json", pasta)
    atuais = json.loads(client.search_rules_with_http_info(indice, {"hitsPerPage": 1000}).raw_data)["hits"]
    if mesmos_objetos(atuais, regras):
        print("  Rules iguais", flush=True)
    else:
        esperar(
            indice, client.save_rules(indice, regras, forward_to_replicas=True, clear_existing_rules=True)
        )
    print(f"  records: replace_all_objects em {indice}…", flush=True)
    client.replace_all_objects(indice, records, batch_size=500)

    replicas_no_indice = client.get_settings(indice).replicas or []
    if sorted(replicas_no_indice) != sorted(primario["replicas"]):
        raise RuntimeError(f"replicas fora do esperado depois da troca: {replicas_no_indice}")
    # list_indices() quebra na validação do client 4.47 quando há replicas (faltam campos no modelo): lê cru
    resposta = json.loads(client.list_indices_with_http_info().raw_data)
    contagem = {i["name"]: i["entries"] for i in resposta["items"] if i["name"].startswith(indice)}
    print(f"índices: {contagem}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--aplicar", action="store_true", help="escreve na Algolia (sem isso, só ensaia)")
    parser.add_argument("--idioma", choices=list(IDIOMAS), default="pt", help="loja e índice (padrão: pt)")
    parser.add_argument("--mock", type=Path, help="pasta do catálogo VTEX mock (padrão: a do idioma)")
    args = parser.parse_args(argv)

    carregar_env()
    idioma = IDIOMAS[args.idioma]
    indice = os.environ.get("ALGOLIA_INDEX", idioma.indice) if args.idioma == "pt" else idioma.indice
    ids = None if args.idioma == "pt" else ids_do_idioma_padrao()
    records = montar_registros(FonteArquivo(args.mock or idioma.mock), ids)
    tamanhos = sorted(tamanho(r) for r in records)
    print(
        f"{len(records)} records para {indice}; tamanho p50 {tamanhos[len(tamanhos) // 2]} B, "
        f"máximo {tamanhos[-1]} B (limite {LIMITE_RECORD} B)"
    )
    if tamanhos[-1] > LIMITE_RECORD:
        print("record acima do limite do plano Free", file=sys.stderr)
        return 1

    saida = RAIZ / "data" / "algolia"
    saida.mkdir(parents=True, exist_ok=True)
    (saida / idioma.saida).write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    if not args.aplicar:
        print(f"ensaio: nada foi escrito na Algolia (records em {saida / idioma.saida})")
        return 0
    aplicar(records, indice, args.idioma)
    return 0


if __name__ == "__main__":
    sys.exit(main())
