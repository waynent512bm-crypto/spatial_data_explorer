"""Cell type column auto-detection and unannotated-label handling (docs/PLAN.md §2)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_CATEGORIES = 2
MAX_CATEGORIES = 200

# Name keywords, highest tier first. Matched against the normalized column name.
_TIER_KEYWORDS: list[tuple[int, tuple[str, ...]]] = [
    (3, ("cell_type", "celltype", "cell_annotation", "annotation", "cell_label",
         "predicted_label", "majority_voting")),
    (2, ("type", "label", "annot", "class")),
    (1, ("leiden", "louvain", "cluster", "seurat_clusters")),
]

# Values shown as gray "Unannotated" (compared case-insensitively, after stripping).
UNANNOTATED_LABELS = frozenset({
    "", "unassigned", "unknown", "unannotated", "na", "n/a", "nan", "none", "null",
})


@dataclass(frozen=True)
class Detection:
    column: str | None
    reason: str


def normalize_name(name: str) -> str:
    return re.sub(r"[\s_\-.]+", "_", str(name).strip().lower())


def name_tier(name: str) -> int:
    norm = normalize_name(name)
    for tier, keywords in _TIER_KEYWORDS:
        if any(k in norm for k in keywords):
            return tier
    return 0


def is_categorical_like(s: pd.Series) -> bool:
    if isinstance(s.dtype, pd.CategoricalDtype):
        n = len(s.cat.categories)
    elif pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
        n = s.nunique(dropna=True)
    else:
        return False
    return MIN_CATEGORIES <= n <= MAX_CATEGORIES


def text_fraction(s: pd.Series) -> float:
    """Fraction of category labels that are not purely numeric (e.g. 'T cell' vs '3')."""
    cats = s.cat.categories if isinstance(s.dtype, pd.CategoricalDtype) else s.dropna().unique()
    labels = [str(c).strip() for c in cats]
    if not labels:
        return 0.0
    numeric = sum(bool(re.fullmatch(r"-?\d+(\.\d+)?", lab)) for lab in labels)
    return 1.0 - numeric / len(labels)


def detect_celltype_column(obs: pd.DataFrame) -> Detection:
    candidates = [c for c in obs.columns if is_categorical_like(obs[c])]
    if not candidates:
        return Detection(None, "no categorical column found")

    # Sort key: name tier, then text-vs-numeric labels, then original column order.
    scored = [(name_tier(c), text_fraction(obs[c]), -i, c) for i, c in enumerate(candidates)]
    tier, _, _, best = max(scored)
    if tier == 0:
        return Detection(candidates[0], "no annotation-like name; first categorical column")
    return Detection(best, f"name match (tier {tier})")


def is_unannotated(values: pd.Series) -> np.ndarray:
    """Boolean mask of cells whose label is missing or an 'unassigned'-type placeholder."""
    missing = values.isna().to_numpy()
    as_text = values.astype("string").str.strip().str.lower()
    placeholder = as_text.isin(UNANNOTATED_LABELS).fillna(False).to_numpy(dtype=bool)
    return missing | placeholder
