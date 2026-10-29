import numpy as np


def decode(resp):
    shape = tuple(int(x) for x in resp.headers["X-Shape"].split(","))
    return np.frombuffer(resp.content, dtype=np.dtype(resp.headers["X-Dtype"]).newbyteorder("<")).reshape(shape)


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_dataset_summary(client, demo_adata):
    s = client.get("/api/dataset").json()
    assert s["n_cells"] == demo_adata.n_obs
    assert s["n_genes"] == demo_adata.n_vars
    assert s["default_color_column"] == "cell_type"
    assert set(s["embeddings"]) >= {"spatial", "umap"}
    kinds = {c["name"]: c["kind"] for c in s["obs_columns"]}
    assert kinds["cell_type"] == "categorical"
    assert kinds["transcript_counts"] == "numeric"


def test_embedding_binary(client, demo_adata):
    for name, key in [("spatial", "spatial"), ("umap", "X_umap")]:
        r = client.get(f"/api/embedding/{name}")
        assert r.status_code == 200
        np.testing.assert_allclose(decode(r), demo_adata.obsm[key][:, :2], rtol=1e-6)
    assert client.get("/api/embedding/nope").status_code == 404


def test_categorical_obs_marks_unannotated(client, demo_adata):
    meta = client.get("/api/obs/cell_type").json()
    assert "Unassigned" not in meta["categories"]
    codes = decode(client.get("/api/obs/cell_type/values"))
    labels = demo_adata.obs["cell_type"].astype(str).to_numpy()
    assert meta["unannotated_count"] == (labels == "Unassigned").sum() == (codes == -1).sum()
    annotated = codes >= 0
    decoded = np.array(meta["categories"])[codes[annotated]]
    assert (decoded == labels[annotated]).all()


def test_numeric_obs(client, demo_adata):
    meta = client.get("/api/obs/cell_area").json()
    assert meta["kind"] == "numeric" and meta["min"] <= meta["max"]
    values = decode(client.get("/api/obs/cell_area/values"))
    np.testing.assert_allclose(values, demo_adata.obs["cell_area"].to_numpy(), rtol=1e-6)


def test_gene_search_prefix_first(client):
    genes = client.get("/api/genes", params={"q": "cd"}).json()["genes"]
    assert genes and all("cd" in g.lower() for g in genes)
    starts = [g.lower().startswith("cd") for g in genes]
    assert starts == sorted(starts, reverse=True)


def test_expression(client, demo_adata):
    r = client.get("/api/expression/CD3E")
    expected = demo_adata[:, "CD3E"].X.toarray().ravel()
    np.testing.assert_allclose(decode(r), expected, rtol=1e-6)
    assert client.get("/api/expression/NOT_A_GENE").status_code == 404
