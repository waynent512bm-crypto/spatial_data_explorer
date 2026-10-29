# Spatial Data Explorer — MVP 規劃

本文件定義第一版可用產品（MVP）的範圍、架構與開發階段。目前僅為規劃，尚未開始實作。

## 1. 目標

一個本地執行的互動式 spatial omics 資料瀏覽器，用於檢視**已完成 clustering 與 cell type annotation** 的資料，可以：

- 在組織空間中把每個細胞畫成**多邊形**（cell boundary），依 metadata（例如 cell type）著色
- 同時檢視 **UMAP**，兩個視圖連動
- 用滑鼠**圈選細胞**
- 對圈選的細胞做 **differential gene expression（DE）分析**
- **點選基因**，依表現量為細胞上色

本工具**不做**前處理、QC、clustering 或 annotation，這些都在分析 notebook 中完成；explorer 只負責讀取結果並互動檢視。

## 2. 支援平台與輸入格式

每個資料集由兩部分組成：

1. **`.h5ad`（必要）**：已 cluster、已 annotate 的 AnnData，需含：
   - `obsm["spatial"]`：細胞中心點座標（微米）
   - `obsm["X_umap"]`：UMAP 座標
   - `obs` 中已有的 cluster / cell type 欄位（**不需要另外新增或改名**，程式會自動偵測，見下方「Cell type 欄位自動偵測」）
   - 表現矩陣：log-normalized 值（`X` 或某個 `layers`，啟動時指定）
2. **細胞邊界檔（建議）**：用來畫多邊形。

| 平台 | 細胞邊界檔 | 格式 | 座標單位 |
|---|---|---|---|
| 10x Xenium | `cell_boundaries.parquet` | 每列一個頂點：`cell_id`, `vertex_x`, `vertex_y` | 微米 |
| Vizgen MERSCOPE | `cell_boundaries.parquet`（較新版本） | 每列一個細胞：`EntityID`, `ZIndex`, `Geometry`（WKB 多邊形） | 微米（待用實際檔案確認） |
| NanoString CosMx | `*-polygons.csv` | 每列一個頂點：`fov`, `cellID`, `x_global_px`, `y_global_px` | 像素，需乘上 pixel size 換算成微米（待確認各版本數值） |

### Cell type 欄位自動偵測

使用者不需要把 annotation 欄位改成固定名稱，程式啟動時從 `obs` 自動挑出最可能的 cell type 欄位作為預設著色：

1. 候選欄位：類別型（`category` / 字串）且類別數介於 2 到 200 之間的欄位。
2. 依欄位名稱評分（不分大小寫，底線、空白、連字號視為相同），優先順序：
   - 名稱含 `cell_type`、`celltype`、`cell_annotation`、`annotation`、`cell_label`、`predicted_label`、`majority_voting` 等
   - 名稱含 `type`、`label`、`annot`、`class`
   - cluster 欄位：`leiden`、`louvain`、`cluster`、`seurat_clusters`
3. 同分時，偏好類別名稱是文字（例如 `T cell`）而非純數字（例如 `0`、`1`）的欄位，因為純數字通常是未命名的 cluster。
4. 偵測結果在介面上顯示（例如「著色依據：`cell_type`（自動偵測）」），使用者可從下拉選單改選任何其他 `obs` 欄位。
5. 都找不到時，退回第一個類別型欄位；連類別型欄位都沒有時，以單一顏色顯示並提示。

### 未註釋細胞

以下細胞一律以**灰色**顯示，並在圖例中列為「Unannotated」：

- cell type 值為缺值（`NaN`），或為 `Unassigned`、`Unknown`、`Unannotated`、`NA`、`none`、空字串等（不分大小寫）
- 出現在細胞邊界檔、但不在 `.h5ad` 中的細胞（例如 QC 時被過濾掉的細胞）：畫成灰色多邊形保持組織外觀完整，但沒有表現量資料，不能被圈選，也不會進入 DE

