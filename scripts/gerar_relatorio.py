"""Gera o relatório estático de cada cargo (relatorio/<cargo>/RELATORIO.md) com gráficos e mapas em PNG.

Usa os docs/<cargo>.js produzidos por gerar_dados.py, então rode aquele primeiro:

  python scripts/gerar_dados.py <arquivo do TSE> --cargo Presidente
  python scripts/gerar_relatorio.py              # todos os cargos gerados
  python scripts/gerar_relatorio.py presidente   # só um
"""
import json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon, Patch
from matplotlib.colors import to_rgb

RAIZ = Path(__file__).resolve().parent.parent
REL = RAIZ / "relatorio"
SITE = "https://felipemechatronics.github.io/Elei-es-2026/"

CORES = ["#2a78d6", "#eb6834", "#1baf7a"]
OUTROS = "#c3c9ce"
VAZIO = "#eceff1"
TINTA, TINTA2, LINHA = "#15212c", "#4a5966", "#dce2e6"
MB, MSTEP = (5, 15, 30), (0.38, 0.58, 0.8, 1.0)

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": TINTA,
                     "axes.edgecolor": LINHA, "axes.labelcolor": TINTA2, "xtick.color": TINTA2,
                     "ytick.color": TINTA2, "figure.dpi": 150, "savefig.bbox": "tight",
                     "savefig.facecolor": "white"})


def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def n(x):
    return f"{int(x):,}".replace(",", ".")


def mix(c, t):
    r, g, b = to_rgb(c)
    return (1 - t + t * r, 1 - t + t * g, 1 - t + t * b)


def ler_js(nome):
    s = (RAIZ / "docs" / nome).read_text(encoding="utf-8")
    return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))


def main():
    ids = sys.argv[1:] or [c["id"] for c in ler_js("cargos.js")]
    geo = ler_js("geo.js")
    for cid in ids:
        D = ler_js(f"{cid}.js")
        D.update(geo)
        gerar(D, REL / cid)


