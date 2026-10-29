# Spatial Data Explorer — MVP 規劃

本文件定義第一版可用產品（MVP）的範圍、架構與開發階段。目前僅為規劃，尚未開始實作。

## 1. 目標

一個跨平台（Windows / macOS / Linux）的互動式 spatial omics 資料瀏覽器，可以：

- 同時檢視細胞的**空間分布**與 **UMAP**
- 用滑鼠**圈選細胞**
- 對圈選的細胞做 **differential gene expression（DE）分析**
- **點選基因**，依表現量為細胞上色

## 2. MVP 功能範圍

| 功能 | 說明 |
|---|---|
| 雙視圖連動 | Spatial（組織座標）與 UMAP 兩張散佈圖並排，可縮放、平移；在一邊選取的細胞會同步顯示在另一邊 |
| 上色 | 依 cluster（`leiden`、`cell_type`、`domain` 等類別欄位）、QC 指標（`gene_counts`、`volume` 等數值欄位）或單一基因表現量上色，並顯示圖例／色條 |
| Lasso 圈選 | 滑鼠自由畫圈選取細胞；可存成多個群組（Group A、Group B…），可命名、刪除 |
| DE 分析 | Group A vs. Group B，或 Group A vs. 其餘所有細胞；結果以表格（gene、logFC、p-adj）與 volcano plot 呈現 |
| 基因選取 | 搜尋框（自動完成）選基因；點 DE 表格中的基因即可依該基因上色 |

### 不在 MVP 範圍內（之後再做）

- 多樣本切換與比較
- 細胞邊界多邊形、組織影像底圖
- Dot plot / violin plot、多基因同時檢視
- 匯出圈選結果與 DE 結果
- 網頁直接上傳檔案（MVP 由啟動時指定 `.h5ad` 路徑）
- 多使用者、登入、雲端部署

## 3. 預設決策

以下事項尚未正式討論，先採用預設值，之後可調整：

| 項目 | 預設 |
|---|---|
| 使用者 | 單人、本機執行（瀏覽器開 `localhost`） |
| 資料規模 | 以約 741k 細胞 × 500 基因（MERFISH 子宮癌資料）為基準；全轉錄體資料之後再優化 |
| 輸入格式 | `.h5ad`（AnnData），需已含 `obsm["spatial"]`、`obsm["X_umap"]` 與 cluster 欄位；其他平台資料先在 notebook 轉成 `.h5ad` |
| DE 方法 | Wilcoxon rank-sum（與分析 notebook 一致），使用 log-normalized 表現量，Benjamini–Hochberg 校正 |
| 前端技術 | React + TypeScript |

## 4. 架構

```
┌──────────── 瀏覽器（Windows / Mac / Linux）─────────────┐
│ React + TypeScript (Vite)                               │
│  ├─ deck.gl (WebGL)：繪製百萬等級的點                    │
│  ├─ Lasso 繪製 → 判斷哪些細胞在圈內（Web Worker）        │
│  └─ DE 表格 + volcano plot                              │
└───────────────┬─────────────────────────────────────────┘
                │ HTTP（座標與表現量以二進位陣列傳輸）
┌───────────────▼─────────────────────────────────────────┐
│ Python 後端：FastAPI                                     │
│  ├─ 以 anndata 讀取 .h5ad                                │
│  ├─ API：metadata / 座標 / 基因表現 / DE                 │
│  └─ DE：scanpy 或向量化 Wilcoxon                         │
└─────────────────────────────────────────────────────────┘
```

### 選擇理由

- **跨平台**：前端在瀏覽器執行，Windows 與 Mac 行為一致；之後可打包成桌面 app 或部署成網站。
- **Python 後端**：直接沿用 scanpy / anndata 生態系，DE 結果可與分析 notebook 互相驗證。
- **deck.gl**：741k 個點用 Plotly / Matplotlib 互動會明顯卡頓，deck.gl 以 GPU 繪製可流暢處理百萬等級的點。
- **二進位傳輸**：座標與表現量用 `Float32Array` 傳送，避免 JSON 序列化數十 MB 的資料。

### 考慮過的替代方案

- **Dash / Plotly、Streamlit**：純 Python、上手快，但大資料量下 lasso 圈選延遲明顯，客製化介面較受限。
- **Vitessce**：現成的開源 spatial viewer，可嵌入使用；缺點是 lasso 圈選與 DE 的整合流程較難照自己的需求設計。

## 5. 後端 API（草案）

| Endpoint | 回傳 |
|---|---|
| `GET /api/dataset` | 細胞數、基因數、可用的 `obs` 欄位（類別／數值）與 embedding 名稱 |
| `GET /api/embedding/{name}` | 該 embedding（`spatial`、`umap`）的座標，二進位 |
| `GET /api/obs/{column}` | 某個 `obs` 欄位的值（類別欄位附類別清單） |
| `GET /api/genes?q=` | 基因名稱搜尋（自動完成） |
| `GET /api/expression/{gene}` | 該基因在所有細胞的表現量，二進位 |
| `POST /api/de` | 輸入兩組細胞 index（或一組 + "rest"），回傳 DE 結果表 |

## 6. 開發階段

每個階段完成後各自 commit 並 push。

| 階段 | 目標 | 完成標準 |
|---|---|---|
| 0. 專案骨架 | 建立 `frontend/`、`backend/` 結構、`.gitignore`（資料檔與 `.h5ad` 不進 git）、一行指令啟動 | 開啟網頁顯示「已連線到後端」 |
| 1. 資料 API | 後端讀取 `.h5ad`，提供 metadata、座標、基因表現 | API 回傳正確的細胞數與基因清單 |
| 2. 雙視圖 | Spatial + UMAP 散佈圖，依 cluster 上色 | 741k 點縮放流暢 |
| 3. 基因上色 | 搜尋基因、依表現量上色、顯示色條 | 選 `CD3E` 能看到 T 細胞區域亮起 |
| 4. Lasso 圈選 | 雙視圖連動選取、群組管理 | 在 UMAP 圈一群，spatial 圖同步標示同一批細胞 |
| 5. DE 分析 | A vs. B / A vs. rest、表格 + volcano plot、點基因上色 | 結果與 notebook 中 `rank_genes_groups` 一致 |

階段 0–5 完成即為 MVP。

## 7. 測試資料

- `MERFISH_UterineCancer_analysis_V1.ipynb` 輸出的 `rna_processed.h5ad`（目前為 50,000 細胞的開發用子抽樣；含 `X_umap`、`leiden`、`spatial`）
- 驗證完畢後再用全部約 741,749 個細胞測試效能

## 8. 待確認事項

- 是否需要給工作坊學員或其他人透過網站使用（影響部署與登入設計）
- 是否會載入全轉錄體（2 萬以上基因）或數百萬細胞的資料
- DE 是否需要 t-test 等較快的替代方法作為選項
