"""Relatório em PDF sobre a abstenção no 1º turno de 2026 no Rio Grande do Norte.

Usa os dados gerados para o site (docs/presidente.js e docs/geo.js) e, se disponível,
o boletim de urna de Presidente em dados_tse/ para a análise por seção.

  python scripts/gerar_pdf_abstencao.py
Saída: relatorio/abstencao/abstencao_RN_2026.pdf (+ figuras em relatorio/abstencao/img)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
from matplotlib.colors import BoundaryNorm, ListedColormap

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Image, Table,
                                TableStyle, PageBreak, KeepTogether, NextPageTemplate)

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "relatorio" / "abstencao"
IMG = OUT / "img"
BU = RAIZ / "dados_tse" / "Urnas_Presidente.xlsx"

# paleta sequencial (azul) para abstenção e cores de apoio
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
INK, INK2, MUTED, LINE, EMPTY = "#15212c", "#4a5966", "#7a8792", "#dce2e6", "#eceff1"
LULA, FLAVIO = "#eb6834", "#2a78d6"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK,
                     "axes.edgecolor": LINE, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "figure.dpi": 200, "savefig.bbox": "tight", "savefig.facecolor": "white", "axes.titlesize": 10})


def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def n(x):
    return f"{int(round(x)):,}".replace(",", ".")


def ler_js(nome):
    s = (RAIZ / "docs" / nome).read_text(encoding="utf-8")
    return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))


# ------------------------------------------------------------------ dados
D = ler_js("presidente.js")
G = ler_js("geo.js")
E = D["estado"]
C = D["cands"]
M = pd.DataFrame(D["munis"])
L = pd.DataFrame(D["locais"])
B = pd.DataFrame(D["bairros"])
for X in (M, L, B):
    X["abp"] = np.where(X.ap > 0, 100 * X.ab / X.ap.replace(0, np.nan), np.nan)
M["cand0"] = 100 * M.vt.str[0] / M.v
M["cand1"] = 100 * M.vt.str[1] / M.v
munis = {m["id"]: m for m in D["munis"]}
nome_m = {m["id"]: m["n"] for m in D["munis"]}
L["muni"] = L.m.map(nome_m)
B["muni"] = B.m.map(nome_m)
bfeat = {f["properties"]["id"]: f for f in G["bmapa"]["features"]}
mfeat = G["mapa"]["features"]

ABS_E = 100 * E["ab"] / E["ap"]
CIDADES = [("2408102", "Natal"), ("2408003", "Mossoró"), ("2403251", "Parnamirim"), ("2412005", "São Gonçalo do Amarante")]

sec = None
if BU.exists():
    bu = pd.read_excel(BU, dtype=str)
    for c in ["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES", "NR_ZONA", "NR_SECAO", "CD_MUNICIPIO"]:
        bu[c] = bu[c].astype(int)
    sec = bu.drop_duplicates(["NR_ZONA", "NR_SECAO"])[["CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO", "QT_APTOS",
                                                         "QT_COMPARECIMENTO", "QT_ABSTENCOES", "DS_SECOES_AGREGADAS"]].copy()
    sec["abp"] = 100 * sec.QT_ABSTENCOES / sec.QT_APTOS
    assert sec.QT_APTOS.sum() == E["ap"] and sec.QT_ABSTENCOES.sum() == E["ab"], "boletins e site divergem"

# ------------------------------------------------------------------ desenho de mapas
def polys(f):
    g = f["geometry"]
    return [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]


def desenhar(ax, feats, cores, lw=0.4, edge="white"):
    patches, fc = [], []
    for f, c in zip(feats, cores):
        for p in polys(f):
            patches.append(Polygon(p[0], closed=True)); fc.append(c)
    ax.add_collection(PatchCollection(patches, facecolor=fc, edgecolor=edge, linewidth=lw))
    ax.autoscale_view(); ax.set_aspect(1 / 0.994); ax.axis("off")


BOUNDS = [0, 15, 17, 19, 21, 23, 100]
CM = ListedColormap(SEQ[:6]); NORM = BoundaryNorm(BOUNDS, CM.N)
LABELS = ["até 15%", "15 a 17%", "17 a 19%", "19 a 21%", "21 a 23%", "23% ou mais"]


def legenda_seq(ax, loc="lower left", title="Abstenção (% do eleitorado apto)"):
    from matplotlib.patches import Patch
    h = [Patch(facecolor=CM(i), label=l) for i, l in enumerate(LABELS)]
    lg = ax.legend(handles=h, loc=loc, frameon=False, fontsize=7.5, title=title, title_fontsize=8)
    lg._legend_box.align = "left"


def cor_abs(x):
    return EMPTY if (x is None or np.isnan(x)) else CM(NORM(x))


def fig_mapa_municipios():
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.3))
    ax = axs[0]
    desenhar(ax, mfeat, [cor_abs(munis[f["properties"]["id"]]["ab"] / munis[f["properties"]["id"]]["ap"] * 100) for f in mfeat])
    legenda_seq(ax)
    ax.set_title("Taxa de abstenção por município", loc="left", fontweight="bold")
    ax = axs[1]
    desenhar(ax, mfeat, [EMPTY] * len(mfeat), edge="white")
    cen = []
    for f in mfeat:
        ring = max((p[0] for p in polys(f)), key=len)
        A = cx = cy = 0.0
        for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
            c = x0 * y1 - x1 * y0; A += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c
        cen.append((cx / (3 * A), cy / (3 * A)))
    ab = np.array([munis[f["properties"]["id"]]["ab"] for f in mfeat]); o = np.argsort(-ab)
    ax.scatter([cen[i][0] for i in o], [cen[i][1] for i in o], s=ab[o] / ab.max() * 900, color=SEQ[4], alpha=.7,
               edgecolor="white", linewidth=.6, zorder=3)
    for r in (1000, 10000, 100000):
        ax.scatter([], [], s=r / ab.max() * 900, color=SEQ[4], alpha=.7, edgecolor="white", label=f"{n(r)} eleitores")
    ax.legend(loc="lower left", frameon=False, fontsize=7.5, scatterpoints=1, labelspacing=1.4, borderpad=1,
              title="Abstenções (número de eleitores)", title_fontsize=8)
    ax.set_title("Quantidade de eleitores que não votaram", loc="left", fontweight="bold")
    fig.savefig(IMG / "mapa_municipios.png"); plt.close(fig)


def fig_porte_e_dispersao():
    bins = [0, 10000, 25000, 80000, 1e9]; labs = ["Até 10 mil", "10 a 25 mil", "25 a 80 mil", "Mais de 80 mil"]
    M["cl"] = pd.cut(M.ap, bins, labels=labs)
    g = M.groupby("cl", observed=True).agg(n=("id", "size"), ap=("ap", "sum"), ab=("ab", "sum"))
    g["abp"] = 100 * g.ab / g.ap
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axs[0]
    ax.barh(range(len(g)), g.abp, color=SEQ[4], height=.6)
    for i, (k, r) in enumerate(g.iterrows()):
        ax.text(r.abp + .2, i, f"{br(r.abp)}%", va="center", fontsize=8.5)
    ax.set_yticks(range(len(g)), [f"{k}\n{int(r.n)} municípios" for k, r in g.iterrows()], fontsize=8)
    ax.invert_yaxis(); ax.set_xlim(0, g.abp.max() * 1.25); ax.axvline(ABS_E, color=INK, ls=":", lw=1)
    ax.text(ABS_E, len(g) - 0.35, f" RN: {br(ABS_E)}%", fontsize=7.5, color=INK2, va="top")
    ax.set_xticks([]); [ax.spines[s].set_visible(False) for s in ("top", "right", "bottom")]
    ax.set_title("Abstenção por tamanho do eleitorado", loc="left", fontweight="bold")
    ax = axs[1]
    ax.scatter(M.ap, M.abp, s=np.clip(np.sqrt(M.ap) / 6, 6, 120), color=SEQ[4], alpha=.65, edgecolor="white", linewidth=.5)
    ax.set_xscale("log"); ax.axhline(ABS_E, color=INK, ls=":", lw=1)
    lab = pd.concat([M.nlargest(3, "abp"), M.nsmallest(2, "abp"), M.nlargest(3, "ap")]).drop_duplicates("id")
    for _, r in lab.iterrows():
        ax.annotate(r.n, (r.ap, r.abp), fontsize=6.5, color=INK2, xytext=(5, -3 if r.abp < 15 else 2), textcoords="offset points")
    ax.set_xlabel("eleitorado apto (escala logarítmica)"); ax.set_ylabel("abstenção (%)")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: n(x)))
    [ax.spines[s].set_visible(False) for s in ("top", "right")]
    ax.set_title("Cada município: tamanho e abstenção", loc="left", fontweight="bold")
    fig.savefig(IMG / "porte_dispersao.png"); plt.close(fig)
    return g


def fig_extremos():
    top = M.nlargest(15, "abp").iloc[::-1]; low = M.nsmallest(15, "abp").iloc[::-1]
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"wspace": 0.75})
    for ax, df, t in ((axs[0], top, "15 maiores taxas"), (axs[1], low, "15 menores taxas")):
        ax.hlines(range(len(df)), 0, df.abp, color=LINE, lw=1)
        ax.scatter(df.abp, range(len(df)), color=SEQ[5] if ax is axs[0] else SEQ[2], s=30, zorder=3)
        for i, (_, r) in enumerate(df.iterrows()):
            ax.text(r.abp + .25, i, f"{br(r.abp)}%", va="center", fontsize=7.5)
        ax.set_yticks(range(len(df)), [f"{r.n} ({n(r.ap)})" for _, r in df.iterrows()], fontsize=7.5)
        ax.set_xlim(0, 27); ax.axvline(ABS_E, color=INK, ls=":", lw=1)
        ax.set_xticks([]); [ax.spines[s].set_visible(False) for s in ("top", "right", "bottom")]
        ax.set_title(t, loc="left", fontweight="bold")
    fig.savefig(IMG / "extremos.png"); plt.close(fig)


def fig_bairros():
    fig, axs = plt.subplots(2, 2, figsize=(11, 10))
    for ax, (mid, nm) in zip(axs.flat, CIDADES):
        bs = B[B.m == mid]
        feats = [bfeat[i] for i in bs.id if i in bfeat]
        vals = [bs.set_index("id").abp.get(f["properties"]["id"]) for f in feats]
        desenhar(ax, feats, [cor_abs(v if (v == v and bs.set_index("id").ap[f["properties"]["id"]] > 0) else np.nan) for f, v in zip(feats, vals)], lw=.6)
        m = munis[mid]
        ax.set_title(f"{nm}: {br(100 * m['ab'] / m['ap'])}% de abstenção", loc="left", fontweight="bold")
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(facecolor=CM(i), label=l) for i, l in enumerate(LABELS)] + [Patch(facecolor=EMPTY, label="sem local de votação")],
               loc="lower center", ncol=7, frameon=False, fontsize=8, title="Abstenção (% do eleitorado apto)", title_fontsize=8.5)
    fig.suptitle("Abstenção por bairro (bairros do IBGE; em cinza, sem local de votação)", x=0.02, ha="left", fontsize=11, fontweight="bold")
    fig.savefig(IMG / "bairros.png"); plt.close(fig)


def fig_locais(mid, nm, arq):
    bs = B[B.m == mid]; feats = [bfeat[i] for i in bs.id if i in bfeat]
    ls = L[(L.m == mid) & (L.aprox == 0)].sort_values("ap", ascending=False)
    fig, ax = plt.subplots(figsize=(7.5, 8.2))
    desenhar(ax, feats, ["#f3f5f7"] * len(feats), lw=.7, edge="#b9c2ca")
    ax.scatter(ls.lon, ls.lat, s=ls.ap / ls.ap.max() * 260, c=[cor_abs(v) for v in ls.abp], edgecolor=INK, linewidth=.35, zorder=3)
    for _, b in bs[bs.ap > 0].iterrows():
        f = bfeat.get(b.id)
        if f is None: continue
        ring = max((p[0] for p in polys(f)), key=len); xs, ys = zip(*ring)
        ax.text(np.mean(xs), np.mean(ys), b.n, fontsize=4.6, color=MUTED, ha="center", va="center", zorder=2)
    xs = [x for f in feats for p in polys(f) for x, _ in p[0]]; ys = [y for f in feats for p in polys(f) for _, y in p[0]]
    dx, dy = (max(xs) - min(xs)) * .04, (max(ys) - min(ys)) * .04
    ax.set_xlim(min(xs) - dx, max(xs) + dx); ax.set_ylim(min(ys) - dy, max(ys) + dy)
    fora = ls[(ls.lon < min(xs)) | (ls.lon > max(xs)) | (ls.lat < min(ys)) | (ls.lat > max(ys))]
    if len(fora):
        ax.text(0.99, 0.01, f"{len(fora)} locais fora da área urbana não aparecem neste recorte", transform=ax.transAxes, ha="right", fontsize=6.5, color=MUTED)
    legenda_seq(ax, loc="lower left", title="Abstenção do local de votação")
    ax.set_title(f"{nm}: locais de votação (tamanho = eleitorado apto)", loc="left", fontweight="bold")
    fig.savefig(IMG / arq); plt.close(fig)


def fig_secoes():
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.4), gridspec_kw={"width_ratios": [1.3, 1]})
    ax = axs[0]
    ax.hist(sec.abp, bins=np.arange(0, 38, 1), color=SEQ[3], edgecolor="white")
    ax.axvline(ABS_E, color=INK, ls=":", lw=1); ax.text(ABS_E + .3, ax.get_ylim()[1] * .92, f"RN: {br(ABS_E)}%", fontsize=7.5)
    ax.set_xlabel("abstenção na seção (%)"); ax.set_ylabel("seções")
    [ax.spines[s].set_visible(False) for s in ("top", "right")]
    ax.set_title(f"Distribuição das {n(len(sec))} seções eleitorais", loc="left", fontweight="bold")
    ax = axs[1]
    ms = M.sort_values("ab", ascending=False); cum = 100 * ms.ab.cumsum() / ms.ab.sum()
    ax.plot(range(1, len(ms) + 1), cum, color=SEQ[5], lw=2)
    for k in (1, 4, 10, 30):
        ax.scatter(k, cum.iloc[k - 1], color=SEQ[5], s=14, zorder=3)
        ax.annotate(f"{k} {'município' if k == 1 else 'municípios'}: {br(cum.iloc[k - 1], 0)}%", (k, cum.iloc[k - 1]),
                    xytext=(8, -10), textcoords="offset points", fontsize=7.5)
    ax.set_xscale("log"); ax.set_ylim(0, 100); ax.set_xlabel("municípios, do maior para o menor número de abstenções")
    ax.set_ylabel("% das abstenções do estado")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: n(x)))
    [ax.spines[s].set_visible(False) for s in ("top", "right")]
    ax.set_title("Concentração das abstenções", loc="left", fontweight="bold")
    fig.savefig(IMG / "secoes_concentracao.png"); plt.close(fig)


def fig_voto():
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.4), sharey=True)
    for ax, col, c in ((axs[0], "cand0", C[0]), (axs[1], "cand1", C[1])):
        cor = LULA if c["partido"] == "PT" else FLAVIO
        ax.scatter(M[col], M.abp, s=np.clip(np.sqrt(M.ap) / 6, 6, 120), color=cor, alpha=.6, edgecolor="white", linewidth=.5)
        r = np.corrcoef(M[col], M.abp)[0, 1]
        ax.set_xlabel(f"% dos votos válidos de {c['nome']}"); ax.set_title(f"{c['nome']} (correlação: {br(r, 2)})", loc="left", fontweight="bold")
        [ax.spines[s].set_visible(False) for s in ("top", "right")]
    axs[0].set_ylabel("abstenção (%)")
    fig.savefig(IMG / "abstencao_voto.png"); plt.close(fig)


# ------------------------------------------------------------------ PDF
def build():
    IMG.mkdir(parents=True, exist_ok=True)
    fig_mapa_municipios(); g_porte = fig_porte_e_dispersao(); fig_extremos(); fig_bairros()
    fig_locais("2408102", "Natal", "locais_natal.png"); fig_locais("2408003", "Mossoró", "locais_mossoro.png")
    if sec is not None:
        fig_secoes()
    fig_voto()

    # --- números para o texto
    ms = M.sort_values("ab", ascending=False)
    cum = 100 * ms.ab.cumsum() / ms.ab.sum()
    natal = munis["2408102"]; moss = munis["2408003"]
    hi, lo = M.loc[M.abp.idxmax()], M.loc[M.abp.idxmin()]
    alien = E["ab"] + E["b"] + E["nu"]
    r0 = np.corrcoef(M.cand0, M.abp)[0, 1]; r1 = np.corrcoef(M.cand1, M.abp)[0, 1]
    acima = int((M.abp > ABS_E).sum())
    Lb = L[(L.ap >= 500)]
    bw = B[B.ap > 0]

    # --- estilos
    st = {
        "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=colors.HexColor(INK), spaceAfter=8, spaceBefore=4),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=colors.HexColor(INK), spaceBefore=12, spaceAfter=5),
        "p": ParagraphStyle("p", fontName="Helvetica", fontSize=9.6, leading=14, textColor=colors.HexColor(INK), spaceAfter=6),
        "small": ParagraphStyle("s", fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor(INK2), spaceAfter=4),
        "cap": ParagraphStyle("c", fontName="Helvetica-Oblique", fontSize=7.8, leading=10.5, textColor=colors.HexColor(MUTED), spaceAfter=8),
        "big": ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=26, leading=28, textColor=colors.HexColor(INK)),
        "lbl": ParagraphStyle("l", fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor(INK2)),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=7.6, leading=9.5, textColor=colors.HexColor(INK)),
    }
    W = A4[0] - 3.6 * cm

    def img(path, width=W):
        from PIL import Image as PI
        w, h = PI.open(path).size
        return Image(str(path), width=width, height=width * h / w)

    def tabela(head, rows, widths, align_right=()):
        data = [[Paragraph(f"<b>{h}</b>", st["cell"]) for h in head]] + [[Paragraph(str(c), st["cell"]) for c in r] for r in rows]
        t = Table(data, colWidths=widths, repeatRows=1)
        sty = [("LINEBELOW", (0, 0), (-1, 0), .8, colors.HexColor(INK)), ("LINEBELOW", (0, 1), (-1, -1), .25, colors.HexColor(LINE)),
               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]
        t.setStyle(TableStyle(sty))
        for i in align_right:
            for row in data:
                row[i].style = ParagraphStyle("r", parent=st["cell"], alignment=TA_RIGHT)
        return t

    P = lambda t: Paragraph(t, st["p"])
    story = []

    # ---- capa
    story += [Spacer(1, 3.2 * cm),
              Paragraph("Eleições 2026 · Rio Grande do Norte", st["lbl"]), Spacer(1, 6),
              Paragraph("Abstenção no 1º turno", ParagraphStyle("t", parent=st["h1"], fontSize=30, leading=34)),
              Paragraph("Quem deixou de votar em 4 de outubro de 2026: estado, municípios, bairros, locais de votação e seções eleitorais",
                        ParagraphStyle("sub", parent=st["p"], fontSize=12.5, leading=17, textColor=colors.HexColor(INK2))),
              Spacer(1, 1.2 * cm)]
    kp = [[Paragraph(f"{br(ABS_E)}%", st["big"]), Paragraph(n(E["ab"]), st["big"]), Paragraph(f"{br(100 * natal['ab'] / natal['ap'])}%", st["big"])],
          [Paragraph("do eleitorado apto não votou", st["lbl"]), Paragraph(f"eleitores ausentes, de {n(E['ap'])} aptos", st["lbl"]),
           Paragraph(f"de abstenção em Natal, que concentra {br(100 * natal['ab'] / E['ab'], 0)}% das ausências do estado", st["lbl"])]]
    t = Table(kp, colWidths=[W / 3] * 3); t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEABOVE", (0, 0), (-1, 0), 1.2, colors.HexColor(INK)), ("TOPPADDING", (0, 0), (-1, 0), 10)]))
    story += [t, Spacer(1, 1.6 * cm), img(IMG / "mapa_municipios.png"),
              Paragraph("Fonte: TSE, boletins de urna do 1º turno (eleição federal) por seção; malhas municipais e de bairros do IBGE. Elaboração própria a partir dos dados do projeto Elei-es-2026.", st["cap"]),
              PageBreak()]

    # ---- 1. resumo
    story += [Paragraph("Resumo", st["h1"]),
              P(f"No 1º turno de 2026, <b>{n(E['ab'])}</b> dos <b>{n(E['ap'])}</b> eleitores aptos do Rio Grande do Norte não compareceram às urnas, uma abstenção de <b>{br(ABS_E)}%</b>. "
                f"Compareceram {n(E['cp'])} eleitores ({br(100 * E['cp'] / E['ap'])}%). Somando ausentes, votos brancos ({n(E['b'])}) e nulos ({n(E['nu'])}) na eleição para presidente, "
                f"{n(alien)} eleitores ({br(100 * alien / E['ap'])}% do eleitorado) não escolheram nenhum candidato."),
              P(f"A abstenção variou de <b>{br(lo.abp)}%</b> em {lo.n} a <b>{br(hi.abp)}%</b> em {hi.n}. Em {acima} dos 167 municípios ela ficou acima da média estadual. "
                f"Natal teve {br(100 * natal['ab'] / natal['ap'])}%, acima do estado, e sozinha responde por {br(100 * natal['ab'] / E['ab'])}% de todas as ausências; "
                f"os quatro municípios com mais ausências (Natal, Mossoró, Parnamirim e São Gonçalo do Amarante) somam {br(cum.iloc[3], 0)}%. Mossoró, a segunda maior cidade, ficou abaixo da média, com {br(100 * moss['ab'] / moss['ap'])}%."),
              P(f"Dentro das cidades, a abstenção também varia bastante. Em Natal, vai de {br(bw[bw.m == '2408102'].abp.min())}% a {br(bw[bw.m == '2408102'].abp.max())}% entre bairros; "
                f"entre os {n(len(L))} locais de votação do estado, de {br(L.abp.min())}% a {br(L.abp.max())}%."
                + (f" Entre as {n(len(sec))} seções eleitorais, metade teve abstenção entre {br(sec.abp.quantile(.25))}% e {br(sec.abp.quantile(.75))}%." if sec is not None else "")),
              P(f"A taxa de abstenção quase não se relaciona com o desempenho dos candidatos: a correlação entre abstenção e o percentual de {C[0]['nome']} nos municípios é de {br(r0, 2)}, "
                f"e com o de {C[1]['nome']}, de {br(r1, 2)}. Ou seja, municípios com mais ausências não pendem para nenhum lado."),
              Paragraph("Como ler este relatório", st["h2"]),
              P("A abstenção é a parcela do eleitorado apto que não compareceu para votar. Os números vêm dos boletins de urna de cada seção, que registram o eleitorado apto e o comparecimento. "
                "O eleitor é contado no local onde está inscrito para votar, e não onde mora. O eleitorado apto inclui pessoas que mudaram de cidade sem transferir o título e registros ainda não "
                "cancelados, o que tende a elevar a abstenção medida, sobretudo em municípios com muita migração."),
              PageBreak()]

    # ---- 2. municípios
    story += [Paragraph("1. Municípios", st["h1"]),
              P(f"O mapa da capa mostra a taxa de abstenção (à esquerda) e a quantidade de ausentes (à direita). As taxas mais altas aparecem espalhadas pelo estado, "
                f"enquanto as quantidades se concentram nas cidades grandes. A taxa média entre os municípios, sem ponderar pelo tamanho, é de {br(M.abp.mean())}%; "
                f"metade deles ficou entre {br(M.abp.quantile(.25))}% e {br(M.abp.quantile(.75))}%."),
              img(IMG / "extremos.png"),
              Paragraph("Linha pontilhada: abstenção no estado.", st["cap"]),
              P("O tamanho do município pesa pouco. A abstenção nos municípios com mais de 80 mil eleitores é puxada para cima por Natal; nas faixas intermediárias, fica perto da média estadual."),
              img(IMG / "porte_dispersao.png")]
    rows = [[k, int(r.n), n(r.ap), n(r.ab), f"{br(r.abp)}%"] for k, r in g_porte.iterrows()]
    story += [Spacer(1, 4), tabela(["Faixa de eleitorado", "Municípios", "Aptos", "Abstenções", "Abstenção"], rows, [5.2 * cm, 2.6 * cm, 3.2 * cm, 3.2 * cm, 2.6 * cm], (1, 2, 3, 4))]
    rows = [[r.n, n(r.ap), n(r.cp), n(r.ab), f"{br(r.abp)}%", f"{br(100 * r.ab / E['ab'])}%"] for _, r in M.nlargest(15, "ap").iterrows()]
    story += [Paragraph("As 15 maiores cidades", st["h2"]),
              tabela(["Município", "Aptos", "Comparecimento", "Abstenções", "Abstenção", "% das ausências do RN"], rows,
                     [4.6 * cm, 2.4 * cm, 2.8 * cm, 2.4 * cm, 2.1 * cm, 3.1 * cm], (1, 2, 3, 4, 5)),
              PageBreak()]

    # ---- 3. bairros
    story += [Paragraph("2. Bairros das maiores cidades", st["h1"]),
              P("Para Natal, Mossoró, Parnamirim e São Gonçalo do Amarante, que têm bairros delimitados pelo IBGE, cada local de votação foi associado ao bairro onde fica. "
                "A abstenção do bairro soma o eleitorado e as ausências desses locais. Como o eleitor vota perto de onde se inscreveu, que nem sempre é onde mora hoje, "
                "bairros com muita mudança de moradores tendem a mostrar abstenção maior."),
              img(IMG / "bairros.png")]
    for mid, nm in CIDADES:
        x = bw[bw.m == mid].sort_values("abp", ascending=False)
        rows = [[r.n, int(r.nloc), n(r.ap), n(r.ab), f"{br(r.abp)}%"] for _, r in x.iterrows()]
        story += [KeepTogether([Paragraph(f"{nm}: abstenção por bairro", st["h2"]),
                                Paragraph(f"{len(x)} bairros com local de votação, do maior para o menor percentual. Abstenção no município: {br(100 * munis[mid]['ab'] / munis[mid]['ap'])}%.", st["small"]),
                                tabela(["Bairro", "Locais", "Aptos", "Abstenções", "Abstenção"], rows, [6.4 * cm, 2 * cm, 3 * cm, 3 * cm, 2.6 * cm], (1, 2, 3, 4))])]
    fora = L[(L.m.isin([c[0] for c in CIDADES])) & (L.bi.isna())]
    story += [Paragraph(f"Locais sem bairro atribuído (coordenada ausente ou fora dos limites dos bairros, inclusive zona rural): {len(fora)}, com {n(fora.ap.sum())} eleitores e abstenção de {br(100 * fora.ab.sum() / fora.ap.sum())}%.", st["small"]),
              PageBreak()]

    # ---- 4. locais
    story += [Paragraph("3. Locais de votação", st["h1"]),
              P(f"Os {n(len(L))} locais de votação do estado mostram mais variação do que os municípios: metade teve abstenção entre {br(L.abp.quantile(.25))}% e {br(L.abp.quantile(.75))}%. "
                "Nos mapas abaixo, cada círculo é um local, com tamanho proporcional ao eleitorado e cor pela abstenção."),
              img(IMG / "locais_natal.png", W * .86), PageBreak(),
              img(IMG / "locais_mossoro.png", W * .78)]
    cols = ["Local de votação", "Município", "Bairro (TSE)", "Aptos", "Abstenção"]
    wd = [6.6 * cm, 3.2 * cm, 3.4 * cm, 1.9 * cm, 1.9 * cm]
    t_hi = [[r.n.title()[:60], r.muni, (r.bt or "").title()[:28], n(r.ap), f"{br(r.abp)}%"] for _, r in Lb.nlargest(18, "abp").iterrows()]
    t_lo = [[r.n.title()[:60], r.muni, (r.bt or "").title()[:28], n(r.ap), f"{br(r.abp)}%"] for _, r in Lb.nsmallest(18, "abp").iterrows()]
    story += [PageBreak(), Paragraph("Locais com maior e menor abstenção", st["h2"]),
              Paragraph(f"Considerando os {n(len(Lb))} locais com pelo menos 500 eleitores aptos, para evitar percentuais instáveis de locais muito pequenos.", st["small"]),
              Paragraph("<b>18 maiores taxas</b>", st["p"]), tabela(cols, t_hi, wd, (3, 4)), Spacer(1, 8),
              Paragraph("<b>18 menores taxas</b>", st["p"]), tabela(cols, t_lo, wd, (3, 4)), PageBreak()]

    # ---- 5. seções
    if sec is not None:
        ag = sec[sec.DS_SECOES_AGREGADAS != "#NULO#"]
        story += [Paragraph("4. Seções eleitorais", st["h1"]),
                  P(f"O boletim de cada uma das {n(len(sec))} seções traz o eleitorado apto e o comparecimento. A abstenção típica de uma seção ficou em torno de {br(sec.abp.median())}% (mediana); "
                    f"{n((sec.abp >= 25).sum())} seções ({br(100 * (sec.abp >= 25).mean())}%) tiveram 25% ou mais de ausências, e {n((sec.abp < 12).sum())} ficaram abaixo de 12%. "
                    f"{n(len(ag))} seções foram agregadas a outras na mesma urna; nelas, o boletim reúne os eleitores das seções agregadas."),
                  P(f"As ausências estão muito concentradas: um único município, Natal, responde por {br(cum.iloc[0], 0)}% delas; os dez municípios com mais ausentes, por {br(cum.iloc[9], 0)}%; "
                    f"e 30 municípios, por {br(cum.iloc[29], 0)}%."),
                  img(IMG / "secoes_concentracao.png")]
    # ---- 6. abstenção e voto
    story += [Paragraph("5. Abstenção e voto", st["h1"]) if sec is None else Paragraph("5. Abstenção e voto", st["h2"]),
              P(f"Cada ponto é um município. Não há relação visível entre a taxa de abstenção e o percentual de votos dos dois candidatos mais votados para presidente "
                f"(correlações de {br(r0, 2)} e {br(r1, 2)}, valores muito próximos de zero). A abstenção, portanto, não favoreceu nenhum dos lados de forma sistemática no conjunto dos municípios."),
              img(IMG / "abstencao_voto.png"), PageBreak()]

    # ---- 7. metodologia
    story += [Paragraph("Metodologia e fontes", st["h1"]),
              P("<b>Eleitorado apto, comparecimento e abstenção</b>: boletins de urna do 1º turno de 2026 para Presidente no RN (TSE, Portal de Dados Abertos), uma linha por seção. "
                "A abstenção é o eleitorado apto menos o comparecimento. Os totais conferem com os do site: "
                f"{n(E['ap'])} aptos, {n(E['cp'])} comparecimentos e {n(E['ab'])} abstenções."),
              P("<b>Voto em trânsito</b>: eleitores que votaram fora do domicílio eleitoral aparecem nas seções onde votaram; por isso o comparecimento para Presidente é um pouco maior "
                "que o para Governador (eleitores em trânsito em outro estado votam só para Presidente)."),
              P("<b>Locais e bairros</b>: cada local de votação é posicionado pela coordenada do cadastro do TSE e atribuído ao bairro do IBGE (Censo 2022) que o contém. "
                "Locais sem coordenada válida ou fora dos bairros mapeados entram nos totais do município, mas não nos dos bairros."),
              P("<b>Limitações</b>: o eleitorado apto inclui pessoas que se mudaram sem transferir o título e registros ainda não cancelados, o que eleva a abstenção medida. "
                "A abstenção é atribuída ao local de inscrição do eleitor, e não ao lugar onde mora. Este relatório é descritivo: não identifica as causas da abstenção."),
              P("<b>Reprodução</b>: script scripts/gerar_pdf_abstencao.py do repositório github.com/felipemechatronics/Elei-es-2026. "
                "Base geográfica organizada a partir do projeto Como o RN votou para governador, de Peterson Sousa."),
              PageBreak()]

    # ---- anexo: todos os municípios
    rows = [[r.n, n(r.ap), n(r.cp), n(r.ab), f"{br(r.abp)}%"] for _, r in M.sort_values("n").iterrows()]
    story += [Paragraph("Anexo: abstenção em todos os municípios", st["h1"]),
              tabela(["Município", "Aptos", "Comparecimento", "Abstenções", "Abstenção"], rows, [6.4 * cm, 2.8 * cm, 3 * cm, 2.8 * cm, 2.4 * cm], (1, 2, 3, 4))]

    # ---- documento
    def deco(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5); canvas.setFillColor(colors.HexColor(MUTED))
        if doc.page > 1:
            canvas.drawString(1.8 * cm, 1.1 * cm, "Abstenção no 1º turno de 2026 · Rio Grande do Norte")
            canvas.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm, f"{doc.page}")
            canvas.setStrokeColor(colors.HexColor(LINE)); canvas.line(1.8 * cm, 1.45 * cm, A4[0] - 1.8 * cm, 1.45 * cm)
        canvas.restoreState()

    pdf = OUT / "abstencao_RN_2026.pdf"
    doc = BaseDocTemplate(str(pdf), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.9 * cm,
                          title="Abstenção no 1º turno de 2026 no Rio Grande do Norte", author="Elei-es-2026",
                          subject="Abstenção por município, bairro, local de votação e seção")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=deco)])
    doc.build(story)
    print(pdf)


if __name__ == "__main__":
    build()