### 需要處理的細節

- **細胞 ID 對應**：多邊形檔的細胞 ID 必須能對到 `.h5ad` 的 `obs_names`。各平台 ID 格式不同（例如 CosMx 需組合 `fov` + `cellID`），由各平台的 reader 負責轉換；對不上的細胞要在啟動時回報數量（只在邊界檔中的細胞依「未註釋細胞」規則顯示為灰色；只在 `.h5ad` 中、沒有多邊形的細胞以中心點畫出）。
- **座標系一致**：多邊形與 `obsm["spatial"]` 必須在同一座標系，否則多邊形會和中心點錯位。啟動時抽樣檢查中心點是否落在對應多邊形內。
- **MERSCOPE 多 z 層**：每個細胞在不同 `ZIndex` 各有一個多邊形，MVP 只取單一 z 層（預設中間層）。
- **沒有邊界檔時**：退回以中心點畫圓點，其他功能照常運作（例如舊的 MERFISH 匯出資料只有兩個 CSV，沒有邊界檔）。
- **多邊形預處理**：第一次載入時把多邊形轉成扁平的二進位格式（頂點陣列 + 每個細胞的起始 offset）並快取，之後開啟不必重新解析 parquet / csv。

## 3. MVP 功能範圍

| 功能 | 說明 |
|---|---|
| Spatial 視圖 | 每個細胞畫成多邊形，依類別欄位（cell type、cluster）、數值欄位（QC 指標）或基因表現量著色；縮小到看不清多邊形時自動改畫中心點，維持流暢 |
| UMAP 視圖 | 散佈圖，著色方式與 spatial 視圖同步 |
| 雙視圖連動 | 在任一視圖選取的細胞，另一視圖同步標示 |
| Lasso 圈選 | 滑鼠自由畫圈選取細胞（以中心點判斷是否在圈內）；可存成多個群組（Group A、Group B…），可命名、刪除 |
| DE 分析 | Group A vs. Group B，或 Group A vs. 其餘所有細胞；結果以表格（gene、logFC、p-adj）與 volcano plot 呈現 |
| 基因選取 | 搜尋框（自動完成）選基因；點 DE 表格中的基因即可依該基因上色 |
| 圖例 | 類別欄位可點選顯示／隱藏個別類別；未註釋細胞固定為灰色；數值欄位顯示色條 |

### 不在 MVP 範圍內（之後再做）

- 多樣本切換與比較
- 組織影像底圖（DAPI / H&E）、轉錄本（transcript）點位
- 蛋白質等第二模態的專屬檢視與 DE（例如 Xenium protein panel；蛋白質的正規化方式之後再決定）
- Dot plot / violin plot、多基因同時檢視
- 匯出圈選結果與 DE 結果
- 網頁直接上傳檔案（MVP 由啟動時指定檔案路徑）
- 多使用者、登入、雲端部署
- Pseudobulk DE

## 4. 已確定的決策

| 項目 | 決定 |
|---|---|
| 部署 | 本地執行：後端與前端都在自己電腦上，瀏覽器開 `localhost` |
| 使用者 | 單人 |
| 輸入資料 | 已 cluster、已 annotate 的 `.h5ad` + 平台原始的細胞邊界檔 |
| 支援平台 | Xenium、MERSCOPE、CosMx |
| DE 方法 | `scanpy.tl.rank_genes_groups`，預設 `method="wilcoxon"`，使用 log-normalized 表現量；**不使用 pseudobulk** |
| 前端技術 | React + TypeScript（開發者熟悉） |

### DE 實作方式

