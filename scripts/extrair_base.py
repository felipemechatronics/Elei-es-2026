"""Extrai a base geográfica (municípios, bairros e locais de votação georreferenciados)
do projeto de referência https://github.com/sousapfe/eleicoesRN (arquivo dados.js).

Essa base vem do cadastro de locais de votação do TSE (coordenadas e eleitorado apto)
e das malhas do IBGE (municípios e bairros do Censo 2022). Ela não depende do cargo,
então serve para qualquer cargo do 1º turno de 2026.

Uso:
    git clone --depth 1 https://github.com/sousapfe/eleicoesRN /tmp/eleicoesRN
    python scripts/extrair_base.py /tmp/eleicoesRN/dados.js
"""
import csv, json, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "base"


def main(src):
    s = Path(src).read_text(encoding="utf-8")
    d = json.loads(s[s.index("=") + 1:].strip().rstrip(";"))
    BASE.mkdir(exist_ok=True)

    with open(BASE / "municipios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cd_ibge", "cd_tse", "nome", "aptos", "secoes", "tem_bairros"])
        for m in d["munis"]:
            w.writerow([m["id"], m["cd"], m["n"], m["ap"], m["se"], int(bool(m["hb"]))])

    with open(BASE / "locais.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "cd_tse", "cd_ibge", "zona", "nr_local", "nome", "endereco",
                    "bairro_tse", "lat", "lon", "aproximado", "cd_bairro", "aptos", "secoes"])
        for l in d["locais"]:
            cd = l["id"].split("-")[0]
            w.writerow([l["id"], cd, l["m"], l["z"], l["nl"], l["n"], l.get("end", ""),
                        l.get("bt", ""), l["lat"], l["lon"], l.get("aprox", 0),
                        l.get("bi") or "", l["ap"], l["se"]])

    with open(BASE / "bairros.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cd_bairro", "cd_ibge", "nome"])
        for b in d["bairros"]:
            w.writerow([b["id"], b["m"], b["n"]])

    for key, name in (("mapa", "municipios.geojson"), ("bmapa", "bairros.geojson")):
        (BASE / name).write_text(json.dumps(d[key], ensure_ascii=False, separators=(",", ":")),
                                 encoding="utf-8")
    print(f"{len(d['munis'])} municípios, {len(d['locais'])} locais, {len(d['bairros'])} bairros")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/eleicoesRN/dados.js")
