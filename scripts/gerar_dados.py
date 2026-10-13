"""Gera os dados do site e do relatório a partir dos resultados por seção do TSE.

Aceita dois formatos do Portal de Dados Abertos do TSE:
  - votacao_secao (CSV ou ZIP), com a coluna DS_CARGO;
  - boletim de urna (CSV, ZIP ou XLSX), com DS_CARGO_PERGUNTA, QT_APTOS e QT_COMPARECIMENTO.

Filtra o cargo, a UF e o turno, soma os votos por local de votação, bairro e município e grava,
para cada cargo (ex.: presidente):

  docs/<cargo>.js                          dados do site interativo
  docs/geo.js                              mapas de municípios e bairros (comum a todos os cargos)
  docs/cargos.js                           lista de cargos disponíveis no site
  docs/dados/<cargo>/resultado_*.csv       tabelas por município, bairro e local de votação
  relatorio/<cargo>/resumo.json            números usados no relatório

Uso:
  python scripts/gerar_dados.py dados_tse/Urnas_Presidente.xlsx --cargo Presidente
  python scripts/gerar_dados.py dados_tse/votacao_secao_2026_RN.csv --cargo Governador --anulados 50,29

Votos anulados (candidatos com registro indeferido ou cassado) não vêm marcados no arquivo
por seção. Informe os números desses candidatos em --anulados; eles passam a contar como nulos,
como faz o TSE na totalização.
"""
import argparse, csv, io, json, re, sys, unicodedata, zipfile
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ / "base"
DOCS = RAIZ / "docs"
REL = RAIZ / "relatorio"

# Número de urna -> sigla, para quando o arquivo não traz o partido. Os dois primeiros
# dígitos do número de um candidato majoritário são o número do partido.
PARTIDOS = {10: "REPUBLICANOS", 11: "PP", 12: "PDT", 13: "PT", 14: "MISSÃO", 15: "MDB", 16: "PSTU",
            18: "REDE", 20: "PODE", 21: "PCB", 22: "PL", 23: "CIDADANIA", 25: "PRD",
            27: "DC", 28: "PRTB", 29: "PCO", 30: "NOVO", 33: "MOBILIZA", 35: "DEMOCRATA",
            36: "AGIR", 40: "PSB", 43: "PV", 44: "UNIÃO", 45: "PSDB", 50: "PSOL",
            55: "PSD", 65: "PCdoB", 70: "AVANTE", 77: "SOLIDARIEDADE", 80: "UP"}