- 把圈選的群組寫成暫時的 `obs` 類別欄位（`A` / `B` / `rest`），對該欄位跑 `rank_genes_groups(groups=["A"], reference="B" 或 "rest")`，結果用 `sc.get.rank_genes_groups_df` 取出。
- 只對被選到的細胞子集計算，避免每次複製整個 AnnData。
- 群組細胞數太少（例如 < 10）時，提示結果不可靠。
- **p 值膨脹警語（必須保留）**：這是 cell-level 的檢定，每個細胞都被當成獨立樣本，但同一組織、同一樣本的細胞彼此並不獨立，因此 p 值會嚴重偏小（膨脹）。結果適合探索與挑選候選基因，不適合當作最終的統計結論。此警語要**常駐顯示在 DE 結果面板上**，不能只寫在文件中。

## 5. 架構

```
┌──────────────────── 瀏覽器 (localhost) ─────────────────┐
│ React + TypeScript (Vite)                               │
│  ├─ deck.gl (WebGL)                                     │
│  │   ├─ Spatial：細胞多邊形（縮小時改為中心點）           │
│  │   └─ UMAP：散佈圖                                    │
│  ├─ Lasso 繪製 → 判斷哪些細胞在圈內（Web Worker）        │
│  └─ DE 表格 + volcano plot                              │
└───────────────┬─────────────────────────────────────────┘
                │ HTTP（座標、多邊形、表現量以二進位陣列傳輸）
┌───────────────▼─────────────────────────────────────────┐
│ Python 後端：FastAPI                                     │
│  ├─ anndata 讀取 .h5ad                                   │
│  ├─ 平台 reader：Xenium / MERSCOPE / CosMx 細胞邊界檔     │
│  │   → 轉成統一的扁平多邊形格式並快取                     │
│  ├─ API：metadata / 座標 / 多邊形 / 基因表現 / DE         │
│  └─ DE：scanpy.tl.rank_genes_groups                      │
└─────────────────────────────────────────────────────────┘
```

### 選擇理由

- **本地瀏覽器介面**：前端在瀏覽器執行，Windows 與 Mac 行為一致，不需要另外打包桌面程式。
- **Python 後端**：直接沿用 scanpy / anndata，DE 結果與分析 notebook 一致。
- **deck.gl**：以 GPU 繪製，可處理數十萬個細胞多邊形；多邊形用二進位 attribute 直接餵給 `SolidPolygonLayer` / `PolygonLayer`，避免建立數十萬個 JavaScript 物件。
- **二進位傳輸**：座標、多邊形頂點與表現量用 `Float32Array` / `Uint32Array` 傳送，避免 JSON 序列化數十 MB 的資料。

### 考慮過的替代方案

- **Dash / Plotly、Streamlit**：純 Python、上手快，但大資料量下多邊形繪製與 lasso 圈選延遲明顯，客製化介面較受限。
- **Vitessce**：現成的開源 spatial viewer，可嵌入使用；缺點是 lasso 圈選與 DE 的整合流程較難照自己的需求設計。

## 6. 後端 API（草案）

| Endpoint | 回傳 |
|---|---|
| `GET /api/dataset` | 平台、細胞數、基因數、可用的 `obs` 欄位（類別／數值）、embedding 名稱、是否有多邊形 |
| `GET /api/embedding/{name}` | 該 embedding（`spatial`、`umap`）的座標，二進位 |
| `GET /api/polygons` | 所有細胞的多邊形：頂點陣列 + 每個細胞的起始 offset，二進位，順序與 `obs` 一致 |
| `GET /api/obs/{column}` | 某個 `obs` 欄位的值（類別欄位附類別清單與預設顏色） |
| `GET /api/genes?q=` | 基因名稱搜尋（自動完成） |
| `GET /api/expression/{gene}` | 該基因在所有細胞的表現量，二進位 |
| `POST /api/de` | 輸入群組 A 的細胞 index，以及群組 B 的細胞 index 或 `"rest"`；回傳 DE 結果表 |

## 7. 開發階段

每個階段完成後各自 commit 並 push。

