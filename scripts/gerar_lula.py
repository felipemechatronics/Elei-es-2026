"""Estima como os eleitores de cada candidato a Presidente votaram para Governador (RN, 1º turno).

O voto é secreto: não existe dado de "quem votou em Lula e em quem votou para governador".
O que existe é o resultado de cada seção para os dois cargos (os mesmos eleitores votam nos
dois na mesma urna). A partir dessas ~8 mil seções, a relação é estimada por inferência
ecológica:

1. Em cada seção, s = parcela de cada opção para Presidente (Lula, Flávio, outros, branco/nulo)
   e g = parcela de cada opção para Governador (Allyson, Cadu, Álvaro, outros, branco/nulo).
2. Procura-se a matriz de transição P (4 x 5, cada linha soma 1, sem valores negativos) tal que
   g ≈ s · P em todas as seções, por mínimos quadrados ponderados pelo comparecimento.
3. Isso é feito para o estado e, para cada município, com as seções do município puxadas em
   direção à matriz estadual (encolhimento), o que evita estimativas instáveis onde há poucas seções.
4. As contagens estimadas de cada município são ajustadas (IPF) para bater exatamente com os
   votos reais de cada candidato a governador e com a proporção real de cada candidato a presidente.
5. Intervalos de 90% por reamostragem (bootstrap) das seções.

Grava docs/lula.js (window.LULA) e docs/dados/lula/*.csv.

Uso:
  python scripts/gerar_lula.py dados_tse/Urnas_Presidente.xlsx dados_tse/votacao_secao_2026_RN.csv
"""
import csv, json, sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

RAIZ = Path(__file__).resolve().parent.parent
DOCS, BASE = RAIZ / "docs", RAIZ / "base"
PRES = ["lula", "flavio", "outros", "bn"]
GOV = ["allyson", "cadu", "alvaro", "outros", "bn"]
ANULADOS = {29, 50}          # governador: votos que a totalização trata como nulos
LAMBDA = 30.0                # força do encolhimento municipal (em "seções equivalentes")
NBOOT = int(__import__("os").environ.get("NBOOT", 200))
rng = np.random.default_rng(2026)


def cat_p(n):
    return "lula" if n == 13 else "flavio" if n == 22 else "bn" if n in (95, 96) else "outros"


def cat_g(n):
    if n in ANULADOS or n in (95, 96):
        return "bn"
    return "allyson" if n == 44 else "cadu" if n == 13 else "alvaro" if n == 22 else "outros"