BRANCO, NULO = 95, 96
PARTICULAS = {"DA", "DE", "DO", "DAS", "DOS", "E"}
NULOS_TSE = {"#NULO#", "#NE#", "", "nan", "None"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.strip().upper()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", norm(s).lower()).strip("_")


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


# ---------------------------------------------------------------- leitura
def abrir(caminhos):
    """Gera (nome, DataFrame-iterável) para cada tabela dentro dos arquivos."""
    for c in caminhos:
        c = Path(c)
        suf = c.suffix.lower()
        if suf in (".xlsx", ".xls"):
            yield c.name, [pd.read_excel(c, dtype=str)]
        elif suf == ".zip":
            z = zipfile.ZipFile(c)
            for n in z.namelist():
                if n.lower().endswith(".csv"):
                    yield n, pd.read_csv(io.TextIOWrapper(z.open(n), encoding="latin1"), sep=";",
                                         dtype=str, chunksize=400_000)
        else:
            yield c.name, pd.read_csv(c, sep=";", encoding="latin1", dtype=str, chunksize=400_000)


def padronizar(ch):
    """Leva os dois formatos do TSE para as mesmas colunas."""
    ch = ch.rename(columns={"DS_CARGO_PERGUNTA": "DS_CARGO", "DT_PLEITO": "DT_ELEICAO"})
    keep = ["SG_UF", "NR_TURNO", "DS_CARGO", "DS_ELEICAO", "DT_ELEICAO", "CD_MUNICIPIO", "NR_ZONA",
            "NR_SECAO", "NR_LOCAL_VOTACAO", "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS", "SG_PARTIDO",
            "QT_APTOS", "QT_COMPARECIMENTO", "NM_LOCAL_VOTACAO", "DS_LOCAL_VOTACAO_ENDERECO"]
    return ch[[c for c in keep if c in ch.columns]]


def ler_votos(caminhos, cargo, uf, turno):
    alvo = norm(cargo)
    partes, info, formato = [], {}, "votacao_secao"
    for nome, chunks in abrir(caminhos):
        for ch in chunks:
            ch = padronizar(ch)
            if "QT_APTOS" in ch.columns:
                formato = "boletim_urna"
            ch = ch[(ch.SG_UF == uf) & (ch.NR_TURNO.astype(str).str.strip() == str(turno))]
            ch = ch[ch.DS_CARGO.map(norm) == alvo]
            if len(ch):
                info.setdefault("ds_eleicao", ch.DS_ELEICAO.iloc[0])
                dt = str(ch.DT_ELEICAO.iloc[0])
                m = re.match(r"(\d{4})-(\d{2})-(\d{2})", dt)
                info.setdefault("dt_eleicao", f"{m[3]}/{m[2]}/{m[1]}" if m else dt)
                partes.append(ch)
        print(f"  lido: {nome}", file=sys.stderr)
    if not partes:
        return None, info, formato
    df = pd.concat(partes, ignore_index=True)
    for c in ("CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_VOTAVEL", "QT_VOTOS", "NR_LOCAL_VOTACAO",
              "QT_APTOS", "QT_COMPARECIMENTO"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c]).astype(int)
    return df, info, formato


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


