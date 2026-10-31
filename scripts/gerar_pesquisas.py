"""Gera docs/pesquisas.js a partir da planilha de acompanhamento de pesquisas (RN 2026).

Entrada (exportada da planilha "PESQUISAS RN 2026", abas "Completa Gov e Sen" e "Governo 2 turno"):
  dados_pesquisas/pesquisas_1turno.csv   Governador e Senador, 1º turno
  dados_pesquisas/pesquisas_2turno.csv   Governador, 2º turno
Resultados oficiais: docs/governador.js, docs/governador_2t.js e o votacao_secao (Senador).

A data de cada pesquisa é o último dia do trabalho de campo (ou a de publicação, quando a planilha não traz o campo).
Cada pesquisa vira votos válidos: o percentual de cada candidato dividido pela soma dos candidatos
daquela pesquisa (sem brancos, nulos, indecisos e "rejeita todos"), que é como o TSE divulga o resultado.

Uso:  python scripts/gerar_pesquisas.py
"""
import csv, json, re, sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DP, DOCS = RAIZ / "dados_pesquisas", RAIZ / "docs"
ANO = 2026
MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}

# rótulo limpo de cada coluna da aba "Completa Gov e Sen" (na ordem da planilha; None = coluna vazia)
COL1 = ["DATAVERO (cenário 1) · 10–11/jan", "Affare (cenário 1) · 8–12/jan", "TN/Consult (cenário 1) · 15–18/mar",
        "Seta (cenário 1) · 7–9/mar", "Metadata · 27–28/mar", "Instituto Veritá · 29/mar–4/abr", "Seta · 31/mar–2/abr",
        "Instituto Affare · 7–11/abr", "Data Census (cenário 1) · 18–20/abr", "Exatus · 14–17/mai", "Seta (cenário 1) · 3–5/mai",
        "Instituto Veritá · 4–8/mai", "Metadata · 7–9/mai", "Instituto Affare · 16–21/mai", "Seta (cenário 2) · 26–28/mai",
        "Data Census (cenário 2) · 20–23/abr", "AtlasIntel · 22–27/mai", "Item · 18–22/mai", "O Potengi · 21–27/mai",
        "Seta (cenário 2) · 26–28/mai", "Agorasei · 28–31/mai", None, None, None, None, "Insppe/Clube FM · 28–31/mai",
        "Exatus · 26–29/jun", "Veritá · 27–31/mai", "98 FM · 12–14/jun", "Seta · 15–17/jun", "IPSensus · 18–22/jun",
        "Item · 22–24/jun", "Data Census · 26–29/jun", "Data Capital", "Metadata/98 FM", "Agora Sei", "Seta · 7–9/ago",
        "DATAVERO · 10–12/ago", "TN/Consult · 8–10/ago", "Data Census · 26–29/ago", "Item · 18–22/ago", "Perfil/BG · 13–16/ago",
        "Quaest/InterTV · 20–23/ago"]
COL2 = ["Seta · 10–13/out", "Quaest · 10–11/out", "Affare · 10–11/out", "DATAVERO/Diário do RN · 13–15/out",
        "Data Capital · 13–15/out", "Real Time Big Data/UOL · 15–19/out", "Mensury · 15–19/out"]

GOV = {"Cadu Xavier": "cadu", "Allyson Bezerra": "allyson", "Álvaro Dias": "alvaro", "Rogério Marinho": "rogerio",
       "Carlos Eduardo": "carlos", "Robério Paulino": "roberio", "Karlo Vieira": "karlo", "Dário Barbosa": "dario"}
SEN = {"Fátima Bezerra": "fatima", "Styvenson Valentim": "styvenson", "Álvaro Dias": "alvaro_s", "Coronel Hélio": "helio",
       "Zaneide Maia": "zenaide", "Jean Paul Prates": "jeanpaul", "Thabatta Pimenta": "thabatta", "Samanda Alves": "samanda",
       "Ezequiel Ferreira": "ezequiel", "Rafael Motta": "rafael", "Sandro pimentel": "sandro", "Babá pereira": "baba",
       "Luciana Lima": "luciana", "Rosália Fernandes": "rosalia", "Flávio Rocha": "flaviorocha", "Luizinho Cavalcante": "luizinho"}
