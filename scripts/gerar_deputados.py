"""Gera os dados de Deputado Federal e Deputado Estadual para a página docs/deputados.html.

Lê o votacao_secao do TSE (eleição estadual), soma os votos por candidato e por partido
(nominais + legenda) em cada local de votação, bairro e município, e grava:

  docs/dep_federal.js          estado, partidos, candidatos, municípios e bairros
  docs/dep_federal_locais.js   votos de cada candidato por local (carregado sob demanda)
  docs/dep_estadual.js / docs/dep_estadual_locais.js
  docs/dados/dep_<cargo>/votos_candidatos_municipios.csv e votos_partidos_municipios.csv

Uso:
  python scripts/gerar_deputados.py dados_tse/votacao_secao_2026_RN.csv
"""
import csv, json, sys, unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
BASE, DOCS = RAIZ / "base", RAIZ / "docs"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gerar_dados import PARTIDOS, titulo  # noqa: E402

CARGOS = {"federal": "Deputado Federal", "estadual": "Deputado Estadual"}
BRANCO, NULO = 95, 96


def compacto(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def main(arq):
    usecols = ["DS_CARGO", "NR_TURNO", "SG_UF", "DT_ELEICAO", "DS_ELEICAO", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO",
               "NR_LOCAL_VOTACAO", "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS"]
    df = pd.read_csv(arq, sep=";", encoding="latin1", dtype=str, usecols=usecols)
    df = df[(df.SG_UF == "RN") & (df.NR_TURNO == "1")]
    for c in ("CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_LOCAL_VOTACAO", "NR_VOTAVEL", "QT_VOTOS"):
        df[c] = df[c].astype(int)
    df["lid"] = df.CD_MUNICIPIO.astype(str) + "-" + df.NR_ZONA.astype(str) + "-" + df.NR_LOCAL_VOTACAO.astype(str)

    base_loc = pd.read_csv(BASE / "locais.csv", dtype=str, keep_default_na=False)
    base_mun = pd.read_csv(BASE / "municipios.csv", dtype=str)
    mun_ids = list(base_mun.cd_ibge); mun_idx = {m: i for i, m in enumerate(mun_ids)}
    tse2ibge = dict(zip(base_mun.cd_tse, base_mun.cd_ibge))
    bairros = pd.read_csv(BASE / "bairros.csv", dtype=str)
    b_ids = list(bairros.cd_bairro); b_idx = {b: i for i, b in enumerate(b_ids)}

    for cid, cargo in CARGOS.items():
        x = df[df.DS_CARGO == cargo]
        if x.empty:
            print(f"sem dados para {cargo}", file=sys.stderr); continue
        tipo = x.NR_VOTAVEL.map(lambda n: "b" if n == BRANCO else "n" if n == NULO else "l" if n < 100 else "c")
        x = x.assign(tipo=tipo, partido=x.NR_VOTAVEL.map(lambda n: n if n < 100 else int(str(n)[:2])))

        # locais (mesma ordem/ids do site)
        locs = sorted(x.lid.unique())
        bl = base_loc.set_index("id")
        loc_rows, loc_idx = [], {}
        for i, lid in enumerate(locs):
            loc_idx[lid] = i
            if lid in bl.index:
                b = bl.loc[lid]
                loc_rows.append({"id": lid, "m": b.cd_ibge, "n": b["nome"], "bt": b.bairro_tse, "lat": float(b.lat), "lon": float(b.lon),
                                 "aprox": int(b.aproximado), "bi": b.cd_bairro or None, "ap": int(b.aptos)})
            else:
                cd = lid.split("-")[0]
                loc_rows.append({"id": lid, "m": tse2ibge[cd], "n": f"Local {lid.split('-')[2]}", "bt": "", "lat": None, "lon": None,
                                 "aprox": 1, "bi": None, "ap": 0})
        # totais por local
        tl = x.groupby(["lid", "tipo"]).QT_VOTOS.sum().unstack(fill_value=0)
        for r in loc_rows:
            t = tl.loc[r["id"]] if r["id"] in tl.index else {}
            r["cp"] = int(sum(t.get(k, 0) for k in "bnlc")); r["v"] = int(t.get("l", 0) + t.get("c", 0))
            r["b"] = int(t.get("b", 0)); r["nu"] = int(t.get("n", 0))
            r["ap"] = max(r["ap"], r["cp"])
        L = pd.DataFrame(loc_rows)
        L["mi"] = L.m.map(mun_idx); L["bix"] = L.bi.map(lambda b: b_idx.get(b) if b else None)

        # municípios e estado
        def soma(g):
            return {"ap": int(g.ap.sum()), "cp": int(g.cp.sum()), "v": int(g.v.sum()), "b": int(g.b.sum()), "nu": int(g.nu.sum())}
        munis = []
        for i, mid in enumerate(mun_ids):
            g = L[L.mi == i]; d = soma(g); d.update({"id": mid, "n": base_mun.nome[i]}); munis.append(d)
        bairros_out = []
        for i, bid in enumerate(b_ids):
            g = L[L.bix == i]; d = soma(g); d.update({"id": bid, "m": bairros.cd_ibge[i], "n": bairros.nome[i], "nloc": int(len(g))}); bairros_out.append(d)
        est = soma(L)

        # candidatos
        xc = x[x.tipo == "c"]
        tot_c = xc.groupby("NR_VOTAVEL").QT_VOTOS.sum().sort_values(ascending=False)
        nomes = xc.drop_duplicates("NR_VOTAVEL").set_index("NR_VOTAVEL").NM_VOTAVEL
        cnr = list(tot_c.index); c_idx = {n: i for i, n in enumerate(cnr)}
        xc = xc.assign(li=xc.lid.map(loc_idx))
        cl = xc.groupby(["NR_VOTAVEL", "li"]).QT_VOTOS.sum()
        L2 = L.set_index(L.index)
        cands, locais_por_cand = [], {}
        for nr in cnr:
            s = cl.loc[nr]
            mv = s.groupby(L2.mi.reindex(s.index).values).sum()
            bv = s.groupby(L2.bix.reindex(s.index).values).sum()
            cands.append({"nr": int(nr), "nome": titulo(nomes[nr]), "p": int(str(nr)[:2]), "t": int(tot_c[nr]),
                          "m": [v for k, val in mv.items() for v in (int(k), int(val))],
                          "bz": [v for k, val in bv.items() if k == k for v in (int(k), int(val))]})
            locais_por_cand[int(nr)] = [v for k, val in s.items() for v in (int(k), int(val))]

        # partidos (nominal + legenda), por município
        xp = x[x.tipo.isin(["c", "l"])].assign(mi=lambda d: d.lid.map(loc_idx).map(L.mi))
        pn = xp.groupby(["partido", "tipo"]).QT_VOTOS.sum().unstack(fill_value=0)
        pm = xp.groupby(["partido", "mi"]).QT_VOTOS.sum()
        nome_leg = x[x.tipo == "l"].drop_duplicates("NR_VOTAVEL").set_index("NR_VOTAVEL").NM_VOTAVEL
        parts = []
        for pnr in pn.assign(t=pn.sum(axis=1)).sort_values("t", ascending=False).index:
            s = pm.loc[pnr]
            parts.append({"nr": int(pnr), "sigla": PARTIDOS.get(int(pnr), f"nº {pnr}"),
                          "nome": titulo(nome_leg[pnr]) if pnr in nome_leg.index else PARTIDOS.get(int(pnr), ""),
                          "nom": int(pn.loc[pnr].get("c", 0)), "leg": int(pn.loc[pnr].get("l", 0)),
                          "nc": int((xc.drop_duplicates("NR_VOTAVEL").NR_VOTAVEL.astype(str).str[:2] == str(pnr)).sum()),
                          "m": [v for k, val in s.items() for v in (int(k), int(val))]})

        meta = {"id": cid, "cargo": cargo, "eleicao": x.DS_ELEICAO.iloc[0], "data": x.DT_ELEICAO.iloc[0],
                "nominais": int(xc.QT_VOTOS.sum()), "legenda": int(x[x.tipo == "l"].QT_VOTOS.sum())}
        loc_pub = [{k: r[k] for k in ("id", "m", "n", "bt", "lat", "lon", "aprox", "bi", "ap", "cp", "v", "b", "nu")} for r in loc_rows]
        out = {"meta": meta, "estado": est, "partidos": parts, "cands": cands, "munis": munis, "bairros": bairros_out, "locais": loc_pub}
        (DOCS / f"dep_{cid}.js").write_text(f"window.DEP={compacto(out)};\n", encoding="utf-8")
        (DOCS / f"dep_{cid}_locais.js").write_text(f"window.DEP_LOCAIS={compacto(locais_por_cand)};\n", encoding="utf-8")

        # CSVs
        pasta = DOCS / "dados" / f"dep_{cid}"; pasta.mkdir(parents=True, exist_ok=True)
        with open(pasta / "votos_candidatos_municipios.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["numero", "candidato", "partido", "cd_ibge", "municipio", "votos", "validos_municipio", "pct_validos"])
            for c in cands:
                for k in range(0, len(c["m"]), 2):
                    mu = munis[c["m"][k]]; v = c["m"][k + 1]
                    w.writerow([c["nr"], c["nome"], PARTIDOS.get(c["p"], c["p"]), mu["id"], mu["n"], v, mu["v"], round(100 * v / mu["v"], 3) if mu["v"] else ""])
        with open(pasta / "votos_partidos_municipios.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["numero", "partido", "cd_ibge", "municipio", "votos_nominais_e_legenda", "validos_municipio", "pct_validos"])
            for p in parts:
                for k in range(0, len(p["m"]), 2):
                    mu = munis[p["m"][k]]; v = p["m"][k + 1]
                    w.writerow([p["nr"], p["sigla"], mu["id"], mu["n"], v, mu["v"], round(100 * v / mu["v"], 3) if mu["v"] else ""])

        sz = (DOCS / f"dep_{cid}.js").stat().st_size // 1024, (DOCS / f"dep_{cid}_locais.js").stat().st_size // 1024
        print(f"{cargo}: {len(cands)} candidatos, {len(parts)} partidos, válidos {est['v']:,} (nominais {meta['nominais']:,}, legenda {meta['legenda']:,}), "
              f"brancos {est['b']:,}, nulos {est['nu']:,}; arquivos {sz[0]} KB + {sz[1]} KB", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(RAIZ / "dados_tse" / "votacao_secao_2026_RN.csv"))
