"""Relatório em PDF: os votos de Lula por candidato a governador nos bairros do RN (1º turno de 2026).

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


# ------------------------------------------------------------------ documento
def build():
    IMG.mkdir(parents=True, exist_ok=True)
    fig_estado(IMG / "estado.png"); fig_dispersao(IMG / "dispersao_bairros.png")
    for mid in GRANDES:
        fig_cidade(mid, IMG / f"mapas_{mid}.png"); fig_barras_cidade(mid, IMG / f"barras_{mid}.png")

    st = {
        "h1": ParagraphStyle("h1", fontName="DVB", fontSize=16, leading=20, textColor=colors.HexColor(INK), spaceAfter=8, spaceBefore=4),
        "h2": ParagraphStyle("h2", fontName="DVB", fontSize=11.5, leading=15, textColor=colors.HexColor(INK), spaceBefore=10, spaceAfter=5),
        "p": ParagraphStyle("p", fontName="DV", fontSize=9, leading=13.4, textColor=colors.HexColor(INK), spaceAfter=6),
        "small": ParagraphStyle("s", fontName="DV", fontSize=7.6, leading=10.5, textColor=colors.HexColor(INK2), spaceAfter=4),
        "cap": ParagraphStyle("c", fontName="DVI", fontSize=7.3, leading=10, textColor=colors.HexColor(MUTED), spaceAfter=8),
        "big": ParagraphStyle("b", fontName="DVB", fontSize=22, leading=25, textColor=colors.HexColor(INK)),
        "lbl": ParagraphStyle("l", fontName="DV", fontSize=8, leading=10.5, textColor=colors.HexColor(INK2)),
        "cell": ParagraphStyle("cell", fontName="DV", fontSize=6.9, leading=8.6, textColor=colors.HexColor(INK)),
    }
    W = A4[0] - 3.6 * cm
    P = lambda t: Paragraph(t, st["p"])

    def img(path, width=W, maxh=None):
        from PIL import Image as PI
        w, h = PI.open(path).size
        hh = width * h / w
        if maxh and hh > maxh:
            width, hh = width * maxh / hh, maxh
        return Image(str(path), width=width, height=hh)

    def tabela(head, rows, widths, right=(), zebra=False):
        data = [[Paragraph(f"<b>{h}</b>", st["cell"]) for h in head]] + [[Paragraph(str(c), st["cell"]) for c in r] for r in rows]
        t = Table(data, colWidths=widths, repeatRows=1)
        sty = [("LINEBELOW", (0, 0), (-1, 0), .8, colors.HexColor(INK)), ("LINEBELOW", (0, 1), (-1, -1), .25, colors.HexColor(LINE)),
               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
               ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
        t.setStyle(TableStyle(sty))
        for i in right:
            for row in data:
                row[i].style = ParagraphStyle("r", parent=st["cell"], alignment=TA_RIGHT)
        return t

    def cel(b, j, ci=True):
        lo, hi = b.get("lo"), b.get("hi")
        s = f"{n(b['lv'][j])} <font color='{MUTED}'>({br(100 * b['sh'][j], 0)}%)</font>"
        if ci and lo:
            s += f"<br/><font size='5.8' color='{MUTED}'>[{br(100 * lo[j], 0)}–{br(100 * hi[j], 0)}%]</font>"
        return s

    HEAD = ["Bairro", "Seç.", "Lula", "Cadu", "Lula − Cadu", "Lula → Cadu", "Lula → Allyson", "Lula → Álvaro", "Lula → branco, nulo ou outro"]
    WID = [3.5 * cm, 1.05 * cm, 1.55 * cm, 1.55 * cm, 1.65 * cm, 2.05 * cm, 2.05 * cm, 1.95 * cm, 2.05 * cm]

    def linha(b, nome=None):
        bo = dict(b); bo["lv"] = list(b["lv"]); bo["lv"][GB] = b["lv"][GB] + b["lv"][GO]
        bo["sh"] = list(b["sh"]); bo["sh"][GB] = b["sh"][GB] + b["sh"][GO]
        if b.get("lo"):
            bo["lo"] = list(b["lo"]); bo["hi"] = list(b["hi"]); bo["lo"][GB] = b["lo"][GB] + b["lo"][GO]; bo["hi"][GB] = b["hi"][GB] + b["hi"][GO]
        return [(nome or b["n"]) + (" *" if b["s"] < 10 else ""), n(b["s"]), n(b["p"][0]), n(b["g"][CA]), sgn(b["gapV"]),
                cel(bo, CA), cel(bo, AL), cel(bo, AV), cel(bo, GB)]

    story = []
    # ---- capa
    natal = MUN["2408102"]
    top_al = max(B, key=lambda b: b["lv"][AL])
    story += [Spacer(1, 2.4 * cm),
              Paragraph("Eleições 2026 · Rio Grande do Norte · 1º turno", st["lbl"]), Spacer(1, 6),
              Paragraph("Os votos de Lula e o voto para governador nos bairros",
                        ParagraphStyle("t", parent=st["h1"], fontSize=26, leading=31)),
              Paragraph("Estimativa de como os eleitores de Lula votaram para governador (Allyson Bezerra, Cadu de Lula, Álvaro Dias, "
                        f"branco ou nulo) em {len(B)} bairros de {len(CID)} municípios, a partir dos resultados das seções eleitorais",
                        ParagraphStyle("sub", parent=st["p"], fontSize=11.5, leading=16, textColor=colors.HexColor(INK2))),
              Spacer(1, 1.0 * cm)]
    kp = [[Paragraph(n(LB), st["big"]), Paragraph(f"{br(100 * LVB[CA] / LB, 0)}%", st["big"]), Paragraph(f"{br(100 * LVB[AL] / LB, 0)}%", st["big"])],
          [Paragraph(f"votos de Lula nos bairros analisados ({br(100 * LB / EST_P[0], 0)}% dos votos de Lula no estado)", st["lbl"]),
           Paragraph(f"dos eleitores de Lula nesses bairros votaram em Cadu de Lula (estimado; no estado, {br(100 * sh_est[CA], 0)}%)", st["lbl"]),
           Paragraph(f"votaram em Allyson Bezerra (estimado; no estado, {br(100 * sh_est[AL], 0)}%)", st["lbl"])]]
    t = Table(kp, colWidths=[W / 3] * 3)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEABOVE", (0, 0), (-1, 0), 1.2, colors.HexColor(INK)), ("TOPPADDING", (0, 0), (-1, 0), 10)]))
    story += [t, Spacer(1, 1.0 * cm), img(IMG / "mapas_2408102.png"),
              Paragraph("Natal: diferença entre os votos de Lula e de Cadu e estimativa do voto para governador dos eleitores de Lula, por bairro.", st["cap"]),
              Spacer(1, 0.5 * cm),
              Paragraph("O voto é secreto: nenhum dado oficial diz em quem cada eleitor de Lula votou para governador. Os números deste relatório "
                        "são estimativas estatísticas feitas com os resultados das seções eleitorais, nas quais os mesmos eleitores votaram para os dois cargos. "
                        "Fonte: TSE (boletins de urna e votação por seção do 1º turno); malha de bairros do IBGE (Censo 2022).", st["cap"]),
              PageBreak()]

    # ---- 1. resumo
    bs_g = [b for b in B if b["s"] >= 10]
    mx_al = max(bs_g, key=lambda b: b["sh"][AL]); mx_ca = max(bs_g, key=lambda b: b["sh"][CA])
    mx_gap = max(B, key=lambda b: b["gapV"])
    cid_txt = ", ".join(f"{MUN[m]['n']} ({sum(1 for b in B if b['m'] == m)})" for m in CID)
    story += [Paragraph("1. Resumo", st["h1"]),
              P(f"No estado, Lula teve <b>{n(EST_P[0])}</b> votos para presidente e Cadu de Lula, <b>{n(EST_G[CA])}</b> para governador: "
                f"uma diferença de <b>{n(EST_P[0] - EST_G[CA])}</b> votos. Pela estimativa, cerca de <b>{br(100 * sh_est[CA], 0)}%</b> dos eleitores de Lula "
                f"votaram em Cadu, <b>{br(100 * sh_est[AL], 0)}%</b> em Allyson Bezerra, <b>{br(100 * sh_est[AV], 0)}%</b> em Álvaro Dias e "
                f"<b>{br(100 * (sh_est[GB] + sh_est[GO]), 0)}%</b> votaram branco, nulo ou em outro candidato."),
              P(f"Este relatório desce ao nível de bairro nos {len(CID)} municípios que têm bairros delimitados pelo IBGE e locais de votação dentro deles: "
                f"{cid_txt}. São {len(B)} bairros, {n(SECB)} seções e {n(LB)} votos de Lula, {br(100 * LB / EST_P[0], 0)}% do total do estado."),
              P(f"Nesses bairros, a estimativa é que <b>{n(LVB[CA])}</b> eleitores de Lula ({br(100 * LVB[CA] / LB, 0)}%) votaram em Cadu, "
                f"<b>{n(LVB[AL])}</b> ({br(100 * LVB[AL] / LB, 0)}%) em Allyson, <b>{n(LVB[AV])}</b> ({br(100 * LVB[AV] / LB, 0)}%) em Álvaro "
                f"e <b>{n(LVB[GB] + LVB[GO])}</b> ({br(100 * (LVB[GB] + LVB[GO]) / LB, 0)}%) votaram branco, nulo ou em outro."),
              P(f"Entre os bairros com pelo menos 10 seções, a maior parcela estimada de eleitores de Lula com Allyson está em "
                f"<b>{mx_al['n']}</b> ({mx_al['mn']}), com {br(100 * mx_al['sh'][AL], 0)}%; a maior parcela com Cadu, em <b>{mx_ca['n']}</b> "
                f"({mx_ca['mn']}), com {br(100 * mx_ca['sh'][CA], 0)}%. A maior diferença em votos entre Lula e Cadu está em <b>{mx_gap['n']}</b> "
                f"({mx_gap['mn']}): {sgn(mx_gap['gapV'])} votos. O bairro com mais eleitores de Lula que votaram em Allyson, em número, é "
                f"<b>{top_al['n']}</b> ({top_al['mn']}), com cerca de {n(top_al['lv'][AL])}."),
              Paragraph("Como ler", st["h2"]),
              P("Os votos de Lula, Cadu e dos demais candidatos são os resultados oficiais. As colunas \"Lula → …\" são estimativas: quantos eleitores "
                "de Lula naquele bairro votaram em cada opção para governador, com a porcentagem sobre os eleitores de Lula do bairro. Embaixo, entre "
                "colchetes, o intervalo de 90% da porcentagem. O voto é contado no bairro do <i>local de votação</i>, não no bairro onde o eleitor mora. "
                "Bairros marcados com * têm menos de 10 seções: a estimativa deles fica próxima da do município e merece mais cautela."),
              Paragraph("2. O estado", st["h2"]),
              img(IMG / "estado.png"),
              Paragraph("Como votaram para governador os eleitores de cada candidato a presidente (estimativa, % de cada linha). Entre parênteses, votos para presidente.", st["cap"])]
    rows = []
    for i in range(4):
        t = Nst[i].sum()
        rows.append([NOMEP[i]] + [f"{br(100 * Nst[i, j] / t)}%<br/><font size='5.8' color='{MUTED}'>[{br(100 * D['lo'][i][j], 0)}–{br(100 * D['hi'][i][j], 0)}]</font>" for j in range(5)])
    story += [tabela(["Presidente → governador"] + NOMEG, rows, [4.2 * cm] + [2.64 * cm] * 5, right=(1, 2, 3, 4, 5)),
              Spacer(1, 6),
              Paragraph(f"De onde vieram os votos para governador (estimado): {br(100 * Nst[0, AL] / EST_G[AL], 0)}% dos votos de Allyson Bezerra, "
                        f"{br(100 * Nst[0, CA] / EST_G[CA], 0)}% dos de Cadu de Lula e {br(100 * Nst[0, AV] / EST_G[AV], 0)}% dos de Álvaro Dias vieram de eleitores de Lula.", st["small"]),
              PageBreak()]

    # ---- 3. visão geral dos bairros
    story += [Paragraph("3. Os bairros em conjunto", st["h1"]),
              P("Quanto maior a votação de Lula em um bairro, maior tende a ser a parcela dos seus eleitores que votou em Cadu? Os gráficos abaixo comparam, bairro a bairro, "
                "o desempenho de Lula com a estimativa do voto para governador dos seus eleitores."),
              img(IMG / "dispersao_bairros.png"), Spacer(1, 8)]
    rows = []
    for m in CID:
        bs = [b for b in B if b["m"] == m]
        lv = np.sum([b["lv"] for b in bs], axis=0); lb = sum(b["p"][0] for b in bs)
        rows.append([MUN[m]["n"], len(bs), n(sum(b["s"] for b in bs)), n(lb), n(sum(b["g"][CA] for b in bs)),
                     f"{n(lv[CA])} <font color='{MUTED}'>({br(100 * lv[CA] / lb, 0)}%)</font>", f"{n(lv[AL])} <font color='{MUTED}'>({br(100 * lv[AL] / lb, 0)}%)</font>",
                     f"{n(lv[AV])} <font color='{MUTED}'>({br(100 * lv[AV] / lb, 0)}%)</font>", f"{n(lv[GB] + lv[GO])} <font color='{MUTED}'>({br(100 * (lv[GB] + lv[GO]) / lb, 0)}%)</font>"])
    story += [Paragraph("Bairros por município (soma dos bairros com local de votação)", st["h2"]),
              tabela(["Município", "Bairros", "Seções", "Lula", "Cadu", "Lula → Cadu", "Lula → Allyson", "Lula → Álvaro", "Lula → branco, nulo ou outro"], rows,
                     [3.6 * cm, 1.2 * cm, 1.3 * cm, 1.6 * cm, 1.6 * cm, 2.1 * cm, 2.1 * cm, 1.95 * cm, 2.0 * cm], right=tuple(range(1, 9))),
              Paragraph("Nos municípios com poucos bairros delimitados, eles cobrem só parte do eleitorado do município.", st["cap"]),
              PageBreak()]

    # ---- 4. cidades
    sec = 4
    for k, mid in enumerate(GRANDES):
        m = MUN[mid]; bs = sorted([b for b in B if b["m"] == mid], key=lambda b: -b["p"][0])
        lv = np.sum([b["lv"] for b in bs], axis=0); lb = sum(b["p"][0] for b in bs)
        mx_al = max(bs, key=lambda b: b["sh"][AL]); mx_ca = max(bs, key=lambda b: b["sh"][CA])
        story += [Paragraph(f"{sec}.{k + 1} {m['n']}", st["h1"]),
                  P(f"Em {m['n']}, Lula teve {n(m['p'][0])} votos ({br(m['pL'])}% dos válidos para presidente) e Cadu de Lula {n(m['g'][CA])} "
                    f"({br(m['pC'])}% dos válidos para governador); Allyson Bezerra teve {n(m['g'][AL])} e Álvaro Dias {n(m['g'][AV])}. "
                    f"Para o município inteiro, a estimativa é que {br(100 * m['sh'][CA], 0)}% dos eleitores de Lula votaram em Cadu e "
                    f"{br(100 * m['sh'][AL], 0)}% em Allyson. Nos {len(bs)} bairros com local de votação ({n(lb)} votos de Lula), "
                    f"a parcela com Allyson vai de {br(100 * min(b['sh'][AL] for b in bs), 0)}% a {br(100 * mx_al['sh'][AL], 0)}% ({mx_al['n']}), "
                    f"e a parcela com Cadu, de {br(100 * min(b['sh'][CA] for b in bs), 0)}% a {br(100 * mx_ca['sh'][CA], 0)}% ({mx_ca['n']})."),
                  img(IMG / f"mapas_{mid}.png", maxh=8.2 * cm),
                  Spacer(1, 4),
                  img(IMG / f"barras_{mid}.png", maxh=13 * cm),
                  Paragraph("Barras: eleitores de Lula em cada bairro, divididos pela estimativa do voto para governador. * menos de 10 seções.", st["cap"]),
                  CondPageBreak(6 * cm),
                  Paragraph(f"Tabela: {m['n']}, bairro a bairro", st["h2"]),
                  tabela(HEAD, [linha(b) for b in bs] + [["<b>Total dos bairros</b>", n(sum(b["s"] for b in bs)), f"<b>{n(lb)}</b>",
                                                          f"<b>{n(sum(b['g'][CA] for b in bs))}</b>", f"<b>{sgn(lb - sum(b['g'][CA] for b in bs))}</b>",
                                                          f"<b>{n(lv[CA])}</b>", f"<b>{n(lv[AL])}</b>", f"<b>{n(lv[AV])}</b>", f"<b>{n(lv[GB] + lv[GO])}</b>"]],
                         WID, right=tuple(range(1, 9))),
                  PageBreak()]
    # ---- demais municípios
    if PEQ:
        story += [Paragraph(f"{sec}.{len(GRANDES) + 1} Demais municípios com bairros", st["h1"]),
                  P("Municípios com menos de cinco bairros com local de votação. Em geral, os bairros delimitados cobrem a área central e parte do eleitorado.")]
        rows = []
        for mid in PEQ:
            for b in sorted([b for b in B if b["m"] == mid], key=lambda b: -b["p"][0]):
                rows.append(linha(b, f"{b['n']} <font color='{MUTED}'>({MUN[mid]['n']})</font>"))
        story += [tabela(HEAD, rows, WID, right=tuple(range(1, 9))), PageBreak()]

    # ---- método
    r2 = D["meta"]["r2"]
    story += [Paragraph("5. Como foi feito", st["h1"]),
              P("<b>Dados.</b> Votos para Presidente por seção, dos boletins de urna do TSE; votos para Governador por seção, do arquivo de votação por seção do TSE. "
                "As duas fontes foram casadas por zona e número da seção (8.115 seções). Votos em candidatos a governador com registro indeferido entram como nulos, como "
                "na totalização oficial. Cada seção foi atribuída ao bairro do IBGE (Censo 2022) que contém o seu local de votação, pela coordenada do cadastro do TSE."),
              P("<b>Estimativa.</b> O voto é secreto, então a relação entre o voto para presidente e o voto para governador é estimada por inferência ecológica. "
                "Em cada seção se conhece a parcela de Lula, de Flávio Bolsonaro, dos demais candidatos e de brancos e nulos para presidente, e a parcela de cada opção "
                "para governador. Procura-se a tabela de transferência (que fração dos eleitores de cada candidato a presidente votou em cada candidato a governador) "
                "que melhor reproduz os resultados de todas as seções ao mesmo tempo, com cada fração entre 0 e 100% e cada linha somando 100%, ponderando as seções pelo comparecimento."),
              P(f"<b>Do estado ao bairro.</b> A tabela é estimada para o estado, depois para cada município (puxada em direção à estadual) e depois para cada bairro, com as seções "
                f"dos locais de votação do bairro, puxada em direção à tabela do município. A força dessa aproximação equivale a {int(D['meta']['lambda'])} seções: num bairro "
                f"com 150 seções, a estimativa é quase toda do próprio bairro; num bairro com 5 seções, fica perto da do município. Por fim, as contagens de cada bairro são "
                f"ajustadas para somar exatamente os votos reais de cada candidato a governador no bairro e as proporções reais de cada candidato a presidente."),
              P(f"<b>Incerteza.</b> O intervalo de 90% vem de {D['meta']['nboot']} reamostragens das seções dentro de cada bairro e município. "
                f"No nível das seções, o modelo explica {br(100 * r2['allyson'], 0)}% da variação do voto em Allyson Bezerra, {br(100 * r2['cadu'], 0)}% do voto em Cadu "
                f"de Lula e {br(100 * r2['alvaro'], 0)}% do voto em Álvaro Dias."),
              P("<b>Limites.</b> A estimativa supõe que, dentro de um bairro, eleitores de Lula de seções diferentes votam para governador de forma parecida. Quando isso não "
                "acontece, a estimativa pode ficar enviesada, e o intervalo de 90% não captura esse tipo de erro. O bairro é o do local de votação: eleitores que votam em "
                "uma escola de um bairro podem morar em outro. Use os números como ordem de grandeza e compare com pesquisas de opinião, que perguntam diretamente ao eleitor."),
              P("<b>Arquivos.</b> As estimativas de todos os bairros, com os intervalos de cada célula, estão em docs/dados/lula/transferencia_estimada_bairros.csv. "
                "O cálculo está em scripts/gerar_lula.py e este relatório em scripts/gerar_pdf_lula.py, no repositório github.com/felipemechatronics/Elei-es-2026. "
                "A página interativa (Lula × Governo) traz mapas e tabelas de municípios e bairros e uma simulação de migração para o 2º turno."),
              P("Base geográfica (coordenadas dos locais de votação e atribuição de bairros) organizada a partir do projeto Como o RN votou para governador, de Peterson Sousa.")]

    def deco(canvas, doc):
        canvas.saveState()
        canvas.setFont("DV", 7); canvas.setFillColor(colors.HexColor(MUTED))
        if doc.page > 1:
            canvas.drawString(1.8 * cm, 1.1 * cm, "Os votos de Lula e o voto para governador nos bairros · RN, 1º turno de 2026")
            canvas.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm, f"{doc.page}")
            canvas.setStrokeColor(colors.HexColor(LINE)); canvas.line(1.8 * cm, 1.45 * cm, A4[0] - 1.8 * cm, 1.45 * cm)
        canvas.restoreState()

    pdf = OUT / "lula_bairros_RN_2026.pdf"
    doc = BaseDocTemplate(str(pdf), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.9 * cm,
                          title="Os votos de Lula e o voto para governador nos bairros do RN", author="Elei-es-2026",
                          subject="Estimativa do voto para governador dos eleitores de Lula por bairro, 1º turno de 2026")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=deco)])
    doc.build(story)
    dst = RAIZ / "docs" / "relatorio"; dst.mkdir(exist_ok=True)
    shutil.copy(pdf, dst / pdf.name)
    print(pdf)


if __name__ == "__main__":
    build()