NOMES = {"cadu": "Cadu de Lula", "allyson": "Allyson Bezerra", "alvaro": "Álvaro Dias", "rogerio": "Rogério Marinho",
         "carlos": "Carlos Eduardo", "roberio": "Robério Paulino", "karlo": "Karlo Vieira", "dario": "Dário Barbosa",
         "fatima": "Fátima Bezerra", "styvenson": "Styvenson Valentim", "alvaro_s": "Álvaro Dias", "helio": "Coronel Hélio",
         "zenaide": "Zenaide Maia", "jeanpaul": "Jean Paul Prates", "thabatta": "Thabatta Pimenta", "samanda": "Samanda Alves",
         "ezequiel": "Ezequiel Ferreira", "rafael": "Rafael Motta", "sandro": "Sandro Pimentel", "baba": "Babá Pereira",
         "luciana": "Luciana Lima", "rosalia": "Rosália Fernandes", "flaviorocha": "Flávio Rocha", "luizinho": "Luizinho Cavalcante"}
# quem de fato concorreu (para marcar cenários com candidatos que saíram da disputa)
CONCORREU = {"cadu", "allyson", "alvaro", "karlo", "styvenson", "samanda", "zenaide", "helio", "rafael", "sandro", "luciana", "rosalia"}
PRINCIPAIS = {"gov1": ["allyson", "cadu", "alvaro"], "gov2": ["allyson", "cadu"],
              "sen1": ["styvenson", "samanda", "zenaide", "helio", "rafael"]}
OUTROS_LBL = {"Nulo/Branco": "bn", "Nulos/brancos": "bn", "Não Sabe/Não respondeu": "ns", "Não sabe/não respondeu": "ns",
              "Não Sabe/ Não Respondeu": "ns", "Rejeita todos/não votaria em nenhum": "rej"}


def num(s):
    s = (s or "").strip()
    return float(s.replace(".", "").replace(",", ".")) if re.fullmatch(r"[\d.]+(,\d+)?", s) and s.count(".") <= 1 and not re.fullmatch(r"\d+\.\d{1,2}", s) else (
        float(s.replace(",", ".")) if re.fullmatch(r"\d+(,\d+)?", s) else None)


def pct(s):
    s = (s or "").strip()
    return float(s.replace(",", ".")) if re.fullmatch(r"\d+(,\d+)?", s) else None


def data(s):
    m = re.match(r"(\d{1,2})[-.]\s*([a-zç]+)", (s or "").strip().lower())
    return date(ANO, MESES[m[2][:3]], int(m[1])).isoformat() if m else None


def fim_campo(rot):
    """Último dia do trabalho de campo, a partir do rótulo ("26–29/ago", "29/mar–4/abr")."""
    m = re.search(r"(\d{1,2})/([a-z]{3})$", rot)
    return date(ANO, MESES[m[2]], int(m[1])).isoformat() if m else None


def ler(arq):
    return list(csv.reader(open(arq, encoding="utf-8")))


