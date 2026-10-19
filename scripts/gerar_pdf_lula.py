"""Relatório em PDF: os votos de Lula por candidato a governador nos bairros de Natal e Mossoró (1º turno de 2026).

Usa as estimativas de scripts/gerar_lula.py (relatorio/lula/bairros.json) e a malha de bairros de docs/geo.js.

  python scripts/gerar_pdf_lula.py
Saída: relatorio/lula/lula_bairros_RN_2026.pdf (+ figuras em relatorio/lula/img), copiado para docs/relatorio/.
"""
import json, shutil
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon, Patch
from matplotlib.colors import to_rgb

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Image, Table,
                                TableStyle, PageBreak, KeepTogether, CondPageBreak)

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "relatorio" / "lula"
IMG = OUT / "img"
FONTES = Path("/usr/share/fonts/truetype/dejavu")
pdfmetrics.registerFont(TTFont("DV", str(FONTES / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", str(FONTES / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DVI", str(FONTES / "DejaVuSans-Oblique.ttf")))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVB")

INK, INK2, MUTED, LINE, EMPTY = "#15212c", "#4a5966", "#7a8792", "#dce2e6", "#eceff1"
CORG = ["#2a78d6", "#eb6834", "#1baf7a", "#c3c9ce", "#9aa5ae"]  # Allyson, Cadu, Álvaro, outros, branco/nulo
NOMEG = ["Allyson Bezerra", "Cadu de Lula", "Álvaro Dias", "Outros", "Branco ou nulo"]
CURTO = ["Allyson", "Cadu", "Álvaro", "Outros", "Branco/nulo"]
NOMEP = ["Lula", "Flávio Bolsonaro", "Outros candidatos", "Branco ou nulo"]
LU, AL, CA, AV, GO, GB = 0, 0, 1, 2, 3, 4

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "text.color": INK,
                     "axes.edgecolor": LINE, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "figure.dpi": 200, "savefig.bbox": "tight", "savefig.facecolor": "white", "axes.titlesize": 9.5})


def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def n(x):
    return f"{int(round(x)):,}".replace(",", ".")


def sgn(x):
    return ("+" if x > 0 else "−" if x < 0 else "") + n(abs(x))


def ler_js(nome):
    s = (RAIZ / "docs" / nome).read_text(encoding="utf-8")
    return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))


# ------------------------------------------------------------------ dados
D = json.loads((OUT / "bairros.json").read_text(encoding="utf-8"))
G = ler_js("geo.js")
bfeat = {f["properties"]["id"]: f for f in G["bmapa"]["features"]}
MUN = {m["id"]: m for m in D["munis"]}


def prep(x):
    vp = x["p"][0] + x["p"][1] + x["p"][2]
    vg = x["g"][0] + x["g"][1] + x["g"][2] + x["g"][3]
    t = sum(x["N"][0]) or 1
    sh = [v / t for v in x["N"][0]]                      # parcela dos eleitores de Lula em cada opção
    x.update(vp=vp, vg=vg, pL=100 * x["p"][0] / vp, pC=100 * x["g"][1] / vg, gapV=x["p"][0] - x["g"][1],
             gapP=100 * x["p"][0] / vp - 100 * x["g"][1] / vg, sh=sh, lv=[s * x["p"][0] for s in sh])
    return x


B = [prep(b) for b in D["bairros"]]
for m in D["munis"]:
    prep(m)
for b in B:
    b["mn"] = MUN[b["m"]]["n"]
CID = sorted({b["m"] for b in B}, key=lambda m: -MUN[m]["p"][0])
GRANDES = [m for m in CID if sum(1 for b in B if b["m"] == m) >= 5]
PEQ = [m for m in CID if m not in GRANDES]
Nst = np.array(D["N"], float)
EST_P = [sum(m["p"][i] for m in D["munis"]) for i in range(4)]
EST_G = [sum(m["g"][j] for m in D["munis"]) for j in range(5)]
sh_est = Nst[0] / Nst[0].sum()
# conjunto dos bairros
LB = sum(b["p"][0] for b in B)
LVB = np.sum([b["lv"] for b in B], axis=0)
SECB = sum(b["s"] for b in B)


# ------------------------------------------------------------------ figuras
def polys(f):
    g = f["geometry"]
    return [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]


def desenhar(ax, feats, cores, lw=0.5, edge="white"):
    patches, fc = [], []
    for f, c in zip(feats, cores):
        for p in polys(f):
            patches.append(Polygon(p[0], closed=True)); fc.append(c)
    ax.add_collection(PatchCollection(patches, facecolor=fc, edgecolor=edge, linewidth=lw))
    ax.autoscale_view(); ax.set_aspect(1 / 0.994); ax.axis("off")


def ramp(base, k):
    a, b = np.array(to_rgb("#ffffff")), np.array(to_rgb(base))
    return [tuple(a + (b - a) * t) for t in np.linspace(0.15, 0.95, k)]


