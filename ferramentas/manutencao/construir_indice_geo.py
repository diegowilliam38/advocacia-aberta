#!/usr/bin/env python3
"""Constrói o índice local de geolocalização por IP usado nos relatórios de acesso.

Converte o CSV do DB-IP Lite em dois arquivos compactos, para que a consulta seja
feita na própria máquina, sem enviar IP nenhum a serviço externo:

    ranges.bin   faixas IPv4 ordenadas — 10 bytes por faixa (início, fim, local)
    locais.tsv   tabela "país<TAB>estado", uma linha por local

Só IPv4 entra, e a cidade é descartada: os IPs chegam mascarados em /24 nos logs, o
que sustenta país e estado, não cidade. Faixas vizinhas com o mesmo local são unidas,
o que reduz o índice em cerca de metade.

Uso:

    curl -sO https://download.db-ip.com/free/dbip-city-lite-AAAA-MM.csv.gz
    sudo python3 construir_indice_geo.py dbip-city-lite-AAAA-MM.csv.gz /var/lib/dbip

Fonte: DB-IP Lite (https://db-ip.com/db/download/ip-to-city-lite), licença CC BY 4.0 —
a atribuição é obrigatória em qualquer publicação que use estes dados. A base é mensal;
reconstrua de tempos em tempos para não trabalhar com faixas envelhecidas.
"""

from __future__ import annotations

import csv
import gzip
import struct
import sys
from pathlib import Path

REGISTRO = struct.Struct("<IIH")  # início, fim, índice do local
LIMITE_LOCAIS = 65_535            # o índice do local cabe em 2 bytes


def para_inteiro(ip: str) -> int | None:
    """Converte um IPv4 em inteiro. Devolve None para IPv6 ou lixo."""
    partes = ip.split(".")
    if len(partes) != 4:
        return None
    valor = 0
    for parte in partes:
        try:
            octeto = int(parte)
        except ValueError:
            return None
        if not 0 <= octeto <= 255:
            return None
        valor = (valor << 8) | octeto
    return valor


def construir(origem: Path, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    locais: dict[tuple[str, str], int] = {}
    faixas: list[tuple[int, int, int]] = []
    ignoradas = 0

    abrir = gzip.open if origem.suffix == ".gz" else open
    with abrir(origem, "rt", encoding="utf-8", errors="replace", newline="") as arquivo:
        for linha in csv.reader(arquivo):
            if len(linha) < 5:
                continue
            inicio = para_inteiro(linha[0])
            fim = para_inteiro(linha[1])
            if inicio is None or fim is None:
                ignoradas += 1
                continue

            pais = linha[3].strip() or "??"
            estado = linha[4].strip()
            chave = (pais, estado)
            if chave not in locais:
                if len(locais) >= LIMITE_LOCAIS:
                    # Passou do que o índice de 2 bytes comporta: agrupa pelo país.
                    chave = (pais, "")
                    locais.setdefault(chave, len(locais))
                else:
                    locais[chave] = len(locais)
            indice = locais[chave]

            # Une a faixa anterior quando é contígua e aponta para o mesmo local.
            if faixas and faixas[-1][2] == indice and faixas[-1][1] + 1 == inicio:
                faixas[-1] = (faixas[-1][0], fim, indice)
            else:
                faixas.append((inicio, fim, indice))

    faixas.sort(key=lambda f: f[0])

    with (destino / "ranges.bin").open("wb") as saida:
        for inicio, fim, indice in faixas:
            saida.write(REGISTRO.pack(inicio, fim, indice))

    ordenados = sorted(locais.items(), key=lambda item: item[1])
    with (destino / "locais.tsv").open("w", encoding="utf-8") as saida:
        for (pais, estado), _ in ordenados:
            saida.write(f"{pais}\t{estado}\n")

    tamanho = (destino / "ranges.bin").stat().st_size
    print(f"Faixas IPv4 : {len(faixas):,}".replace(",", "."))
    print(f"Locais      : {len(locais):,}".replace(",", "."))
    print(f"Índice      : {tamanho / 1_048_576:.1f} MiB em {destino}")
    if ignoradas:
        print(f"Linhas IPv6 ou inválidas ignoradas: {ignoradas:,}".replace(",", "."))
    print("\nFonte: DB-IP Lite (CC BY 4.0) — cite a atribuição ao publicar estes dados.")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    origem = Path(sys.argv[1])
    if not origem.exists():
        print(f"CSV não encontrado: {origem}", file=sys.stderr)
        return 1
    construir(origem, Path(sys.argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
