"""Gera docs/digital.js para a página de acompanhamento digital (redes sociais).

Entrada:
  dados_digitais/powerbi_extracao.json  dados do painel público "Acompanhamento Eleitoral - Governo RN - Redes Sociais"
                                        (Power BI), extraídos com as consultas do próprio painel: seguidores, posts,
                                        engajamento e interações por perfil e dia, e publicações do Instagram
  dados_digitais/meta_ads.txt           gasto em anúncios na Meta (Biblioteca de Anúncios, valor acumulado da janela
                                        informada pela Meta) por página e dia
  docs/governador.js, docs/governador_2t.js e o votacao_secao (Senador)  resultados oficiais

Uso:  python scripts/gerar_digital.py
"""
import json, sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DD, DOCS = RAIZ / "dados_digitais", RAIZ / "docs"

PERFIS = {
    "gov": [("allysonbezerra.rn", ["allysonbezerra.rn"], "Allyson Bezerra", 44),
            ("caduxavier", ["caduxavier"], "Cadu de Lula", 13),
            ("alvarodiasrn", ["alvarodiasrn"], "Álvaro Dias", 22)],
    "sen": [("senadorstyvensonvalentim", ["senadorstyvensonvalentim"], "Styvenson Valentim", 200),
            ("samanda", ["samandaalves", "samanda"], "Samanda Alves", 131),
            ("drazenaide", ["drazenaide"], "Zenaide Maia", 555),
            ("coronelheliorn", ["coronelheliorn", "coronelheliorn222"], "Coronel Hélio", 222),
            ("rafaelmottarn", ["rafaelmottarn"], "Rafael Motta", 123)],
}


def js(nome):
    s = (DOCS / nome).read_text(encoding="utf-8"); return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))