def classes(vals, edges, cores):
    return [EMPTY if v is None else cores[int(np.searchsorted(edges, v, side="right"))] for v in vals]


# limites fixos para que os mapas de cidades diferentes sejam comparáveis
E_GAP = [5, 10, 15, 20]           # Lula − Cadu, p.p. dos válidos
E_SH = [30, 40, 50, 60]           # % dos eleitores de Lula
LBL = lambda e, u: [f"até {e[0]}{u}"] + [f"{e[i]} a {e[i + 1]}{u}" for i in range(len(e) - 1)] + [f"{e[-1]}{u} ou mais"]


def fig_cidade(mid, arq):
    bb = {b["id"]: b for b in B if b["m"] == mid}
    feats = [f for k, f in bfeat.items() if k[:7] == mid]
    fig, axs = plt.subplots(1, 3, figsize=(11, 4.6))
    spec = [("Lula − Cadu (p.p. dos válidos)", lambda b: b["gapP"], E_GAP, ramp("#3a4652", 5), " p.p."),
            ("Eleitores de Lula que votaram\nem Allyson (estimado)", lambda b: 100 * b["sh"][AL], E_SH, ramp(CORG[AL], 5), "%"),
            ("Eleitores de Lula que votaram\nem Cadu (estimado)", lambda b: 100 * b["sh"][CA], E_SH, ramp(CORG[CA], 5), "%")]
    for ax, (tit, fn, ed, cores, u) in zip(axs, spec):
        vals = [fn(bb[f["properties"]["id"]]) if f["properties"]["id"] in bb else None for f in feats]
        desenhar(ax, feats, classes(vals, ed, cores))
        ax.set_title(tit, loc="left", fontweight="bold")
        h = [Patch(facecolor=c, label=l) for c, l in zip(cores, LBL(ed, u))] + [Patch(facecolor=EMPTY, label="sem local de votação")]
        ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2, frameon=False, fontsize=6.8, handlelength=1.2, columnspacing=0.8)
    fig.savefig(arq); plt.close(fig)


def fig_barras_cidade(mid, arq):
    bs = sorted([b for b in B if b["m"] == mid], key=lambda b: b["p"][0])
    h = max(2.2, 0.24 * len(bs) + 0.8)
    fig, ax = plt.subplots(figsize=(10, h))
    y = np.arange(len(bs)); left = np.zeros(len(bs))
    for j in (CA, AL, AV, GO, GB):
        v = np.array([b["lv"][j] for b in bs])
        ax.barh(y, v, left=left, color=CORG[j], height=0.72, label=NOMEG[j] if j != GO else None, edgecolor="white", linewidth=0.4)
        for k in range(len(bs)):
            if j in (CA, AL) and v[k] >= 0.09 * max(b["p"][0] for b in bs) and v[k] / bs[k]["p"][0] > 0.12:
                ax.text(left[k] + v[k] / 2, y[k], f"{br(100 * bs[k]['sh'][j], 0)}%", ha="center", va="center", fontsize=6.6, color="white", fontweight="bold")
        left += v
    ax.set_yticks(y, [b["n"] + (" *" if b["s"] < 10 else "") for b in bs], fontsize=7.2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: n(x)))
    ax.spines[["top", "right", "left"]].set_visible(False); ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=LINE, linewidth=0.6); ax.set_axisbelow(True)
    ax.set_xlabel("Eleitores de Lula no bairro (estimativa de como votaram para governador)")
    hs = [Patch(facecolor=CORG[j], label=NOMEG[j]) for j in (CA, AL, AV, GB)]
    ax.legend(handles=hs, loc="lower right", frameon=False, fontsize=7, ncol=2)
    fig.savefig(arq); plt.close(fig)


def fig_estado(arq):
    fig, ax = plt.subplots(figsize=(10, 2.5))
    for i in range(4):
        t = Nst[i].sum(); left = 0
        for j in (CA, AL, AV, GO, GB):
            w = Nst[i, j] / t
            ax.barh(3 - i, w, left=left, color=CORG[j], height=0.68, edgecolor="white", linewidth=0.6)
            if w > 0.06:
                ax.text(left + w / 2, 3 - i, f"{br(100 * w, 0)}%", ha="center", va="center", fontsize=7.5,
                        color="white" if j < 3 else INK, fontweight="bold")
            left += w
    ax.set_yticks(range(4), [f"{NOMEP[3 - k]}  ({n(EST_P[3 - k])})" for k in range(4)], fontsize=8)
    ax.set_xlim(0, 1); ax.set_xticks([]); ax.spines[:].set_visible(False); ax.tick_params(length=0)
    ax.legend(handles=[Patch(facecolor=CORG[j], label=NOMEG[j]) for j in (CA, AL, AV, GO, GB)], loc="upper center",
              bbox_to_anchor=(0.5, -0.04), ncol=5, frameon=False, fontsize=7.5)
    fig.savefig(arq); plt.close(fig)


