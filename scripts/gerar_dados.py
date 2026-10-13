"""Gera os dados do relatório a partir dos resultados por seção do TSE.

Lê o arquivo votacao_secao (CSV ou ZIP) publicado pelo TSE, filtra o cargo, a UF e o
turno, soma os votos por local de votação, bairro e município e grava:

  docs/dados.js                         dados do site interativo (GitHub Pages)
  docs/dados/resultado_municipios.csv   tabela por município
  docs/dados/resultado_bairros.csv      tabela por bairro (municípios com bairros do IBGE)
  docs/dados/resultado_locais.csv       tabela por local de votação
  relatorio/resumo.json                 números usados no relatório

Uso:
  python scripts/gerar_dados.py dados_tse/votacao_secao_2026_RN.csv
  python scripts/gerar_dados.py arquivo.zip --cargo Presidente --turno 1
  python scripts/gerar_dados.py arquivo.csv --cargo Governador --anulados 50,29

Votos anulados (candidatos com registro indeferido ou cassado) não vêm marcados no
arquivo por seção. Informe os números desses candidatos em --anulados; eles passam a
contar como nulos, como faz o TSE na totalização.
"""
import argparse, csv, io, json, re, sys, unicodedata, zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ / "base"
DOCS = RAIZ / "docs"
REL = RAIZ / "relatorio"

USECOLS = ["SG_UF", "NR_TURNO", "DS_CARGO", "DT_ELEICAO", "DS_ELEICAO", "CD_MUNICIPIO",
           "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS",
           "NR_LOCAL_VOTACAO", "NM_LOCAL_VOTACAO", "DS_LOCAL_VOTACAO_ENDERECO"]

# Número de urna -> sigla. Os dois primeiros dígitos do número do candidato
# majoritário são o número do partido. Pode ser sobrescrito em config/candidatos.json.
PARTIDOS = {10: "REPUBLICANOS", 11: "PP", 12: "PDT", 13: "PT", 15: "MDB", 16: "PSTU",
            18: "REDE", 20: "PODE", 21: "PCB", 22: "PL", 23: "CIDADANIA", 25: "PRD",
            27: "DC", 28: "PRTB", 29: "PCO", 30: "NOVO", 33: "MOBILIZA", 35: "PMB",
            36: "AGIR", 40: "PSB", 43: "PV", 44: "UNIÃO", 45: "PSDB", 50: "PSOL",
            55: "PSD", 65: "PCdoB", 70: "AVANTE", 77: "SOLIDARIEDADE", 80: "UP"}