def main():
    d = json.loads((DD / "powerbi_extracao.json").read_text(encoding="utf-8"))
    alias = {a: p for grupo in PERFIS.values() for p, als, _, _ in grupo for a in als}
    d0 = min(r[1] for r in d["fol"]); d1 = max(r[1] for r in d["fol"])
    dias = [(date.fromisoformat(d0) + timedelta(i)).isoformat() for i in range((date.fromisoformat(d1) - date.fromisoformat(d0)).days + 1)]
    di = {x: i for i, x in enumerate(dias)}
    serie = lambda: [None] * len(dias)
    S = defaultdict(lambda: defaultdict(serie))
    for nm, dt, ch, tot in d["fol"]:
        p = alias.get(nm)
        if p and dt in di:
            S[p]["nov"][di[dt]] = (S[p]["nov"][di[dt]] or 0) + (ch or 0)
            if tot: S[p]["seg"][di[dt]] = max(S[p]["seg"][di[dt]] or 0, tot)
    for nm, dt, up, tp in d["posts"]:
        p = alias.get(nm)
        if p and dt in di: S[p]["posts"][di[dt]] = (S[p]["posts"][di[dt]] or 0) + (tp or 0)
    for nm, dt, e, _ in d["eng"]:
        p = alias.get(nm)
        if p and dt in di and e is not None: S[p]["eng"][di[dt]] = e
    for nm, dt, lk, cm, sh, sv, tot in d["int"]:
        p = alias.get(nm)
        if p and dt in di:
            for k, v in (("lik", lk), ("com", cm), ("int", tot)):
                S[p][k][di[dt]] = (S[p][k][di[dt]] or 0) + (v or 0)
    # publicações: uma por perfil e horário de publicação (a tabela guarda várias coletas do mesmo post)
    posts, vistos = defaultdict(dict), set()
    for nm, pub, tipo, lk, cm, sh, link, txt in d["tp"]:
        p = alias.get(nm)
        if not p or not pub:
            continue
        lk, cm = int(float(lk or 0)), int(float(cm or 0))
        cur = posts[p].get(pub)
        if not cur or lk > cur[2]:
            posts[p][pub] = [pub, tipo, lk, cm, link or (cur and cur[4]), txt or (cur and cur[5])]
    # tipos de post e média de curtidas por dia
    for p, ps in posts.items():
        for pub, tipo, lk, cm, link, txt in ps.values():
            i = di.get(pub[:10])
            if i is None: continue
            S[p]["np"][i] = (S[p]["np"][i] or 0) + 1
            S[p]["lk_p"][i] = (S[p]["lk_p"][i] or 0) + lk
    top = {p: sorted([x for x in ps.values() if x[5]], key=lambda x: -x[2])[:40] for p, ps in posts.items()}
    tipos = {p: dict(pd.Series([x[1] for x in ps.values()]).value_counts()) for p, ps in posts.items()}

    ads = {}
    for ln in (DD / "meta_ads.txt").read_text(encoding="utf-8").split():
        p, ini, vals = ln.split("|")
        p = alias.get(p, p)
        start = date.fromisoformat(f"2026-{ini}")
        ads[p] = [[(start + timedelta(i)).isoformat(), int(v)] for i, v in enumerate(vals.split(","))]

    # resultados oficiais e municípios
    g1, g2 = js("governador.js"), js("governador_2t.js")
    res = {}
    def por_muni(D, nr):
        k = next(c["k"] for c in D["cands"] if c["nr"] == nr)
        mun = []
        ganhou = 0
        for m in D["munis"]:
            if not m["v"]: continue
            mun.append([m["n"], round(100 * m["vt"][k] / m["v"], 2), m["vt"][k]])
            if max(range(len(m["vt"])), key=lambda j: m["vt"][j]) == k: ganhou += 1
        mun.sort(key=lambda x: -x[1])
        return {"v": D["estado"]["vt"][k], "p": round(100 * D["estado"]["vt"][k] / D["estado"]["v"], 2), "mun": ganhou, "top": mun[:15]}
    for p, _, nome, nr in PERFIS["gov"]:
        res[p] = {"t1": por_muni(g1, nr)}
        if any(c["nr"] == nr for c in g2["cands"]):
            res[p]["t2"] = por_muni(g2, nr)
    s = pd.read_csv(RAIZ / "dados_tse" / "votacao_secao_2026_RN.csv", sep=";", encoding="latin1", dtype=str,
                    usecols=["DS_CARGO", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_VOTAVEL", "QT_VOTOS"])
    s = s[s.DS_CARGO == "Senador"].copy(); s["QT_VOTOS"] = s.QT_VOTOS.astype(int); s["NR_VOTAVEL"] = s.NR_VOTAVEL.astype(int)
    s = s[~s.NR_VOTAVEL.isin([95, 96])]
    tm = s.groupby(["CD_MUNICIPIO", "NR_VOTAVEL"]).QT_VOTOS.sum().unstack(fill_value=0)
    nomes_m = dict(zip(g1["munis"][i]["cd"] if "cd" in g1["munis"][i] else None, [m["n"] for m in g1["munis"]]) for i in [])
    cd2n = {str(m["cd"]): m["n"] for m in g1["munis"]}
    valid_m = tm.sum(1); vencedor = tm.idxmax(axis=1)
    tot_valid = int(tm.values.sum())
    for p, _, nome, nr in PERFIS["sen"]:
        col = tm[nr]
        pct = (100 * col / valid_m).round(2)
        top_m = sorted([[cd2n.get(str(int(cd)), cd), float(pct[cd]), int(col[cd])] for cd in tm.index], key=lambda x: -x[1])[:15]
        res[p] = {"t1": {"v": int(col.sum()), "p": round(100 * col.sum() / tot_valid, 2), "mun": int((vencedor == nr).sum()), "top": top_m}}

    out = {"fonte": "Painel público Acompanhamento Eleitoral - Governo RN - Redes Sociais (Power BI)",
           "dias": [dias[0], dias[-1]], "n": len(dias),
           "grupos": {g: [{"id": p, "nome": nome, "nr": nr, "perfil": als[-1]} for p, als, nome, nr in grupo] for g, grupo in PERFIS.items()},
           "serie": {p: dict(v) for p, v in S.items() if p in alias.values()},
           "top": top, "tipos": {p: {k: int(v) for k, v in t.items()} for p, t in tipos.items()},
           "ads": ads, "res": res}
    (DOCS / "digital.js").write_text("window.DIG=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"digital.js: {(DOCS / 'digital.js').stat().st_size // 1024} KB, {len(dias)} dias ({dias[0]} a {dias[-1]})", file=sys.stderr)
    for g, grupo in PERFIS.items():
        for p, _, nome, _ in grupo:
            sr = S[p]; ult = max(i for i, v in enumerate(sr["seg"]) if v)
            print(f"  {nome:20s} seguidores {sr['seg'][ult]:>8,} ({dias[ult]}); posts {len(posts[p])}; "
                  f"1º turno {res[p]['t1']['p']}% e {res[p]['t1']['mun']} municípios", file=sys.stderr)


if __name__ == "__main__":
    main()