def ler(arq_pres, arq_gov):
    bu = pd.read_excel(arq_pres, dtype=str) if str(arq_pres).endswith("xlsx") else pd.read_csv(arq_pres, sep=";", encoding="latin1", dtype=str)
    if "DS_CARGO_PERGUNTA" in bu:
        bu = bu[bu.DS_CARGO_PERGUNTA.str.upper().str.startswith("PRESIDENTE")]
    for c in ("CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_VOTAVEL", "QT_VOTOS"):
        bu[c] = bu[c].astype(int)
    bu["c"] = bu.NR_VOTAVEL.map(cat_p)
    P = bu.pivot_table(index=["CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"], columns="c", values="QT_VOTOS", aggfunc="sum", fill_value=0)
    gv = pd.read_csv(arq_gov, sep=";", encoding="latin1", dtype=str,
                     usecols=["DS_CARGO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_VOTAVEL", "QT_VOTOS"])
    gv = gv[(gv.DS_CARGO == "Governador") & (gv.NR_TURNO == "1") & (gv.SG_UF == "RN")]
    for c in ("CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "NR_VOTAVEL", "QT_VOTOS"):
        gv[c] = gv[c].astype(int)
    gv["c"] = gv.NR_VOTAVEL.map(cat_g)
    G = gv.pivot_table(index=["CD_MUNICIPIO", "NR_ZONA", "NR_SECAO"], columns="c", values="QT_VOTOS", aggfunc="sum", fill_value=0)
    P = P.reindex(columns=PRES, fill_value=0); G = G.reindex(columns=GOV, fill_value=0)
    J = P.join(G, lsuffix="_p", rsuffix="_g", how="inner")
    print(f"seções: presidente {len(P)}, governador {len(G)}, casadas {len(J)}", file=sys.stderr)
    J = J.reset_index()
    Xc = J[[f"{c}_p" if c in ("outros", "bn") else c for c in PRES]].to_numpy(float)
    Yc = J[[f"{c}_g" if c in ("outros", "bn") else c for c in GOV]].to_numpy(float)
    return J, Xc, Yc


def ajustar(XtX, XtY, prior=None, lam=0.0, x0=None):
    """min ||Y - X P||²_W (+ lam ||P - prior||²) com linhas de P no simplex."""
    k, m = XtY.shape
    A = XtX + (lam * np.eye(k) if lam else 0)
    B = XtY + (lam * prior if lam else 0)

    def f(p):
        Pm = p.reshape(k, m)
        return np.sum(Pm * (A @ Pm)) - 2 * np.sum(Pm * B)

    def gr(p):
        Pm = p.reshape(k, m)
        return (2 * (A @ Pm) - 2 * B).ravel()

    cons = [{"type": "eq", "fun": (lambda p, i=i: p.reshape(k, m)[i].sum() - 1), "jac": (lambda p, i=i: np.eye(k)[i].repeat(m) * 1.0)}
            for i in range(k)]
    x0 = np.full(k * m, 1 / m) if x0 is None else x0.ravel()
    r = minimize(f, x0, jac=gr, bounds=[(0, 1)] * (k * m), constraints=cons, method="SLSQP", options={"maxiter": 500, "ftol": 1e-12})
    if not r.success:
        print("aviso: otimizador:", r.message, file=sys.stderr)
    Pm = np.clip(r.x.reshape(k, m), 0, None)
    return Pm / Pm.sum(1, keepdims=True)


def momentos(Xc, Yc, w=None):
    """Matrizes normais com parcelas por seção ponderadas pelo comparecimento."""
    t = Xc.sum(1); ok = t > 0
    X = Xc[ok] / t[ok, None]; Y = Yc[ok] / np.maximum(Yc[ok].sum(1), 1)[:, None]
    wt = t[ok] * (1 if w is None else w[ok])
    sw = wt.sum(); wn = wt / max(sw, 1e-12)          # pesos normalizados: escala estável para o otimizador
    return (X * wn[:, None]).T @ X, (X * wn[:, None]).T @ Y, sw


def ipf(N, lin, col, it=200):
    N = N.copy() + 1e-9
    for _ in range(it):
        N *= (lin / np.maximum(N.sum(1), 1e-12))[:, None]
        N *= (col / np.maximum(N.sum(0), 1e-12))[None, :]
    return N


def estimar(J, Xc, Yc, mun_codes, w=None):
    XtX, XtY, _ = momentos(Xc, Yc, w)
    Pest = ajustar(XtX, XtY)
    tot = np.zeros((len(PRES), len(GOV))); por_mun = {}
    for cd in mun_codes:
        idx = np.flatnonzero(J.CD_MUNICIPIO.to_numpy() == cd)
        if not len(idx):
            continue
        ww = None if w is None else w[idx]
        if ww is not None and ww.sum() == 0:
            ww = np.ones(len(idx))
        a, b, sw = momentos(Xc[idx], Yc[idx], ww)
        # encolhimento: LAMBDA seções "médias" do município equivalem à matriz estadual
        lam = LAMBDA / max(len(idx), 1)               # matrizes já normalizadas: lam = LAMBDA seções / nº de seções
        Pm = ajustar(a, b, prior=Pest, lam=lam, x0=Pest)
        lin = (Xc[idx] * (1 if ww is None else ww[:, None])).sum(0)
        col = (Yc[idx] * (1 if ww is None else ww[:, None])).sum(0)
        # colunas = votos reais para governador; linhas = votos para presidente reescalados ao mesmo total
        # (as duas apurações diferem em poucas seções, 0,15% dos votos no estado)
        lin = lin * col.sum() / max(lin.sum(), 1)
        N = ipf(lin[:, None] * Pm, lin, col)
        por_mun[cd] = (Pm, N); tot += N
    return Pest, tot, por_mun


def _boot(J, Xc, Yc, mun_codes, w):
    _, tb, _ = estimar(J, Xc, Yc, mun_codes, w)
    return tb / tb.sum(1, keepdims=True)   # parcela de cada linha (o bootstrap muda o total de votos)


def main(arq_pres, arq_gov):
    J, Xc, Yc = ler(arq_pres, arq_gov)
    base_mun = pd.read_csv(BASE / "municipios.csv", dtype=str)
    tse2ibge = dict(zip(base_mun.cd_tse.astype(int), base_mun.cd_ibge))
    nomes = dict(zip(base_mun.cd_ibge, base_mun.nome))
    mun_codes = sorted(J.CD_MUNICIPIO.unique())

    Pest, tot, por_mun = estimar(J, Xc, Yc, mun_codes)
    # qualidade do ajuste: R² por candidato a governador nas seções (modelo municipal)
    pred = np.zeros_like(Yc)
    for cd, (Pm, _) in por_mun.items():
        idx = J.CD_MUNICIPIO.to_numpy() == cd
        t = Xc[idx].sum(1, keepdims=True)
        pred[idx] = (Xc[idx] / np.maximum(t, 1)) @ Pm
    yo = Yc / np.maximum(Yc.sum(1, keepdims=True), 1); wt = Xc.sum(1)
    r2 = {}
    for j, g in enumerate(GOV):
        mu = np.average(yo[:, j], weights=wt)
        r2[g] = round(1 - np.sum(wt * (yo[:, j] - pred[:, j]) ** 2) / np.sum(wt * (yo[:, j] - mu) ** 2), 3)
    print("R² municipal:", r2, file=sys.stderr)
    XtX, XtY, _ = momentos(Xc, Yc)
    r2e = {}
    pe = (Xc / np.maximum(Xc.sum(1, keepdims=True), 1)) @ Pest
    for j, g in enumerate(GOV):
        mu = np.average(yo[:, j], weights=wt)
        r2e[g] = round(1 - np.sum(wt * (yo[:, j] - pe[:, j]) ** 2) / np.sum(wt * (yo[:, j] - mu) ** 2), 3)
    print("R² estadual:", r2e, file=sys.stderr)

    # bootstrap: reamostra seções (pesos multinomiais dentro de cada município)
    muni_arr = J.CD_MUNICIPIO.to_numpy()
    grupos = {cd: np.flatnonzero(muni_arr == cd) for cd in mun_codes}
    pesos = []
    for b in range(NBOOT):
        w = np.zeros(len(J))
        for cd, idx in grupos.items():
            w[idx] = rng.multinomial(len(idx), np.full(len(idx), 1 / len(idx)))
        pesos.append(w)
    from concurrent.futures import ProcessPoolExecutor
    from functools import partial
    with ProcessPoolExecutor() as ex:
        boots = np.array(list(ex.map(partial(_boot, J, Xc, Yc, mun_codes), pesos)))
    lo, hi = np.percentile(boots, 5, axis=0), np.percentile(boots, 95, axis=0)

    lin_tot = tot.sum(1)
    share = tot / lin_tot[:, None]
    print("\nDestino estimado (linhas = presidente, % das colunas de governador):", file=sys.stderr)
    for i, p in enumerate(PRES):
        print(f"  {p:7s} " + "  ".join(f"{g}={100 * share[i, j]:5.1f} [{100 * lo[i, j]:4.1f}-{100 * hi[i, j]:4.1f}]" for j, g in enumerate(GOV)), file=sys.stderr)

    # dados por município para o site
    munis = []
    for cd in mun_codes:
        Pm, N = por_mun[cd]
        idx = grupos[cd]
        munis.append({"id": tse2ibge[cd], "n": nomes[tse2ibge[cd]], "s": int(len(idx)),
                      "p": [int(v) for v in Xc[idx].sum(0)], "g": [int(v) for v in Yc[idx].sum(0)],
                      "N": [[int(round(v)) for v in row] for row in N]})
    # seções (para o gráfico de dispersão): % lula, % cadu, % allyson, % álvaro (sobre comparecimento), comparecimento, município
    mi = {cd: i for i, cd in enumerate(mun_codes)}
    tp = Xc.sum(1); tg = Yc.sum(1)
    sec = []
    for k in range(len(J)):
        if tp[k] == 0 or tg[k] == 0:
            continue
        sec += [round(100 * Xc[k, 0] / tp[k], 1), round(100 * Yc[k, 1] / tg[k], 1), round(100 * Yc[k, 0] / tg[k], 1),
                round(100 * Yc[k, 2] / tg[k], 1), int(tp[k]), mi[J.CD_MUNICIPIO[k]]]

    out = {"meta": {"secoes": int(len(J)), "lambda": LAMBDA, "nboot": NBOOT, "r2": r2, "r2_estadual": r2e,
                    "pres": PRES, "gov": GOV},
           "P_estadual": [[round(v, 4) for v in r] for r in Pest],
           "N": [[int(round(v)) for v in r] for r in tot],
           "lo": [[round(v, 4) for v in r] for r in lo], "hi": [[round(v, 4) for v in r] for r in hi],
           "munis": munis, "sec": sec}
    (DOCS / "lula.js").write_text("window.LULA=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    pasta = DOCS / "dados" / "lula"; pasta.mkdir(parents=True, exist_ok=True)
    rot_p = {"lula": "Lula", "flavio": "Flávio Bolsonaro", "outros": "Outros", "bn": "Branco/nulo"}
    rot_g = {"allyson": "Allyson Bezerra", "cadu": "Cadu de Lula", "alvaro": "Álvaro Dias", "outros": "Outros", "bn": "Branco/nulo"}
    with open(pasta / "transferencia_estimada_municipios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cd_ibge", "municipio", "voto_presidente", "votos_presidente"] + [f"estim_{rot_g[g]}" for g in GOV])
        for m in munis:
            for i, p in enumerate(PRES):
                w.writerow([m["id"], m["n"], rot_p[p], m["p"][i]] + m["N"][i])
    with open(pasta / "transferencia_estimada_estado.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["voto_presidente", "governador", "votos_estimados", "pct_da_linha", "ic90_min_pct", "ic90_max_pct"])
        for i, p in enumerate(PRES):
            for j, g in enumerate(GOV):
                w.writerow([rot_p[p], rot_g[g], int(round(tot[i, j])), round(100 * share[i, j], 2), round(100 * lo[i, j], 2), round(100 * hi[i, j], 2)])
    print(f"\ndocs/lula.js: {(DOCS / 'lula.js').stat().st_size // 1024} KB", file=sys.stderr)


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else str(RAIZ / "dados_tse" / "Urnas_Presidente.xlsx")
    b = sys.argv[2] if len(sys.argv) > 2 else str(RAIZ / "dados_tse" / "votacao_secao_2026_RN.csv")
    main(a, b)