| 階段 | 目標 | 完成標準 |
|---|---|---|
| 0. 專案骨架 | 建立 `frontend/`、`backend/` 結構、`.gitignore`（資料檔、`.h5ad`、`.parquet`、快取不進 git）、一行指令啟動 | 開啟網頁顯示「已連線到後端」 |
| 1. 資料 API | 讀取 `.h5ad`，提供 metadata、座標、基因表現 | API 回傳正確的細胞數、基因清單與 `obs` 欄位 |
| 2. 雙視圖（點） | Spatial + UMAP 散佈圖，依自動偵測的 cell type 欄位上色，未註釋細胞為灰色 | 自動選中測試資料的 annotation 欄位；縮放流暢，著色與 notebook 圖一致 |
| 3. 細胞多邊形 | Xenium reader + 多邊形快取 + spatial 視圖畫多邊形，縮小時改畫中心點 | 放大後看得到每個細胞的形狀且依 cell type 著色；中心點都落在多邊形內 |
| 4. 基因上色 | 搜尋基因、依表現量為多邊形與 UMAP 點上色、顯示色條 | 選擇已知 marker 基因時，對應 cell type 的區域亮起 |
| 5. Lasso 圈選 | 雙視圖連動選取、群組管理 | 在 UMAP 圈一群，spatial 圖同步標示同一批細胞 |
| 6. DE 分析 | A vs. B / A vs. rest、表格 + volcano plot、點基因上色、p 值膨脹警語 | 結果與直接在 notebook 跑 `rank_genes_groups` 一致；警語常駐顯示 |
| 7. 其他平台 | MERSCOPE、CosMx 的細胞邊界 reader | 各用一份實際資料確認多邊形與中心點對齊（需等測試資料補上） |

階段 0–7 完成即為 MVP。先以 Xenium 完成整條流程，再補其他平台的 reader；階段 7 要等 MERSCOPE、CosMx 測試資料到位才能開始。

## 8. 測試資料

**主要測試資料（Xenium）**

- `.h5ad`：`/Volumes/Extreme SSD/2026_生物資訊學工作坊/Xenium_V1_Human_Kidney_FFPE_Protein_updated_outs/analysis_out/xenium_rcc_annotated.h5ad`（已 cluster、已 annotate）
- 細胞邊界：同一個 Xenium output 資料夾中的 `cell_boundaries.parquet`
- 上述為 macOS 路徑；在 Windows 上為外接硬碟的磁碟代號（例如 `E:\2026_生物資訊學工作坊\...`）。資料路徑由啟動參數或設定檔指定，不寫死在程式中。

開始實作前要先確認的事：

- 自動偵測是否選中正確的 annotation 欄位，以及其中用來表示未註釋的值（例如 `Unassigned`）是否在灰色規則內
- 表現量在 `X` 還是某個 `layers`，是否已 log-normalize
- `obs_names` 是否就是 Xenium 的 `cell_id`（可直接對到 `cell_boundaries.parquet`）
- 是否經過 QC 過濾（多邊形檔中會有 `.h5ad` 沒有的細胞，需略過）
- 這份資料含 protein panel，確認蛋白質是放在另一個 AnnData、`obsm` 還是與基因混在 `var` 中，避免被當成基因做 DE

**其他測試資料（後續補上）**

- MERSCOPE：待補一份含 `cell_boundaries.parquet` 的已 annotate 資料（現有的 MERFISH 子宮癌資料沒有邊界檔，只能測試「沒有邊界檔時退回畫點」）
- CosMx：待補一份含 `*-polygons.csv` 的已 annotate 資料

## 9. 待確認事項

- 「Nanaotream」是否指 NanoString CosMx（本文件暫以 CosMx 規劃）
- 是否會載入全轉錄體（2 萬以上基因）或數百萬細胞的資料
- DE 是否需要 t-test 等較快的方法作為選項
- 蛋白質資料的正規化方式（例如 arcsinh、CLR）
- MERSCOPE、CosMx 測試資料的來源