def fig_dispersao(arq):
    fig, axs = plt.subplots(1, 2, figsize=(10.5, 3.9))
    cores_c = {m: c for m, c in zip(GRANDES, ["#15212c", "#7a5af5", "#c2410c", "#0e7490", "#a16207"])}
    for ax, j, tit in ((axs[0], CA, "Eleitores de Lula que votaram em Cadu"), (axs[1], AL, "Eleitores de Lula que votaram em Allyson")):
        for b in B:
            c = cores_c.get(b["m"], "#9aa5ae")
            ax.scatter(b["pL"], 100 * b["sh"][j], s=8 + b["p"][0] / 120, color=c, alpha=0.65, edgecolor="white", linewidth=0.5)
        ax.set_xlabel("Lula, % dos votos válidos no bairro"); ax.set_ylabel("% dos eleitores de Lula (estimado)")
        ax.set_title(tit, loc="left", fontweight="bold")
        ax.spines[["top", "right"]].set_visible(False); ax.grid(color=LINE, linewidth=0.5); ax.set_axisbelow(True)
    hs = [plt.Line2D([], [], marker="o", ls="", color=c, label=MUN[m]["n"]) for m, c in cores_c.items()] + \
         [plt.Line2D([], [], marker="o", ls="", color="#9aa5ae", label="demais municípios")]
    fig.legend(handles=hs, frameon=False, fontsize=7.2, loc="lower center", bbox_to_anchor=(0.5, -0.07), ncol=len(hs))
    fig.text(0.01, -0.12, "Cada círculo é um bairro; a área é proporcional aos votos de Lula.", fontsize=7, color=MUTED)
    fig.savefig(arq); plt.close(fig)



CIDADES = [("2408102", "Natal"), ("2408003", "Mossoró")]


def frac(x):
    """parcelas dos eleitores de Lula: Cadu, Allyson, Álvaro, branco/nulo/outro"""
    sh = x["sh"]
    return [sh[CA], sh[AL], sh[AV], sh[GB] + sh[GO]]


COR4 = [CORG[CA], CORG[AL], CORG[AV], CORG[GB]]
NOM4 = ["Cadu de Lula", "Allyson Bezerra", "Álvaro Dias", "Branco, nulo ou outro"]


def fig_quadrados(arq):
    """Três grades de 100 quadrados: como 100 eleitores de Lula votaram para governador."""
    est = {"sh": list(Nst[0] / Nst[0].sum())}
    grupos = [("Rio Grande do Norte", est), ("Natal", MUN["2408102"]), ("Mossoró", MUN["2408003"])]
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.9))
    for ax, (nome, x) in zip(axs, grupos):
        f = frac(x); q = [int(round(100 * v)) for v in f]
        q[0] += 100 - sum(q)                                  # arredondamento fecha 100
        cores = sum(([COR4[i]] * q[i] for i in range(4)), [])
        for k, c in enumerate(cores):
            r, col = divmod(k, 10)
            ax.add_patch(matplotlib.patches.FancyBboxPatch((col + 0.08, 9 - r + 0.08), 0.84, 0.84, boxstyle="round,pad=0,rounding_size=0.12",
                                                           facecolor=c, edgecolor="none"))
        ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.set_aspect(1); ax.axis("off")
        ax.set_title(nome, loc="left", fontweight="bold", fontsize=10.5)
        ax.text(0, -0.55, "  ".join(f"{NOM4[i].split()[0] if i < 3 else 'Br./nulo/outro'}: {q[i]}" for i in range(4) if q[i] > 0),
                fontsize=7.4, color=INK2, va="top")
    fig.legend(handles=[Patch(facecolor=COR4[i], label=NOM4[i]) for i in range(4)], loc="lower center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, -0.1), fontsize=8.2)
    fig.savefig(arq); plt.close(fig)


def fig_escada(arq):
    """Do total de Lula ao total de Cadu, em degraus (RN, Natal, Mossoró)."""
    est = {"p": EST_P, "g": EST_G, "lv": list(Nst[0] / Nst[0].sum() * EST_P[0])}
    grupos = [("Rio Grande do Norte", est), ("Natal", MUN["2408102"]), ("Mossoró", MUN["2408003"])]
    fig, axs = plt.subplots(3, 1, figsize=(10, 6.6))
    for ax, (nome, x) in zip(axs, grupos):
        lula, cadu, lv = x["p"][0], x["g"][CA], x["lv"]
        outros_c = cadu - lv[CA]
        passos = [("Votos de Lula", 0, lula, "#3a4652", n(lula)),
                  ("foram para Allyson", lula - lv[AL], lv[AL], CORG[AL], "−" + n(lv[AL])),
                  ("foram para Álvaro", lula - lv[AL] - lv[AV], lv[AV], CORG[AV], "−" + n(lv[AV])),
                  ("branco, nulo ou outro", lv[CA], lv[GB] + lv[GO], CORG[GB], "−" + n(lv[GB] + lv[GO])),
                  ("eleitores de Lula com Cadu", 0, lv[CA], CORG[CA], n(lv[CA])),
                  ("+ eleitores de outros com Cadu", lv[CA], outros_c, "#f2a57f", "+" + n(outros_c)),
                  ("Votos de Cadu", 0, cadu, CORG[CA], n(cadu))]
        y = np.arange(len(passos))[::-1]
        for yy, (lab, l0, w, c, t) in zip(y, passos):
            ax.barh(yy, w, left=l0, color=c, height=0.66)
            ax.text(l0 + w + lula * 0.01, yy, t if round(w) else "0", va="center", fontsize=8, color=INK)
        ax.set_yticks(y, [p[0] for p in passos], fontsize=8.2)
        ax.set_xlim(0, lula * 1.16); ax.set_xticks([])
        ax.spines[:].set_visible(False); ax.tick_params(length=0)
        ax.set_title(f"{nome}: Lula {n(lula)} × Cadu {n(cadu)} (diferença de {n(lula - cadu)})", loc="left", fontweight="bold", fontsize=9.5)
    fig.tight_layout(h_pad=1.6)
    fig.savefig(arq); plt.close(fig)


def fig_mapas2(mid, arq):
    bb = {b["id"]: b for b in B if b["m"] == mid}
    feats = [f for k, f in bfeat.items() if k[:7] == mid]
    fig, axs = plt.subplots(1, 2, figsize=(10, 5.4))
    spec = [("Quantos eleitores de Lula votaram em CADU", lambda b: 100 * b["sh"][CA], ramp(CORG[CA], 5)),
            ("Quantos eleitores de Lula votaram em ALLYSON", lambda b: 100 * b["sh"][AL], ramp(CORG[AL], 5))]
    ed = [30, 40, 50, 60]
    lbl = ["menos de 3 em 10", "3 a 4 em 10", "4 a 5 em 10", "5 a 6 em 10", "6 ou mais em 10"]
    for ax, (tit, fn, cores) in zip(axs, spec):
        vals = [fn(bb[f["properties"]["id"]]) if f["properties"]["id"] in bb else None for f in feats]
        desenhar(ax, feats, classes(vals, ed, cores), lw=0.7)
        ax.set_title(tit, loc="left", fontweight="bold", fontsize=9.5)
        h = [Patch(facecolor=c, label=l) for c, l in zip(cores, lbl)] + [Patch(facecolor=EMPTY, label="sem local de votação")]
        ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, frameon=False, fontsize=7.2, handlelength=1.2)
    fig.savefig(arq); plt.close(fig)