BRANCO, NULO = 95, 96
PARTICULAS = {"DA", "DE", "DO", "DAS", "DOS", "E"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.strip().upper()


def titulo(s):
    out = []
    for i, w in enumerate(str(s).lower().split()):
        out.append(w if (i and w.upper() in PARTICULAS) else w[:1].upper() + w[1:])
    return " ".join(out)


def nome_curto(nome):
    p = [w for w in str(nome).split() if w.upper() not in PARTICULAS]
    if len(p) <= 2:
        return titulo(" ".join(p))
    return titulo(f"{p[0]} {p[-1]}")


def abrir_csvs(caminhos):
    for c in caminhos:
        c = Path(c)
        if c.suffix.lower() == ".zip":
            z = zipfile.ZipFile(c)
            for n in z.namelist():
                if n.lower().endswith(".csv"):
                    yield n, io.TextIOWrapper(z.open(n), encoding="latin1")
        else:
            yield c.name, open(c, encoding="latin1")


def ler_votos(caminhos, cargo, uf, turno):
    alvo = norm(cargo)
    partes, info = [], {}
    for nome, fh in abrir_csvs(caminhos):
        cols = pd.read_csv(fh, sep=";", nrows=0).columns
        fh.seek(0)
        use = [c for c in USECOLS if c in cols]
        for ch in pd.read_csv(fh, sep=";", dtype=str, usecols=use, chunksize=400_000):
            ch = ch[(ch.SG_UF == uf) & (ch.NR_TURNO == str(turno))]
            ch = ch[ch.DS_CARGO.map(norm) == alvo]
            if len(ch):
                info.setdefault("ds_eleicao", ch.DS_ELEICAO.iloc[0])
                info.setdefault("dt_eleicao", ch.DT_ELEICAO.iloc[0])
                partes.append(ch)
        print(f"  lido: {nome}", file=sys.stderr)
    if not partes:
        return None, info
    df = pd.concat(partes, ignore_index=True)
    for c in ("CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_VOTAVEL", "QT_VOTOS", "NR_LOCAL_VOTACAO"):
        df[c] = df[c].astype(int)
    return df, info


def faixas(secs):
    secs = sorted(set(secs))
    out, i = [], 0
    while i < len(secs):
        j = i
        while j + 1 < len(secs) and secs[j + 1] == secs[j] + 1:
            j += 1
        out.append(str(secs[i]) if i == j else f"{secs[i]}–{secs[j]}")
        i = j + 1
    return ", ".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivos", nargs="+", help="CSV ou ZIP votacao_secao do TSE")
    ap.add_argument("--cargo", default="Presidente")
    ap.add_argument("--uf", default="RN")
    ap.add_argument("--turno", type=int, default=1)
    ap.add_argument("--anulados", default="", help="números de candidatos cujos votos foram anulados, ex.: 50,29")
    ap.add_argument("--config", default=None,
                    help="JSON opcional {numero: {nome, partido}} com nomes de urna e siglas "
                         "(padrão: config/candidatos_<cargo>.json, ex.: candidatos_presidente.json)")
    a = ap.parse_args()

    print(f"Lendo votos para {a.cargo}, {a.uf}, {a.turno}º turno...", file=sys.stderr)
    df, info = ler_votos(a.arquivos, a.cargo, a.uf, a.turno)
    if df is None:
        sys.exit(f"ERRO: nenhuma linha com DS_CARGO = '{a.cargo}', UF {a.uf}, turno {a.turno} "
                 f"nos arquivos informados. Confira se o arquivo é o da eleição que contém esse cargo.")

    anulados = {int(x) for x in a.anulados.split(",") if x.strip()}
    cfg = {}
    a.config = a.config or str(RAIZ / "config" / f"candidatos_{norm(a.cargo).lower().replace(' ', '_')}.json")
    if Path(a.config).exists():
        cfg = {int(k): v for k, v in json.loads(Path(a.config).read_text(encoding="utf-8")).items()}

    # ---- candidatos (ordenados pelo total no estado) ----
    especiais = {BRANCO, NULO} | anulados | {97}
    tot = df.groupby(["NR_VOTAVEL"]).QT_VOTOS.sum()
    nomes = df.drop_duplicates("NR_VOTAVEL").set_index("NR_VOTAVEL").NM_VOTAVEL
    cand_nrs = [int(n) for n in tot.sort_values(ascending=False).index if int(n) not in especiais]
    cands = []
    for i, nr in enumerate(cand_nrs):
        c = cfg.get(nr, {})
        cands.append({"k": i, "nr": nr, "nome": c.get("nome") or nome_curto(nomes[nr]),
                      "completo": titulo(nomes[nr]),
                      "partido": c.get("partido") or PARTIDOS.get(nr // 10 if nr >= 100 else nr, f"nº {nr}")})
    idx = {c["nr"]: c["k"] for c in cands}
    nc = len(cands)

    # ---- agrega por local de votação ----
    df["lid"] = df.CD_MUNICIPIO.astype(str) + "-" + df.NR_ZONA.astype(str) + "-" + df.NR_LOCAL_VOTACAO.astype(str)
    g = df.groupby(["lid", "NR_VOTAVEL"]).QT_VOTOS.sum()
    secs = df.groupby("lid").apply(lambda x: sorted(set(x.NR_SECAO)), include_groups=False)
    meta_loc = df.drop_duplicates("lid").set_index("lid")

    base_loc = pd.read_csv(BASE / "locais.csv", dtype=str, keep_default_na=False).set_index("id")
    base_mun = pd.read_csv(BASE / "municipios.csv", dtype=str).set_index("cd_tse")
    bairros_nome = pd.read_csv(BASE / "bairros.csv", dtype=str).set_index("cd_bairro")

    def vazio():
        return {"ap": 0, "cp": 0, "ab": 0, "v": 0, "b": 0, "nu": 0, "se": 0, "vt": [0] * nc}

    def soma(dst, src):
        for k in ("ap", "cp", "ab", "v", "b", "nu", "se"):
            dst[k] += src[k]
        dst["vt"] = [x + y for x, y in zip(dst["vt"], src["vt"])]

    locais, sem_base = [], 0
    for lid, serie in g.groupby(level=0):
        u = vazio()
        for (_, nr), q in serie.items():
            nr = int(nr); q = int(q)
            u["cp"] += q
            if nr == BRANCO:
                u["b"] += q
            elif nr in (NULO, 97) or nr in anulados:
                u["nu"] += q
            else:
                u["vt"][idx[nr]] += q
        u["v"] = sum(u["vt"])
        s = secs[lid]
        u["se"] = len(s)
        cd, z, nl = lid.split("-")
        mrow = meta_loc.loc[lid]
        if lid in base_loc.index:
            b = base_loc.loc[lid]
            u["ap"] = int(b.aptos)
            lat, lon, aprox = float(b.lat), float(b.lon), int(b.aproximado)
            bi, bt, mid = b.cd_bairro or None, b.bairro_tse, b.cd_ibge
            # seções extras (ex.: voto em trânsito) sem eleitorado no cadastro
            u["ap"] = max(u["ap"], u["cp"])
        else:
            sem_base += 1
            u["ap"] = u["cp"]
            lat = lon = None; aprox = 1; bi = None; bt = ""
            mid = base_mun.loc[cd].cd_ibge
        u["ab"] = u["ap"] - u["cp"]
        u.update({"id": lid, "m": mid, "z": int(z), "nl": int(nl), "n": mrow.NM_LOCAL_VOTACAO,
                  "end": mrow.get("DS_LOCAL_VOTACAO_ENDERECO", "") if hasattr(mrow, "get") else "",
                  "bt": bt, "secs": faixas(s), "lat": lat, "lon": lon, "aprox": aprox, "bi": bi})
        locais.append(u)

    # ---- municípios e bairros ----
    munis = {}
    for cd_tse, r in base_mun.iterrows():
        m = vazio(); m.update({"id": r.cd_ibge, "cd": int(cd_tse), "n": r.nome, "hb": r.tem_bairros == "1",
                               "nloc": 0, "zs": set()})
        munis[r.cd_ibge] = m
    bairros = {}
    for bid, r in bairros_nome.iterrows():
        b = vazio(); b.update({"id": bid, "m": r.cd_ibge, "n": r.nome, "nloc": 0, "zs": set()})
        bairros[bid] = b
    for l in locais:
        m = munis[l["m"]]; soma(m, l); m["nloc"] += 1; m["zs"].add(l["z"])
        if l["bi"] and l["bi"] in bairros:
            b = bairros[l["bi"]]; soma(b, l); b["nloc"] += 1; b["zs"].add(l["z"])
    for coll in (munis, bairros):
        for u in coll.values():
            u["zs"] = sorted(u["zs"])
    est = vazio()
    for m in munis.values():
        soma(est, m)

    # ---- grava dados.js ----
    mapa = json.loads((BASE / "municipios.geojson").read_text(encoding="utf-8"))
    bmapa = json.loads((BASE / "bairros.geojson").read_text(encoding="utf-8"))
    meta = {"cargo": titulo(a.cargo), "uf": a.uf, "turno": a.turno,
            "eleicao": info.get("ds_eleicao", ""), "data": info.get("dt_eleicao", ""),
            "anulados": sorted(anulados), "locais_sem_base": sem_base}
    out = {"meta": meta, "cands": cands, "estado": est, "munis": list(munis.values()),
           "locais": locais, "bairros": list(bairros.values()), "mapa": mapa, "bmapa": bmapa}
    DOCS.mkdir(exist_ok=True)
    (DOCS / "dados.js").write_text("window.DADOS=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n",
                                   encoding="utf-8")

    # ---- CSVs ----
    (DOCS / "dados").mkdir(exist_ok=True)
    ccols = [f"{c['nome']} ({c['nr']})" for c in cands]

    def linha(u):
        r = [u["ap"], u["cp"], u["ab"], u["v"], u["b"], u["nu"]] + u["vt"]
        r += [round(100 * x / u["v"], 2) if u["v"] else "" for x in u["vt"]]
        return r
    head = ["aptos", "comparecimento", "abstencao", "validos", "brancos", "nulos"] + ccols + [f"% {c}" for c in ccols]
    with open(DOCS / "dados" / "resultado_municipios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["cd_ibge", "cd_tse", "municipio", "secoes", "locais"] + head)
        for m in sorted(munis.values(), key=lambda x: x["n"]):
            w.writerow([m["id"], m["cd"], m["n"], m["se"], m["nloc"]] + linha(m))
    with open(DOCS / "dados" / "resultado_bairros.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["cd_bairro", "municipio", "bairro", "locais"] + head)
        for b in sorted(bairros.values(), key=lambda x: (munis[x["m"]]["n"], x["n"])):
            if b["nloc"]:
                w.writerow([b["id"], munis[b["m"]]["n"], b["n"], b["nloc"]] + linha(b))
    with open(DOCS / "dados" / "resultado_locais.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "municipio", "zona", "nr_local", "local", "endereco", "bairro_ibge", "bairro_tse",
                    "lat", "lon", "coord_aproximada", "secoes"] + head)
        for l in sorted(locais, key=lambda x: (munis[x["m"]]["n"], x["z"], x["nl"])):
            w.writerow([l["id"], munis[l["m"]]["n"], l["z"], l["nl"], l["n"], l["end"],
                        bairros[l["bi"]]["n"] if l["bi"] in bairros else "", l["bt"],
                        l["lat"], l["lon"], l["aprox"], l["secs"]] + linha(l))

    REL.mkdir(exist_ok=True)
    (REL / "resumo.json").write_text(json.dumps({"meta": meta, "cands": cands, "estado": est},
                                                ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{meta['cargo']} - {a.uf} - {a.turno}º turno: {len(locais)} locais, {est['se']} seções, "
          f"{len(cands)} candidatos, {sem_base} locais fora do cadastro base", file=sys.stderr)
    for c in cands[:6]:
        print(f"  {c['nome']:<28} {c['partido']:<12} {est['vt'][c['k']]:>9,}  {100*est['vt'][c['k']]/est['v']:5.2f}%",
              file=sys.stderr)


if __name__ == "__main__":
    main()