# ---------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivos", nargs="+", help="arquivo(s) do TSE: CSV, ZIP ou XLSX")
    ap.add_argument("--cargo", default="Presidente")
    ap.add_argument("--uf", default="RN")
    ap.add_argument("--turno", type=int, default=1)
    ap.add_argument("--anulados", default="", help="números de candidatos cujos votos foram anulados, ex.: 50,29")
    ap.add_argument("--config", default=None,
                    help="JSON {numero: {nome, partido, cor}} com nomes de urna, siglas e posição de cor "
                         "(padrão: config/candidatos_<cargo>.json)")
    a = ap.parse_args()

    cid = slug(a.cargo) + ("" if a.turno == 1 else f"_{a.turno}t")
    print(f"Lendo votos para {a.cargo}, {a.uf}, {a.turno}º turno...", file=sys.stderr)
    df, info, formato = ler_votos(a.arquivos, a.cargo, a.uf, a.turno)
    if df is None:
        sys.exit(f"ERRO: nenhuma linha com cargo '{a.cargo}', UF {a.uf}, turno {a.turno} nos arquivos "
                 f"informados. Confira se o arquivo é o da eleição que contém esse cargo "
                 f"(Presidente fica na eleição geral federal; Governador, na estadual).")

    anulados = {int(x) for x in a.anulados.split(",") if x.strip()}
    cfg = {}
    a.config = a.config or str(RAIZ / "config" / f"candidatos_{slug(a.cargo)}.json")
    if Path(a.config).exists():
        cfg = {int(k): v for k, v in json.loads(Path(a.config).read_text(encoding="utf-8")).items()}

    # ---- candidatos (ordenados pelo total no estado) ----
    especiais = {BRANCO, NULO, 97} | anulados
    tot = df.groupby("NR_VOTAVEL").QT_VOTOS.sum()
    primeiros = df.drop_duplicates("NR_VOTAVEL").set_index("NR_VOTAVEL")
    cand_nrs = [int(n) for n in tot.sort_values(ascending=False).index if int(n) not in especiais]
    cands = []
    for i, nr in enumerate(cand_nrs):
        c = cfg.get(nr, {})
        bruto = primeiros.loc[nr, "NM_VOTAVEL"]
        sg = str(primeiros.loc[nr, "SG_PARTIDO"]) if "SG_PARTIDO" in primeiros.columns else ""
        nome = c.get("nome") or (titulo(bruto) if formato == "boletim_urna" else nome_curto(bruto))
        partido = c.get("partido") or (sg if sg not in NULOS_TSE else
                                       PARTIDOS.get(nr // 10 if nr >= 100 else nr, f"nº {nr}"))
        cands.append({"k": i, "nr": nr, "nome": nome, "completo": titulo(bruto), "partido": partido})
    # cores: posição 0, 1, 2 da paleta. Por padrão segue a ordem de votos; config pode fixar.
    fixas = {c["k"]: cfg[c["nr"]]["cor"] for c in cands if "cor" in cfg.get(c["nr"], {})}
    livres = [s for s in range(3) if s not in fixas.values()]
    for c in cands:
        c["cor"] = fixas.get(c["k"], livres.pop(0) if (c["k"] < 3 and livres) else None)
    idx = {c["nr"]: c["k"] for c in cands}
    nc = len(cands)

    # ---- agrega por local de votação ----
    df["lid"] = df.CD_MUNICIPIO.astype(str) + "-" + df.NR_ZONA.astype(str) + "-" + df.NR_LOCAL_VOTACAO.astype(str)
    g = df.groupby(["lid", "NR_VOTAVEL"]).QT_VOTOS.sum()
    secs = df.groupby("lid").NR_SECAO.agg(lambda x: sorted(set(x)))
    aptos_sec = None
    if "QT_APTOS" in df.columns:
        s = df.drop_duplicates(["NR_ZONA", "NR_SECAO"])
        aptos_sec = s.groupby("lid").QT_APTOS.sum()
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
        u["se"] = len(secs[lid])
        cd, z, nl = lid.split("-")
        mrow = meta_loc.loc[lid]
        b = base_loc.loc[lid] if lid in base_loc.index else None
        if b is None:
            sem_base += 1
        ap_ = int(aptos_sec[lid]) if aptos_sec is not None else (int(b.aptos) if b is not None else u["cp"])
        u["ap"] = max(ap_, u["cp"])
        u["ab"] = u["ap"] - u["cp"]
        nome_loc = mrow.get("NM_LOCAL_VOTACAO") if "NM_LOCAL_VOTACAO" in mrow else None
        end_loc = mrow.get("DS_LOCAL_VOTACAO_ENDERECO") if "DS_LOCAL_VOTACAO_ENDERECO" in mrow else None
        u.update({"id": lid, "m": b.cd_ibge if b is not None else base_mun.loc[cd].cd_ibge,
                  "z": int(z), "nl": int(nl),
                  "n": nome_loc or (b.nome if b is not None else f"Local {nl}"),
                  "end": end_loc or (b.endereco if b is not None else ""),
                  "bt": b.bairro_tse if b is not None else "", "secs": faixas(secs[lid]),
                  "lat": float(b.lat) if b is not None else None, "lon": float(b.lon) if b is not None else None,
                  "aprox": int(b.aproximado) if b is not None else 1,
                  "bi": (b.cd_bairro or None) if b is not None else None})
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

    # ---- grava arquivos do site ----
    DOCS.mkdir(exist_ok=True)
    meta = {"id": cid, "cargo": titulo(a.cargo), "uf": a.uf, "turno": a.turno,
            "eleicao": info.get("ds_eleicao", ""), "data": info.get("dt_eleicao", ""),
            "formato": formato, "anulados": sorted(anulados), "locais_sem_base": sem_base}
    out = {"meta": meta, "cands": cands, "estado": est, "munis": list(munis.values()),
           "locais": locais, "bairros": list(bairros.values())}
    (DOCS / f"{cid}.js").write_text("window.DADOS=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n",
                                    encoding="utf-8")
    geo = {"mapa": json.loads((BASE / "municipios.geojson").read_text(encoding="utf-8")),
           "bmapa": json.loads((BASE / "bairros.geojson").read_text(encoding="utf-8"))}
    (DOCS / "geo.js").write_text("window.GEO=" + json.dumps(geo, ensure_ascii=False, separators=(",", ":")) + ";\n",
                                 encoding="utf-8")
    # lista de cargos: mantém os já gerados
    cargos = {}
    cf = DOCS / "cargos.js"
    if cf.exists():
        s = cf.read_text(encoding="utf-8")
        cargos = {c["id"]: c for c in json.loads(s[s.index("=") + 1:].strip().rstrip(";"))}
    cargos[cid] = {"id": cid, "rotulo": titulo(a.cargo) + ("" if a.turno == 1 else f" ({a.turno}º turno)")}
    ordem = ["presidente", "governador", "senador"]
    lista = sorted(cargos.values(), key=lambda c: (ordem.index(c["id"].split("_")[0]) if c["id"].split("_")[0] in ordem else 9, c["id"]))
    cf.write_text("window.CARGOS=" + json.dumps(lista, ensure_ascii=False) + ";\n", encoding="utf-8")

    # ---- CSVs ----
    pasta = DOCS / "dados" / cid
    pasta.mkdir(parents=True, exist_ok=True)
    ccols = [f"{c['nome']} ({c['nr']})" for c in cands]

    def linha(u):
        r = [u["ap"], u["cp"], u["ab"], u["v"], u["b"], u["nu"]] + u["vt"]
        r += [round(100 * x / u["v"], 2) if u["v"] else "" for x in u["vt"]]
        return r
    head = ["aptos", "comparecimento", "abstencao", "validos", "brancos", "nulos"] + ccols + [f"% {c}" for c in ccols]
    with open(pasta / "resultado_municipios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["cd_ibge", "cd_tse", "municipio", "secoes", "locais"] + head)
        for m in sorted(munis.values(), key=lambda x: x["n"]):
            w.writerow([m["id"], m["cd"], m["n"], m["se"], m["nloc"]] + linha(m))
    with open(pasta / "resultado_bairros.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["cd_bairro", "municipio", "bairro", "locais"] + head)
        for b in sorted(bairros.values(), key=lambda x: (munis[x["m"]]["n"], x["n"])):
            if b["nloc"]:
                w.writerow([b["id"], munis[b["m"]]["n"], b["n"], b["nloc"]] + linha(b))
    with open(pasta / "resultado_locais.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "municipio", "zona", "nr_local", "local", "endereco", "bairro_ibge", "bairro_tse",
                    "lat", "lon", "coord_aproximada", "secoes"] + head)
        for l in sorted(locais, key=lambda x: (munis[x["m"]]["n"], x["z"], x["nl"])):
            w.writerow([l["id"], munis[l["m"]]["n"], l["z"], l["nl"], l["n"], l["end"],
                        bairros[l["bi"]]["n"] if l["bi"] in bairros else "", l["bt"],
                        l["lat"], l["lon"], l["aprox"], l["secs"]] + linha(l))

    (REL / cid).mkdir(parents=True, exist_ok=True)
    (REL / cid / "resumo.json").write_text(json.dumps({"meta": meta, "cands": cands, "estado": est},
                                                      ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{meta['cargo']} - {a.uf} - {a.turno}º turno ({formato}): {len(locais)} locais, {est['se']} seções, "
          f"{len(cands)} candidatos, {sem_base} locais fora do cadastro base", file=sys.stderr)
    print(f"  aptos {est['ap']:,}  comparecimento {est['cp']:,}  válidos {est['v']:,}  brancos {est['b']:,}  nulos {est['nu']:,}",
          file=sys.stderr)
    for c in cands[:6]:
        print(f"  {c['nome']:<28} {c['partido']:<12} {est['vt'][c['k']]:>9,}  {100*est['vt'][c['k']]/est['v']:5.2f}%",
              file=sys.stderr)


if __name__ == "__main__":
    main()
