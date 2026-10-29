import numpy as np
import pandas as pd

from sde.annotation import detect_celltype_column, is_unannotated


def obs(**cols):
    n = len(next(iter(cols.values())))
    return pd.DataFrame(cols, index=[f"c{i}" for i in range(n)])


def test_prefers_annotation_name_over_cluster():
    df = obs(leiden=pd.Categorical(["0", "1", "2"] * 10),
             CellType=pd.Categorical(["T", "B", "Tumor"] * 10))
    assert detect_celltype_column(df).column == "CellType"


def test_name_variants_are_normalized():
    for name in ["cell type", "Cell-Type", "cell.type", "celltype"]:
        df = obs(sample=["s1", "s2"] * 5, **{name: ["T", "B"] * 5})
        assert detect_celltype_column(df).column == name


def test_text_labels_win_ties_over_numeric():
    df = obs(cluster_id=pd.Categorical(["0", "1"] * 10),
             cluster_name=pd.Categorical(["T cell", "Tumor"] * 10))
    assert detect_celltype_column(df).column == "cluster_name"


def test_cluster_used_when_no_annotation():
    df = obs(sample=["a", "b"] * 10, leiden=pd.Categorical(["0", "1"] * 10),
             n_genes=np.arange(20))
    assert detect_celltype_column(df).column == "leiden"


def test_ignores_id_like_and_numeric_columns():
    df = obs(barcode=[f"bc{i}" for i in range(300)], n_genes=np.arange(300))
    assert detect_celltype_column(df).column is None


def test_falls_back_to_first_categorical():
    df = obs(n_genes=np.arange(10), batch=["x", "y"] * 5, region=["r1", "r2"] * 5)
    d = detect_celltype_column(df)
    assert d.column == "batch" and "first categorical" in d.reason


def test_unannotated_placeholders():
    s = pd.Series(["T cell", "Unassigned", "unknown", None, "  NA ", "", "Tumor", np.nan])
    assert is_unannotated(s).tolist() == [False, True, True, True, True, True, False, True]
