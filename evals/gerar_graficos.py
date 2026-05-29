"""
Gera os gráficos dos resultados dos evals.

Roda com:  python -m evals.gerar_graficos

Lê o evals/sprint2_results.json e produz dois gráficos PNG em docs/:
- acuracia_por_categoria.png: barras com o score médio por categoria.
- tempo_por_caso.png: tempo de resposta de cada caso.

A gente separou isso do runner de propósito: assim dá pra regerar os
gráficos sem ter que rodar a suite inteira de novo (que gasta API).
"""

import json

import matplotlib
matplotlib.use("Agg")  # backend sem tela, pra rodar no Colab/servidor
import matplotlib.pyplot as plt

from src.config import DIR_EVALS

DIR_DOCS = DIR_EVALS.parent / "docs"

# Paleta sóbria, combinando com o tema clínico.
COR_BARRA = "#2a7de1"
COR_DESTAQUE = "#e15a4a"


def gerar():
    with open(DIR_EVALS / "sprint2_results.json", encoding="utf-8") as f:
        rel = json.load(f)

    # --- Gráfico 1: acurácia por categoria ---
    categorias = list(rel["acuracia_por_categoria"].keys())
    scores = list(rel["acuracia_por_categoria"].values())

    fig, ax = plt.subplots(figsize=(7, 4))
    barras = ax.bar(categorias, scores, color=COR_BARRA)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score médio")
    ax.set_title("Acurácia por categoria de avaliação")
    for b, s in zip(barras, scores):
        ax.text(b.get_x() + b.get_width() / 2, s + 0.02, f"{s:.2f}", ha="center", fontsize=10)
    ax.axhline(rel["score_medio_geral"], color=COR_DESTAQUE, linestyle="--", linewidth=1)
    ax.text(len(categorias) - 0.5, rel["score_medio_geral"] + 0.02,
            f"média geral {rel['score_medio_geral']:.2f}", color=COR_DESTAQUE, ha="right", fontsize=9)
    plt.tight_layout()
    plt.savefig(DIR_DOCS / "acuracia_por_categoria.png", dpi=120)
    plt.close()

    # --- Gráfico 2: tempo de resposta por caso ---
    ids = [r["id"] for r in rel["resultados"]]
    tempos = [r["tempo_resposta_seg"] for r in rel["resultados"]]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(ids, tempos, color=COR_BARRA)
    ax.set_ylabel("Tempo (segundos)")
    ax.set_title("Tempo de resposta por caso de teste")
    ax.axhline(rel["tempo_medio_resposta_seg"], color=COR_DESTAQUE, linestyle="--", linewidth=1)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(DIR_DOCS / "tempo_por_caso.png", dpi=120)
    plt.close()

    print(f"Gráficos salvos em {DIR_DOCS}/")
    print("  - acuracia_por_categoria.png")
    print("  - tempo_por_caso.png")


if __name__ == "__main__":
    gerar()