def gerar(D, PASTA):
    IMG = PASTA / "img"
    IMG.mkdir(parents=True, exist_ok=True)
    C, E = D["cands"], D["estado"]
    NT = min(3, len(C))
    TOP = C[:NT]
    munis = {m["id"]: m for m in D["munis"]}
    bairros = {b["id"]: b for b in D["bairros"]}
    meta = D["meta"]

    def cor(k):
        return CORES[C[k]["cor"]] if (k < NT and C[k].get("cor") is not None) else OUTROS

    def rank(u):
        if not u["v"]:
            return None
        o = sorted(range(len(u["vt"])), key=lambda k: -u["vt"][k])
        s = o[1] if len(o) > 1 else None
        mg = 100 * (u["vt"][o[0]] - (u["vt"][s] if s is not None else 0)) / u["v"]
        return {"w": o[0], "s": s, "mg": mg, "pw": 100 * u["vt"][o[0]] / u["v"]}

    def fill_margem(u):
        r = rank(u)
        if not r:
            return VAZIO
        i = 0 if r["mg"] < MB[0] else 1 if r["mg"] < MB[1] else 2 if r["mg"] < MB[2] else 3
        return mix(cor(r["w"]), MSTEP[i])

    def pct(u, k):
        return 100 * u["vt"][k] / u["v"] if u["v"] else 0

    def desenhar(ax, feats, cores_):
        patches, fc = [], []
        for f, c in zip(feats, cores_):
            g = f["geometry"]
            polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            for p in polys:
                patches.append(Polygon(p[0], closed=True)); fc.append(c)
        ax.add_collection(PatchCollection(patches, facecolor=fc, edgecolor="white", linewidth=0.5))
        ax.autoscale_view(); ax.set_aspect(1 / 0.994); ax.axis("off")

    def legenda_margem(ax, loc="lower left"):
        h = []
        for c in TOP:
            h.append(Patch(facecolor=cor(c["k"]), label=c["nome"]))
        lg = ax.legend(handles=h, loc=loc, frameon=False, fontsize=9, title="Cor mais forte = vantagem maior",
                       title_fontsize=8.5)
        lg._legend_box.align = "left"

    r0 = rank(E)
    W, S = C[r0["w"]], C[r0["s"]]
    ms = [m for m in D["munis"] if m["v"]]
    wins = {}
    for m in ms:
        wins[rank(m)["w"]] = wins.get(rank(m)["w"], 0) + 1

    # 1. resultado no estado
    rows = [(c["nome"], c["partido"], E["vt"][c["k"]], c["k"]) for c in C[:6]]
    resto = E["v"] - sum(r[2] for r in rows)
    if resto > 0:
        rows.append((f"Demais ({len(C) - 6})", "", resto, 99))
    fig, ax = plt.subplots(figsize=(8, 0.48 * len(rows) + 0.6))
    for i, (nm, pt, v, k) in enumerate(rows):
        ax.barh(i, 100 * v / E["v"], color=cor(k), height=0.62)
        ax.text(100 * v / E["v"] + 0.8, i, f"{br(100 * v / E['v'])}%  ({n(v)})", va="center", fontsize=9.5)
    ax.set_yticks(range(len(rows)), [f"{nm}  {pt}".strip() for nm, pt, _, _ in rows])
    ax.invert_yaxis(); ax.set_xlim(0, max(100 * r[2] / E["v"] for r in rows) * 1.35)
    ax.set_xticks([]); [ax.spines[s].set_visible(False) for s in ("top", "right", "bottom")]
    ax.set_title(f"{meta['cargo']} no RN, {meta['turno']}º turno: % dos votos válidos", loc="left", fontsize=12, fontweight="bold")
    fig.savefig(IMG / "resultado_rn.png"); plt.close(fig)

    # 2. mapa do vencedor por município
    feats = D["mapa"]["features"]
    fig, ax = plt.subplots(figsize=(9, 6.2))
    desenhar(ax, feats, [fill_margem(munis[f["properties"]["id"]]) for f in feats])
    legenda_margem(ax)
    ax.set_title("Quem ficou à frente em cada município", loc="left", fontsize=13, fontweight="bold")
    fig.savefig(IMG / "mapa_vencedor.png"); plt.close(fig)

    # 3. mapas de percentual por candidato
    fig, axs = plt.subplots(1, NT, figsize=(5.2 * NT, 4))
    axs = [axs] if NT == 1 else axs
    for ax, c in zip(axs, TOP):
        vals = [pct(munis[f["properties"]["id"]], c["k"]) for f in feats]
        cm = matplotlib.colors.LinearSegmentedColormap.from_list("c", [mix(cor(c["k"]), 0.12), cor(c["k"]),
                                                                         tuple(0.45 * x for x in to_rgb(cor(c["k"])))])
        nrm = matplotlib.colors.Normalize(0, max(vals))
        desenhar(ax, feats, [cm(nrm(v)) for v in vals])
        sm = plt.cm.ScalarMappable(norm=nrm, cmap=cm)
        cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.05, pad=0.02, format="%.0f%%")
        cb.outline.set_visible(False); cb.ax.tick_params(labelsize=8)
        ax.set_title(f"{c['nome']}: {br(pct(E, c['k']))}% no estado", loc="left", fontsize=11, fontweight="bold")
    fig.savefig(IMG / "mapa_percentuais.png"); plt.close(fig)

    # 3b. quantidade de votos nominais (círculos proporcionais)
    def centro(f):
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        ring = max((p[0] for p in polys), key=len)
        A = cx = cy = 0.0
        for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
            c = x0 * y1 - x1 * y0
            A += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c
        return (cx / (3 * A), cy / (3 * A)) if A else tuple(ring[0])
    cen = [centro(f) for f in feats]
    vmax = max(m["vt"][c["k"]] for m in ms for c in TOP)
    fig, axs = plt.subplots(1, NT, figsize=(5.2 * NT, 4))
    axs = [axs] if NT == 1 else axs
    for ax, c in zip(axs, TOP):
        desenhar(ax, feats, [VAZIO] * len(feats))
        vs = [munis[f["properties"]["id"]]["vt"][c["k"]] for f in feats]
        ordem = sorted(range(len(feats)), key=lambda i: -vs[i])
        ax.scatter([cen[i][0] for i in ordem], [cen[i][1] for i in ordem], s=[900 * vs[i] / vmax for i in ordem],
                   color=cor(c["k"]), alpha=0.75, edgecolor="white", linewidth=0.6, zorder=3)
        ax.set_title(f"{c['nome']}: {n(E['vt'][c['k']])} votos", loc="left", fontsize=11, fontweight="bold")
    ref = [r for r in (1000, 10000, 100000) if r <= vmax]
    hs = [plt.scatter([], [], s=900 * r / vmax, color="#9aa5ae", alpha=0.6, edgecolor="white") for r in ref]
    fig.legend(hs, [n(r) + " votos" for r in ref], loc="lower center", ncol=len(ref), frameon=False,
               scatterpoints=1, borderpad=1.2, labelspacing=1.5)
    fig.suptitle("Votos nominais por município (área do círculo proporcional aos votos; mesma escala nos três mapas)",
                 x=0.01, ha="left", fontsize=11)
    fig.savefig(IMG / "mapa_votos.png"); plt.close(fig)

    # 4. abstenção
    fig, ax = plt.subplots(figsize=(9, 6.2))
    vals = [100 * munis[f["properties"]["id"]]["ab"] / munis[f["properties"]["id"]]["ap"] for f in feats]
    cm = matplotlib.colors.LinearSegmentedColormap.from_list("a", ["#e9edf0", "#3b4a57", "#0f1a23"])
    nrm = matplotlib.colors.Normalize(min(vals), max(vals))
    desenhar(ax, feats, [cm(nrm(v)) for v in vals])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=nrm, cmap=cm), ax=ax, orientation="horizontal", fraction=0.04, pad=0.02, format="%.0f%%")
    cb.outline.set_visible(False)
    ax.set_title(f"Abstenção por município (estado: {br(100 * E['ab'] / E['ap'])}%)", loc="left", fontsize=13, fontweight="bold")
    fig.savefig(IMG / "mapa_abstencao.png"); plt.close(fig)

    # 5. bairros das maiores cidades
    bfeat = {f["properties"]["id"]: f for f in D["bmapa"]["features"]}
    by_m = {}
    for b in D["bairros"]:
        by_m.setdefault(b["m"], []).append(b)
    cidades = sorted([m for m in D["munis"] if m["hb"] and len(by_m.get(m["id"], [])) >= 8], key=lambda m: -m["ap"])[:4]
    fig, axs = plt.subplots(2, 2, figsize=(11, 10))
    for ax, m in zip(axs.flat, cidades):
        bs = [b for b in by_m[m["id"]] if b["id"] in bfeat]
        desenhar(ax, [bfeat[b["id"]] for b in bs], [fill_margem(b) if b["v"] else VAZIO for b in bs])
        r = rank(m)
        ax.set_title(f"{m['n']}: {C[r['w']]['nome']} {br(r['pw'])}%", loc="left", fontsize=12, fontweight="bold")
    for ax in list(axs.flat)[len(cidades):]:
        ax.axis("off")
    h = [Patch(facecolor=cor(c["k"]), label=c["nome"]) for c in TOP] + [Patch(facecolor=VAZIO, label="Sem local de votação")]
    fig.legend(handles=h, loc="lower center", ncol=len(h), frameon=False)
    fig.suptitle("Bairros: quem ficou à frente nos locais de votação de cada bairro (cor mais forte = vantagem maior)",
                 x=0.02, ha="left", fontsize=12, fontweight="bold")
    fig.savefig(IMG / "bairros_maiores_cidades.png"); plt.close(fig)

    # 6. por porte
    nat = next((m["id"] for m in D["munis"] if m["n"] == "Natal"), None)
    classes = [("Até 10 mil eleitores", lambda m: m["ap"] < 10000), ("10 a 25 mil", lambda m: 10000 <= m["ap"] < 25000),
               ("25 a 80 mil", lambda m: 25000 <= m["ap"] < 80000),
               ("Mais de 80 mil, exceto Natal", lambda m: m["ap"] >= 80000 and m["id"] != nat), ("Natal", lambda m: m["id"] == nat)]
    agg = []
    for nome, f in classes:
        arr = [m for m in D["munis"] if f(m)]
        if not arr:
            continue
        u = {"v": sum(m["v"] for m in arr), "ap": sum(m["ap"] for m in arr),
             "vt": [sum(m["vt"][k] for m in arr) for k in range(len(C))]}
        agg.append((nome, len(arr), u))
    fig, ax = plt.subplots(figsize=(9, 0.62 * len(agg) + 0.9))
    for i, (nome, cnt, u) in enumerate(agg):
        acc = 0
        partes = [u["vt"][c["k"]] for c in TOP] + [u["v"] - sum(u["vt"][c["k"]] for c in TOP)]
        for k, v in enumerate(partes):
            f = 100 * v / u["v"]
            ax.barh(i, f, left=acc, color=cor(k), height=0.66, edgecolor="white", linewidth=1.5)
            if f > 6 and k < NT:
                ax.text(acc + 1.2, i, f"{br(f)}%", va="center", color="white", fontsize=9, fontweight="bold")
            acc += f
    ax.set_yticks(range(len(agg)), [f"{nm}\n{c} munic. · {br(100 * u['ap'] / E['ap'], 0)}% do eleitorado" for nm, c, u in agg], fontsize=8.5)
    ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_xticks([])
    [ax.spines[s].set_visible(False) for s in ax.spines]
    ax.legend(handles=[Patch(facecolor=cor(c["k"]), label=c["nome"]) for c in TOP] + [Patch(facecolor=OUTROS, label="Outros")],
              loc="upper center", bbox_to_anchor=(0.5, 0), ncol=NT + 1, frameon=False)
    ax.set_title("Votos válidos por tamanho do município", loc="left", fontsize=12, fontweight="bold")
    fig.savefig(IMG / "por_porte.png"); plt.close(fig)

    # ---------- texto ----------
    L = []
    data = meta.get("data", "")
    L.append(f"# Eleições 2026 Rio Grande do Norte: {meta['cargo']}, {meta['turno']}º turno")
    L.append("")
    L.append(f"Relatório gerado a partir dos boletins por seção do TSE ({meta.get('eleicao', '')}, {data}). "
             f"Percentuais de candidatos são sobre os votos válidos. Versão interativa, com mapa por bairro e por local de votação: "
             f"[{SITE}?cargo={meta['id']}]({SITE}?cargo={meta['id']}).")
    L.append("")
    L.append("## Resumo")
    L.append("")
    L.append("- Votos válidos no estado: " + "; ".join(f"{c['nome']} ({c['partido']}) {br(pct(E, c['k']))}%" for c in TOP) + ".")
    L.append(f"- Primeiro lugar por município, entre os {len(D['munis'])} do estado: " +
             "; ".join(f"{c['nome']} em {wins[c['k']]}" for c in C if wins.get(c["k"])) + ".")
    L.append(f"- Compareceram {n(E['cp'])} dos {n(E['ap'])} eleitores aptos ({br(100 * E['cp'] / E['ap'])}%). "
             f"Abstenção de {br(100 * E['ab'] / E['ap'])}%. Brancos: {br(100 * E['b'] / E['cp'])}%; nulos: {br(100 * E['nu'] / E['cp'])}% dos votos.")
    L.append("")
    L.append("![Resultado no estado](img/resultado_rn.png)")
    L.append("")
    L.append("| Candidato | Partido | Votos | % válidos |")
    L.append("|---|---|---:|---:|")
    for c in C:
        L.append(f"| {c['nome']} | {c['partido']} | {n(E['vt'][c['k']])} | {br(pct(E, c['k']), 2)}% |")
    L.append(f"| Brancos | | {n(E['b'])} | |")
    L.append(f"| Nulos | | {n(E['nu'])} | |")
    L.append("")

    L.append("## O mapa dos municípios")
    L.append("")
    L.append("![Vencedor por município](img/mapa_vencedor.png)")
    L.append("")
    L.append("![Percentual por candidato](img/mapa_percentuais.png)")
    L.append("")
    L.append("![Votos nominais por município](img/mapa_votos.png)")
    L.append("")
    for c in TOP:
        best = sorted(ms, key=lambda m: -m["vt"][c["k"]])[:5]
        L.append(f"- Mais votos para **{c['nome']}**: " + ", ".join(f"{m['n']} ({n(m['vt'][c['k']])})" for m in best) + ".")
    for c in TOP:
        best = sorted(ms, key=lambda m: -pct(m, c["k"]))[:5]
        L.append(f"- Maiores percentuais de **{c['nome']}**: " + ", ".join(f"{m['n']} ({br(pct(m, c['k']))}%)" for m in best) + ".")
    tight = sorted(ms, key=lambda m: rank(m)["mg"])[:5]
    L.append("- Disputas mais apertadas: " + ", ".join(
        f"{m['n']} ({C[rank(m)['w']]['nome']} por {n(round(rank(m)['mg'] * m['v'] / 100))} votos)" for m in tight) + ".")
    L.append("")

    L.append("## Tamanho da cidade")
    L.append("")
    L.append("![Por porte](img/por_porte.png)")
    L.append("")
    L.append("| Faixa | Municípios | Eleitorado | " + " | ".join(c["nome"] for c in TOP) + " |")
    L.append("|---|---:|---:|" + "---:|" * NT)
    for nome, cnt, u in agg:
        L.append(f"| {nome} | {cnt} | {br(100 * u['ap'] / E['ap'])}% | " + " | ".join(f"{br(pct(u, c['k']))}%" for c in TOP) + " |")
    L.append("")

    L.append("## As maiores cidades")
    L.append("")
    L.append("| Município | Aptos | Comparec. | " + " | ".join(c["nome"] for c in TOP) + " | À frente |")
    L.append("|---|---:|---:|" + "---:|" * NT + "---|")
    for m in sorted(D["munis"], key=lambda m: -m["ap"])[:15]:
        r = rank(m)
        L.append(f"| {m['n']} | {n(m['ap'])} | {br(100 * m['cp'] / m['ap'])}% | " + " | ".join(f"{br(pct(m, c['k']))}% ({n(m['vt'][c['k']])})" for c in TOP) +
                 f" | {C[r['w']]['nome']} +{br(r['mg'])} |")
    L.append("")

    L.append("## Bairro a bairro")
    L.append("")
    L.append("O voto é contado no local onde o eleitor vota, e não onde ele mora. Cada bairro soma os locais de votação "
             "que ficam dentro dos seus limites (IBGE, Censo 2022). Bairros sem local de votação aparecem em cinza.")
    L.append("")
    L.append("![Bairros das maiores cidades](img/bairros_maiores_cidades.png)")
    L.append("")
    for m in cidades:
        bs = sorted([b for b in by_m[m["id"]] if b["v"]], key=lambda b: -b["v"])
        L.append(f"### {m['n']}")
        L.append("")
        bw = {}
        for b in bs:
            bw[rank(b)["w"]] = bw.get(rank(b)["w"], 0) + 1
        L.append(", ".join(f"{C[k]['nome']} ficou à frente em {v} {'bairro' if v == 1 else 'bairros'}" for k, v in sorted(bw.items(), key=lambda x: -x[1])) + ".")
        L.append("")
        L.append("| Bairro | Locais | Votos válidos | " + " | ".join(c["nome"] for c in TOP) + " | Abstenção |")
        L.append("|---|---:|---:|" + "---:|" * NT + "---:|")
        for b in bs:
            L.append(f"| {b['n']} | {b['nloc']} | {n(b['v'])} | " + " | ".join(f"{br(pct(b, c['k']))}% ({n(b['vt'][c['k']])})" for c in TOP) +
                     f" | {br(100 * b['ab'] / b['ap'])}% |")
        L.append("")

    L.append("## Abstenção")
    L.append("")
    L.append("![Abstenção](img/mapa_abstencao.png)")
    L.append("")
    ab = sorted(ms, key=lambda m: -m["ab"] / m["ap"])
    L.append("- Maior abstenção: " + ", ".join(f"{m['n']} ({br(100 * m['ab'] / m['ap'])}%)" for m in ab[:5]) + ".")
    L.append("- Menor abstenção: " + ", ".join(f"{m['n']} ({br(100 * m['ab'] / m['ap'])}%)" for m in ab[::-1][:5]) + ".")
    L.append("")

    L.append("## Metodologia e fontes")
    L.append("")
    L.append("- Votos por seção: TSE, Portal de Dados Abertos, arquivo `votacao_secao`. Somados por local de votação, bairro e município.")
    L.append("- Eleitorado apto, coordenadas dos locais de votação e atribuição de bairros: cadastro de locais do TSE e malhas do IBGE "
             "(municípios e bairros do Censo 2022), na base organizada pelo projeto "
             "[Como o RN votou para governador](https://sousapfe.github.io/eleicoesRN/), de Peterson Sousa.")
    L.append("- Percentuais de candidatos sobre votos válidos; comparecimento e abstenção sobre o eleitorado apto; "
             "brancos e nulos sobre o comparecimento.")
    if meta.get("anulados"):
        L.append(f"- Votos dos candidatos {', '.join(map(str, meta['anulados']))} (registro indeferido ou cassado) contados como nulos.")
    if meta.get("locais_sem_base"):
        L.append(f"- {meta['locais_sem_base']} locais não constam do cadastro georreferenciado: entram nos totais, mas não no mapa.")
    L.append("- Os partidos são inferidos pelo número de urna e podem ser corrigidos em `config/candidatos.json`.")
    L.append("")
    (PASTA / "RELATORIO.md").write_text("\n".join(L), encoding="utf-8")
    print(PASTA / "RELATORIO.md", "e", len(list(IMG.glob("*.png"))), "figuras")


if __name__ == "__main__":
    main()