def blocos(rows, labels, cargos):
    """Lê as linhas da planilha e devolve pesquisas por cargo."""
    datas = rows[1][1:]; ns = rows[2][1:]
    out, cargo = [], cargos[0][0]
    vals = {c: {} for c, _ in cargos}; outros = {c: {} for c, _ in cargos}
    for r in rows[3:]:
        nome = r[0].strip()
        trocou = [c for c, marca in cargos if marca and nome.startswith(marca)]
        if trocou:
            cargo = trocou[0]; continue
        mapa = GOV if cargo.startswith("gov") else SEN
        chave = mapa.get(nome) or OUTROS_LBL.get(nome)
        if not chave:
            if nome:
                print("linha ignorada:", nome, file=sys.stderr)
            continue
        for i, v in enumerate(r[1:]):
            x = pct(v)
            if x is None:
                continue
            (outros if nome in OUTROS_LBL else vals)[cargo].setdefault(i, {})[chave] = x
    for c, _ in cargos:
        vistos = set()
        for i, cand in sorted(vals[c].items()):
            if i >= len(labels) or labels[i] is None or not datas[i].strip():
                continue
            assin = (labels[i].split(" · ")[0], datas[i], tuple(sorted(cand.items())))
            if assin in vistos:
                continue                                   # coluna repetida na planilha
            vistos.add(assin)
            fora = sum(v for k, v in cand.items() if k not in CONCORREU)
            n = ns[i].strip().replace(".", "")
            out.append({"c": c, "id": f"{c}-{i}", "inst": labels[i].split(" · ")[0].replace(" (cenário 1)", "").replace(" (cenário 2)", ""),
                        "rot": labels[i], "d": fim_campo(labels[i]) or data(datas[i]), "pub": data(datas[i]), "n": int(n) if n.isdigit() else None,
                        "v": cand, "o": outros[c].get(i, {}), "fora": round(fora, 2)})
    return out


def resultados():
    def js(nome):
        s = (DOCS / nome).read_text(encoding="utf-8"); return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))
    g1, g2 = js("governador.js"), js("governador_2t.js")
    pr = {44: "allyson", 13: "cadu", 22: "alvaro", 36: "karlo"}
    res = {}
    for cid, d in (("gov1", g1), ("gov2", g2)):
        res[cid] = {"v": d["estado"]["v"], "votos": {pr[c["nr"]]: d["estado"]["vt"][c["k"]] for c in d["cands"] if c["nr"] in pr}}
    import pandas as pd
    s = pd.read_csv(RAIZ / "dados_tse" / "votacao_secao_2026_RN.csv", sep=";", encoding="latin1", dtype=str,
                    usecols=["DS_CARGO", "NR_VOTAVEL", "QT_VOTOS"])
    s = s[s.DS_CARGO == "Senador"]; s["QT_VOTOS"] = s.QT_VOTOS.astype(int); s["NR_VOTAVEL"] = s.NR_VOTAVEL.astype(int)
    t = s.groupby("NR_VOTAVEL").QT_VOTOS.sum()
    validos = int(t.drop([95, 96], errors="ignore").sum())
    ps = {200: "styvenson", 131: "samanda", 555: "zenaide", 222: "helio", 123: "rafael", 500: "sandro", 161: "luciana", 166: "rosalia"}
    res["sen1"] = {"v": validos, "votos": {k: int(t.get(n, 0)) for n, k in ps.items()}, "vagas": 2}
    return res


def main():
    p1 = blocos(ler(DP / "pesquisas_1turno.csv"), COL1, [("gov1", "Governador"), ("sen1", "Senador")])
    p2 = blocos(ler(DP / "pesquisas_2turno.csv"), COL2, [("gov2", None)])
    polls = sorted(p1 + p2, key=lambda p: (p["c"], p["d"]))
    out = {"fonte": "Planilha PESQUISAS RN 2026 (Google Sheets), abas Completa Gov e Sen e Governo 2 turno",
           "eleicao": {"gov1": "2026-10-04", "sen1": "2026-10-04", "gov2": "2026-10-25"},
           "principais": PRINCIPAIS, "nomes": NOMES, "concorreu": sorted(CONCORREU),
           "resultados": resultados(), "pesquisas": polls}
    (DOCS / "pesquisas.js").write_text("window.PESQ=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    for c in ("gov1", "sen1", "gov2"):
        ps = [p for p in polls if p["c"] == c]
        print(f"{c}: {len(ps)} pesquisas, de {ps[0]['d']} a {ps[-1]['d']}; com candidatos fora da disputa >5%: "
              f"{sum(1 for p in ps if p['fora'] > 5)}", file=sys.stderr)


if __name__ == "__main__":
    main()