def fig_barras(mid, arq):
    bs = sorted([b for b in B if b["m"] == mid], key=lambda b: b["p"][0])
    fig, ax = plt.subplots(figsize=(10, max(2.4, 0.25 * len(bs) + 1.0)))
    y = np.arange(len(bs)); left = np.zeros(len(bs)); mxv = max(b["p"][0] for b in bs)
    for i in range(4):
        v = np.array([frac(b)[i] * b["p"][0] for b in bs])
        ax.barh(y, v, left=left, color=COR4[i], height=0.72, edgecolor="white", linewidth=0.4)
        for k in range(len(bs)):
            if i < 2 and v[k] >= 0.08 * mxv:
                ax.text(left[k] + v[k] / 2, y[k], f"{br(100 * frac(bs[k])[i], 0)}%", ha="center", va="center", fontsize=6.6, color="white", fontweight="bold")
        left += v
    ax.set_yticks(y, [b["n"] for b in bs], fontsize=7.4)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: n(x)))
    ax.spines[["top", "right", "left"]].set_visible(False); ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=LINE, linewidth=0.6); ax.set_axisbelow(True)
    ax.set_xlabel("Número de eleitores de Lula no bairro")
    ax.legend(handles=[Patch(facecolor=COR4[i], label=NOM4[i]) for i in range(4)], loc="lower center", bbox_to_anchor=(0.45, 1.0),
              ncol=4, frameon=False, fontsize=7.6)
    fig.savefig(arq); plt.close(fig)


def confianca(b):
    w = 100 * max(b["hi"][CA] - b["lo"][CA], b["hi"][AL] - b["lo"][AL])
    if b["s"] >= 30 and w <= 4:
        return "alta"
    if b["s"] >= 10:
        return "média"
    return "baixa"


# ------------------------------------------------------------------ documento
def build():
    IMG.mkdir(parents=True, exist_ok=True)
    for f in IMG.glob("*.png"):
        f.unlink()
    fig_quadrados(IMG / "quadrados.png"); fig_escada(IMG / "escada.png")
    for mid, _ in CIDADES:
        fig_mapas2(mid, IMG / f"mapas_{mid}.png"); fig_barras(mid, IMG / f"barras_{mid}.png")

    st = {
        "h1": ParagraphStyle("h1", fontName="DVB", fontSize=17, leading=21, textColor=colors.HexColor(INK), spaceAfter=8, spaceBefore=2),
        "h2": ParagraphStyle("h2", fontName="DVB", fontSize=12, leading=15.5, textColor=colors.HexColor(INK), spaceBefore=10, spaceAfter=5),
        "p": ParagraphStyle("p", fontName="DV", fontSize=9.6, leading=14.4, textColor=colors.HexColor(INK), spaceAfter=7),
        "li": ParagraphStyle("li", fontName="DV", fontSize=9.6, leading=14.4, textColor=colors.HexColor(INK), leftIndent=12, bulletIndent=0, spaceAfter=4),
        "small": ParagraphStyle("s", fontName="DV", fontSize=8, leading=11, textColor=colors.HexColor(INK2), spaceAfter=4),
        "cap": ParagraphStyle("c", fontName="DVI", fontSize=7.6, leading=10.4, textColor=colors.HexColor(MUTED), spaceAfter=8),
        "big": ParagraphStyle("b", fontName="DVB", fontSize=20, leading=23, textColor=colors.HexColor(INK)),
        "lbl": ParagraphStyle("l", fontName="DV", fontSize=8.4, leading=11.2, textColor=colors.HexColor(INK2)),
        "kick": ParagraphStyle("k", fontName="DV", fontSize=8, leading=10, textColor=colors.HexColor(MUTED), spaceAfter=2),
        "cell": ParagraphStyle("cell", fontName="DV", fontSize=7.4, leading=9.2, textColor=colors.HexColor(INK)),
        "box": ParagraphStyle("box", fontName="DV", fontSize=9.2, leading=13.6, textColor=colors.HexColor(INK)),
    }
    W = A4[0] - 3.6 * cm
    P = lambda t: Paragraph(t, st["p"])
    LI = lambda t: Paragraph(t, st["li"], bulletText="•")

    def img(path, width=W, maxh=None):
        from PIL import Image as PI
        w, h = PI.open(path).size
        hh = width * h / w
        if maxh and hh > maxh:
            width, hh = width * maxh / hh, maxh
        return Image(str(path), width=width, height=hh)

    def caixa(conteudo, fundo="#f1f4f6", borda=None):
        t = Table([[conteudo]], colWidths=[W])
        sty = [("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fundo)), ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
               ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]
        if borda:
            sty.append(("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(borda)))
        t.setStyle(TableStyle(sty))
        return t

    def tabela(head, rows, widths, right=(), bold_last=False):
        data = [[Paragraph(f"<b>{h}</b>", st["cell"]) for h in head]] + [[Paragraph(str(c), st["cell"]) for c in r] for r in rows]
        t = Table(data, colWidths=widths, repeatRows=1)
        sty = [("LINEBELOW", (0, 0), (-1, 0), .8, colors.HexColor(INK)), ("LINEBELOW", (0, 1), (-1, -1), .25, colors.HexColor(LINE)),
               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
               ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
        if bold_last:
            sty.append(("LINEABOVE", (0, -1), (-1, -1), .8, colors.HexColor(INK)))
        t.setStyle(TableStyle(sty))
        for i in right:
            for row in data:
                row[i].style = ParagraphStyle("r", parent=st["cell"], alignment=TA_RIGHT)
        return t

    def dez(v):
        """'5 em cada 10' com arredondamento de meio ponto"""
        x = round(10 * v * 2) / 2
        return (br(x, 1) if x % 1 else str(int(x))).replace(",5", " e meio")

    def dz(v):
        """versão curta para tabelas: 3,5"""
        return br(round(10 * v * 2) / 2, 1).replace(",0", "")

    def kpis(itens):
        cel = [[Paragraph(v, st["big"]) for v, _ in itens], [Paragraph(t, st["lbl"]) for _, t in itens]]
        t = Table(cel, colWidths=[W / len(itens)] * len(itens))
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEABOVE", (0, 0), (-1, 0), 1.2, colors.HexColor(INK)),
                               ("TOPPADDING", (0, 0), (-1, 0), 8), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        return t

    shE = list(Nst[0] / Nst[0].sum())
    NAT, MOS = MUN["2408102"], MUN["2408003"]
    fE, fN, fM = frac({"sh": shE}), frac(NAT), frac(MOS)

    story = []
    # ================= RESUMO
    story += [Paragraph("Eleições 2026 · Rio Grande do Norte · 1º turno (4 de outubro)", st["kick"]),
              Paragraph("Resumo", st["h1"]),
              P("Este relatório responde a uma pergunta simples: <b>quem votou em Lula para presidente votou em quem para governador?</b> "
                "A resposta ajuda a entender por que Cadu de Lula teve bem menos votos que Lula, e para onde foram os demais votos. "
                "Olhamos o estado como um todo e, em detalhe, os bairros de <b>Natal</b> e de <b>Mossoró</b>."),
              kpis([(n(EST_P[0]), "votos de Lula para presidente no RN"), (n(EST_G[CA]), "votos de Cadu de Lula para governador"),
                    (n(EST_P[0] - EST_G[CA]), "é a diferença entre os dois")]),
              Spacer(1, 12),
              Paragraph("O que os números mostram", st["h2"]),
              LI(f"<b>No RN, de cada 10 eleitores de Lula, cerca de {dez(fE[0])} votaram em Cadu e {dez(fE[1])} em Allyson Bezerra.</b> "
                 f"O restante votou em Álvaro Dias ({br(100 * fE[2], 0)}%) ou em branco, nulo ou outro candidato ({br(100 * fE[3], 0)}%)."),
              LI(f"<b>Em Natal</b>, os eleitores de Lula ficaram mais com Cadu: cerca de {dez(fN[0])} em cada 10 votaram nele e {dez(fN[1])} em Allyson."),
              LI(f"<b>Em Mossoró</b>, onde Allyson Bezerra foi prefeito, o quadro se inverte: cerca de {dez(fM[1])} em cada 10 eleitores de Lula votaram em Allyson "
                 f"e {dez(fM[0])} em Cadu."),
              LI("A maior parte da diferença entre Lula e Cadu se explica, portanto, por eleitores de Lula que escolheram Allyson para governador."),
              Spacer(1, 4),
              img(IMG / "quadrados.png", maxh=7.2 * cm),
              Paragraph("Cada grade representa 100 eleitores de Lula. A cor de cada quadradinho mostra em quem eles votaram para governador (estimativa).", st["cap"]),
              caixa(Paragraph("<b>Atenção: estes números são estimativas.</b> O voto é secreto, então ninguém sabe em quem cada eleitor votou. "
                              "O que se sabe é o resultado de cada urna. Como o mesmo eleitor vota para presidente e para governador na mesma urna, "
                              "dá para comparar as 8.115 urnas do estado e estimar a relação entre os dois votos. A página 2 explica a ideia.", st["box"]),
                    borda=CORG[CA]),
              PageBreak()]

    # ================= COMO LER / COMO SABEMOS
    story += [Paragraph("Como chegamos a esses números", st["h1"]),
              P("Imagine duas urnas do mesmo bairro. Na primeira, Lula teve 70% dos votos; na segunda, 40%. Se na urna onde Lula foi melhor "
                "Cadu também foi bem melhor, isso indica que muitos eleitores de Lula votaram em Cadu. Se Allyson é que sobe junto com Lula, "
                "é sinal de que parte dos eleitores de Lula escolheu Allyson."),
              P("Fazendo essa comparação ao mesmo tempo em milhares de urnas, um modelo estatístico estima <b>que fração dos eleitores de cada candidato "
                "a presidente votou em cada candidato a governador</b>. O cálculo é feito para o estado, para cada município e para cada bairro, e os "
                "resultados são ajustados para bater exatamente com os votos oficiais."),
              Paragraph("Como ler este relatório", st["h2"]),
              tabela(["Termo", "O que significa"], [
                  ["<b>Votos de Lula, Cadu, Allyson, Álvaro</b>", "Resultado oficial do TSE. Não é estimativa."],
                  ["<b>\"De cada 10 eleitores de Lula, X votaram em Cadu\"</b>", "Estimativa. É a forma mais simples de ler as porcentagens: 50% = 5 em cada 10."],
                  ["<b>Bairro</b>", "Bairro onde fica o local de votação (a escola, por exemplo), e não onde o eleitor mora."],
                  ["<b>Confiança</b>", "Alta: bairro com muitas urnas e estimativa estável. Média: menos urnas. Baixa: menos de 10 urnas; "
                                            "nesse caso o número fica próximo da média da cidade."],
                  ["<b>Diferença Lula − Cadu</b>", "Votos de Lula menos votos de Cadu no mesmo lugar. Quanto maior, mais eleitores de Lula não votaram em Cadu."],
              ], [5.6 * cm, W - 5.6 * cm]),
              Spacer(1, 10),
              Paragraph("De onde vem a diferença entre Lula e Cadu", st["h2"]),
              P("O gráfico abaixo parte dos votos de Lula e mostra, degrau por degrau, quantos eleitores dele foram para cada outro candidato a governador. "
                "No fim, somam-se os eleitores de outros candidatos a presidente que votaram em Cadu, e chega-se ao total de Cadu."),
              img(IMG / "escada.png", maxh=11.2 * cm),
              Paragraph("Valores estimados, exceto as barras \"Votos de Lula\" e \"Votos de Cadu\", que são oficiais.", st["cap"]),
              PageBreak()]

    # ================= CIDADES
    for k, (mid, nome) in enumerate(CIDADES):
        m = MUN[mid]; f = frac(m)
        bs = sorted([b for b in B if b["m"] == mid], key=lambda b: -b["p"][0])
        firmes = [b for b in bs if b["s"] >= 10]
        mx_al = sorted(firmes, key=lambda b: -b["sh"][AL])[:3]
        mx_ca = sorted(firmes, key=lambda b: -b["sh"][CA])[:3]
        mx_gap = sorted(bs, key=lambda b: -b["gapV"])[:3]
        lb = sum(b["p"][0] for b in bs)
        lista = lambda xs, fn: ", ".join(f"{b['n']} ({fn(b)})" for b in xs)
        story += [Paragraph(f"{k + 1}. {nome}", st["h1"]),
                  kpis([(n(m["p"][0]), f"votos de Lula ({br(m['pL'], 0)}% dos válidos)"),
                        (n(m["g"][CA]), f"votos de Cadu ({br(m['pC'], 0)}% dos válidos)"),
                        (n(m["g"][AL]), f"votos de Allyson ({br(100 * m['g'][AL] / m['vg'], 0)}% dos válidos)"),
                        (n(m["g"][AV]), f"votos de Álvaro ({br(100 * m['g'][AV] / m['vg'], 0)}% dos válidos)")]),
                  Spacer(1, 10),
                  P(f"Em {nome}, Lula teve <b>{n(m['p'][0] - m['g'][CA])} votos a mais</b> que Cadu. Pela estimativa, de cada 10 eleitores de Lula na cidade, "
                    f"<b>{dez(f[0])} votaram em Cadu</b>, <b>{dez(f[1])} em Allyson</b>"
                    + (f", {dez(f[2])} em Álvaro" if f[2] >= 0.05 else "")
                    + f" e o restante em branco, nulo ou outro candidato. A análise por bairro cobre {len(bs)} bairros, que somam {n(lb)} votos de Lula "
                    f"({br(100 * lb / m['p'][0], 0)}% dos votos dele na cidade)."),
                  Paragraph("Destaques", st["h2"]),
                  LI(f"<b>Onde os eleitores de Lula mais votaram em Allyson:</b> {lista(mx_al, lambda b: dez(b['sh'][AL]) + ' em 10')}."),
                  LI(f"<b>Onde mais votaram em Cadu:</b> {lista(mx_ca, lambda b: dez(b['sh'][CA]) + ' em 10')}."),
                  LI(f"<b>Maiores diferenças entre Lula e Cadu, em votos:</b> {lista(mx_gap, lambda b: sgn(b['gapV']))}."),
                  Paragraph("Considerados apenas bairros com pelo menos 10 urnas nos dois primeiros itens.", st["cap"]),
                  img(IMG / f"mapas_{mid}.png", maxh=9.4 * cm),
                  Paragraph("Quanto mais forte a cor, maior a parte dos eleitores de Lula daquele bairro que votou no candidato. Bairros em cinza não têm local de votação.", st["cap"]),
                  PageBreak(),
                  Paragraph(f"{nome}: bairro por bairro", st["h2"]),
                  P("Cada barra é o total de eleitores de Lula no bairro, dividido pela estimativa de em quem votaram para governador. "
                    "Os bairros com mais votos de Lula estão no alto."),
                  img(IMG / f"barras_{mid}.png", maxh=16.5 * cm),
                  PageBreak()]
        rows = []
        for b in bs:
            fb = frac(b)
            rows.append([b["n"], n(b["p"][0]), n(b["g"][CA]), sgn(b["gapV"]),
                         f"<b>{dz(fb[0])}</b> <font color='{MUTED}'>({n(fb[0] * b['p'][0])})</font>",
                         f"<b>{dz(fb[1])}</b> <font color='{MUTED}'>({n(fb[1] * b['p'][0])})</font>",
                         f"{dz(fb[2] + fb[3])} <font color='{MUTED}'>({n((fb[2] + fb[3]) * b['p'][0])})</font>",
                         confianca(b)])
        lv = np.sum([[frac(b)[i] * b["p"][0] for i in range(4)] for b in bs], axis=0)
        rows.append(["<b>Todos os bairros</b>", f"<b>{n(lb)}</b>", f"<b>{n(sum(b['g'][CA] for b in bs))}</b>", f"<b>{sgn(lb - sum(b['g'][CA] for b in bs))}</b>",
                     f"<b>{dz(lv[0] / lb)}</b> <font color='{MUTED}'>({n(lv[0])})</font>", f"<b>{dz(lv[1] / lb)}</b> <font color='{MUTED}'>({n(lv[1])})</font>",
                     f"{dz((lv[2] + lv[3]) / lb)} <font color='{MUTED}'>({n(lv[2] + lv[3])})</font>", ""])
        story += [Paragraph(f"{nome}: tabela dos bairros", st["h2"]),
                  P("Nas três colunas da direita: <b>de cada 10 eleitores de Lula no bairro</b>, quantos votaram em cada opção. Exemplo: \"5,5\" em Cadu quer dizer 5 e meio em cada 10, ou 55%. Entre parênteses, o número estimado de eleitores."),
                  tabela(["Bairro", "Votos de Lula", "Votos de Cadu", "Lula − Cadu", "De cada 10 eleitores de Lula: Cadu", "Allyson",
                          "Álvaro, branco, nulo ou outro", "Confiança"], rows,
                         [4.1 * cm, 1.6 * cm, 1.6 * cm, 1.6 * cm, 2.45 * cm, 1.95 * cm, 2.3 * cm, 1.8 * cm], right=(1, 2, 3, 4, 5, 6), bold_last=True),
                  PageBreak()]

    # ================= COMPARAÇÃO E MÉTODO
    def linha_c(nome, m):
        f = frac(m)
        return [nome, n(m["p"][0]), n(m["g"][CA]), n(m["p"][0] - m["g"][CA]), f"{dz(f[0])} em 10", f"{dz(f[1])} em 10", f"{dz(f[2] + f[3])} em 10"]
    estm = {"p": EST_P, "g": EST_G, "sh": shE}
    story += [Paragraph(f"{len(CIDADES) + 1}. Natal e Mossoró lado a lado", st["h1"]),
              tabela(["", "Votos de Lula", "Votos de Cadu", "Diferença", "Eleitores de Lula com Cadu", "com Allyson", "outros"],
                     [linha_c("Rio Grande do Norte", estm), linha_c("Natal", NAT), linha_c("Mossoró", MOS)],
                     [3.6 * cm, 2.2 * cm, 2.2 * cm, 2.0 * cm, 2.9 * cm, 2.2 * cm, 2.3 * cm], right=(1, 2, 3, 4, 5, 6)),
              Spacer(1, 8),
              P(f"As duas maiores cidades do estado mostram comportamentos diferentes dos eleitores de Lula. Em Natal, a maioria deles acompanhou Cadu; "
                f"em Mossoró, onde Allyson Bezerra foi prefeito, a maioria votou em Allyson. Juntas, as duas cidades têm "
                f"{n(NAT['p'][0] + MOS['p'][0])} votos de Lula, {br(100 * (NAT['p'][0] + MOS['p'][0]) / EST_P[0], 0)}% do total do estado."),
              Paragraph(f"{len(CIDADES) + 2}. Detalhes do método (para quem quer saber mais)", st["h1"]),
              P("<b>Dados.</b> Votos para Presidente por urna (boletins de urna do TSE) e votos para Governador por urna (arquivo de votação por seção do TSE), "
                "casados pela zona e pelo número da seção. Votos em candidatos a governador com registro indeferido contam como nulos, como na totalização oficial. "
                "Cada urna foi atribuída ao bairro do IBGE (Censo 2022) onde fica o seu local de votação."),
              P("<b>Modelo.</b> Inferência ecológica: procura-se a tabela de transferência (fração dos eleitores de cada candidato a presidente que votou em cada "
                "candidato a governador) que melhor reproduz o resultado de todas as urnas ao mesmo tempo, com frações entre 0 e 100%, ponderando cada urna pelo "
                "número de votantes. A tabela de cada município é puxada para a do estado, e a de cada bairro para a do município, com força equivalente a "
                f"{int(D['meta']['lambda'])} urnas: num bairro com 150 urnas a estimativa é quase toda do próprio bairro; num bairro com 5, fica perto da média da cidade. "
                "Por fim, os números são ajustados para somar exatamente os votos oficiais de cada candidato."),
              P(f"<b>Confiança.</b> Calculada a partir de {D['meta']['nboot']} reamostragens das urnas. \"Alta\": 30 urnas ou mais e variação de até 4 pontos "
                "percentuais entre as reamostragens; \"média\": 10 urnas ou mais; \"baixa\": menos de 10 urnas."),
              P("<b>Limites.</b> O modelo supõe que, dentro de um bairro, eleitores de Lula de urnas diferentes votam de forma parecida para governador. "
                "Se isso não for verdade, a estimativa pode errar, e a confiança não mede esse tipo de erro. Os números devem ser lidos como ordem de "
                "grandeza e comparados com pesquisas de opinião, que perguntam diretamente ao eleitor."),
              P("<b>Arquivos.</b> As estimativas de todos os bairros do estado estão em docs/dados/lula/transferencia_estimada_bairros.csv, no repositório "
                "github.com/felipemechatronics/Elei-es-2026, e na página interativa Lula × Governo do site do projeto. Base geográfica a partir do projeto "
                "Como o RN votou para governador, de Peterson Sousa.")]

    def deco(canvas, doc):
        canvas.saveState()
        canvas.setFont("DV", 7); canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(1.8 * cm, 1.1 * cm, "Os votos de Lula e o voto para governador · Natal e Mossoró · 1º turno de 2026")
        canvas.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm, f"{doc.page}")
        canvas.setStrokeColor(colors.HexColor(LINE)); canvas.line(1.8 * cm, 1.45 * cm, A4[0] - 1.8 * cm, 1.45 * cm)
        canvas.restoreState()

    pdf = OUT / "lula_bairros_RN_2026.pdf"
    doc = BaseDocTemplate(str(pdf), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.5 * cm, bottomMargin=1.9 * cm,
                          title="Os votos de Lula e o voto para governador em Natal e Mossoró", author="Elei-es-2026",
                          subject="Estimativa do voto para governador dos eleitores de Lula por bairro, 1º turno de 2026")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=deco)])
    doc.build(story)
    dst = RAIZ / "docs" / "relatorio"; dst.mkdir(exist_ok=True)
    shutil.copy(pdf, dst / pdf.name)
    print(pdf)


if __name__ == "__main__":
    build()
