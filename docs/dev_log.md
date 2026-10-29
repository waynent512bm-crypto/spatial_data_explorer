# 開發紀錄

依時間順序記錄每次開發的內容與做出的決策。時間為台北時間（UTC+08:00）。

格式：每筆紀錄包含 **完成事項**、**決策**（含理由）、**待處理**。

---

## 2026-10-29（開發開始前）— 規劃階段

規劃討論的結論已寫入 [PLAN.md](PLAN.md)，此處摘要當時做出的決策：

- **範圍**：先做 MVP（PLAN.md 階段 0–7）。
- **部署**：本地執行，單人使用，瀏覽器開 `localhost`。
- **輸入**：已 cluster、已 annotate 的 `.h5ad` + 平台原始細胞邊界檔；explorer 不做前處理、QC、clustering。
- **支援平台**：Xenium、MERSCOPE、CosMx（使用者寫「Nanaotream」，暫以 NanoString CosMx 規劃，待確認）。
- **細胞繪製**：spatial 視圖以細胞邊界多邊形繪製，依 metadata 著色。
- **Cell type 欄位**：不要求使用者新增或改名，程式自動偵測。
- **未註釋細胞**：灰色顯示；包含只在邊界檔、不在 `.h5ad` 的細胞（不可圈選、不進 DE）。
- **DE**：`scanpy.tl.rank_genes_groups`（Wilcoxon），不用 pseudobulk；p 值膨脹警語常駐顯示於 DE 面板。
- **前端**：React + TypeScript（使用者熟悉）。
- **延後決定**：蛋白質正規化方式；MERSCOPE、CosMx 測試資料後續補上。

---

## 2026-10-29 09:44 — 階段 0（專案骨架）+ 階段 1（資料 API）

### 完成事項

- 專案結構：`backend/`（FastAPI，套件名稱 `sde`）、`frontend/`（React + TypeScript + Vite）、`scripts/`、`docs/`。
- `.gitignore`：排除 `data/`、`*.h5ad`、`*.parquet`、快取、虛擬環境、`node_modules`。
- 後端 API（階段 1）：
  - `GET /api/health`、`GET /api/dataset`
  - `GET /api/embedding/{name}`（`spatial`、`umap`，二進位 float32）
  - `GET /api/obs/{column}`（metadata）+ `GET /api/obs/{column}/values`（二進位）
  - `GET /api/genes?q=`、`GET /api/expression/{gene}`（二進位 float32）
- Cell type 欄位自動偵測與未註釋判定（`backend/src/sde/annotation.py`），規則依 PLAN.md §2。
- 合成示範資料產生器 `python -m sde demo`：模擬已 annotate 的 Xenium 輸出（約 2 萬細胞、48 基因、5% `Unassigned`、Xenium 格式的 `cell_boundaries.parquet`，且邊界檔多出約 3% 不在 `.h5ad` 的細胞，模擬 QC 過濾）。
- 一行指令啟動：`scripts/dev.ps1`（Windows）、`scripts/dev.sh`（macOS / Linux）。
- 前端骨架：連線後顯示「Connected to backend」、資料集摘要與自動偵測的著色欄位。
- 測試：14 個後端測試全部通過（`pytest`）；實際以 uvicorn 讀取磁碟上的示範 `.h5ad` 驗證各 endpoint。

### 決策

| 決策 | 理由 |
|---|---|
| 先用合成示範資料開發 | 測試資料在外接 SSD 上，目前未連接；合成資料也讓測試不依賴大型檔案，可放進 CI |
| `obs` 拆成兩個 endpoint：`/api/obs/{col}`（JSON）與 `/api/obs/{col}/values`（二進位） | 類別名稱可能含中文等非 ASCII 字元，不適合放在 HTTP header；值的陣列用二進位傳輸較省 |
| 類別欄位以 int32 code 傳送，未註釋細胞的 code 為 `-1` | 前端只要判斷 `-1` 就畫灰色；未註釋標籤不列在 `categories` 中 |
| 類別順序保留 `.h5ad` 中 `Categorical` 的原始順序 | 與 notebook 中 scanpy 圖例順序一致；也一併回傳 `uns["{col}_colors"]`，讓顏色與 notebook 相同 |
| 稀疏表現矩陣在載入時轉一份 CSC | 前端每次取一個基因的整欄，CSC 取欄比 CSR 快很多；500 基因 panel 的額外記憶體可接受 |
| 二進位陣列一律 little-endian，以 `X-Dtype`、`X-Shape` header 描述 | 前端直接建立 `Float32Array` / `Int32Array`，不需解析 |
| 前端開發時以 Vite proxy 轉發 `/api` | 同源請求，後端不需要設定 CORS |
| 後端 Python 依賴裝在 `backend/.venv` | 不影響系統的 Python 環境 |
| 前端套件版本固定（React 18.3.1、Vite 5.4.11、TypeScript 5.6.3） | 可重現；deck.gl 等繪圖套件在階段 2 再加入 |

### 待處理

- **前端尚未實際執行**：這台電腦沒有安裝 Node.js，前端檔案已寫好但還沒 `npm install`、型別檢查與瀏覽器驗證；階段 0 的完成標準（網頁顯示「已連線到後端」）要等安裝 Node.js 後確認。
- 外接 SSD 連接後，用 `xenium_rcc_annotated.h5ad` 確認 PLAN.md §8 的五個檢查項目。
- 下一步：階段 2（Spatial + UMAP 雙視圖，deck.gl）。

---

## 2026-10-29 — 階段 0 驗證完成（前端）

### 完成事項

- 使用者安裝 Node.js v26.13.0、npm 11.20.0（Windows installer）。
- `npm install`、`npm run typecheck`、`npm run build` 皆成功；`package-lock.json` 進 git。
- 同時啟動後端（port 8000）與 Vite（port 5173），確認：頁面可載入、`/api/health`、`/api/dataset` 與二進位的 `/api/embedding/umap` 都能經由 Vite proxy 取得。

### 決策

| 決策 | 理由 |
|---|---|
| 不用 Docker 跑 Node.js，改裝原生 Windows installer | 這台電腦沒有 Docker；容器內的 Vite 要連到主機上的後端需額外網路設定，Windows 資料夾掛載進容器時 hot reload 也較慢或失效 |
| 不核准 esbuild 的 postinstall script | npm 11 預設擋下未核准的 install script；esbuild 的平台 binary（`@esbuild/win32-x64`）已由 optional dependency 安裝，`vite build` 正常，不需要額外核准 |

### 待處理

- 瀏覽器畫面由使用者目視確認（開發環境沒有瀏覽器可截圖）。

---

## 2026-10-29 — 階段 2（Spatial + UMAP 雙視圖）

### 完成事項

- 加入 deck.gl 9.1.15（`@deck.gl/core`、`layers`、`react`、`widgets`）。
- `ScatterView`：`OrthographicView` + `ScatterplotLayer`，座標與顏色以二進位 attribute 直接傳給 GPU；自動縮放到資料範圍，提供「Reset view」。
- 著色：預設使用自動偵測的 cell type 欄位，側欄下拉選單可改選任何 `obs` 欄位；類別欄位用 `.h5ad` 中的 `uns["{col}_colors"]`，沒有時用 scanpy 預設 20 色，超過 20 類用黃金角色相產生；數值欄位用 viridis 色條。
- 未註釋細胞（code `-1`）與數值缺值固定為灰色；圖例列出「Unannotated」與細胞數。
- 圖例可點選個別類別顯示／隱藏，並有 Show all / Hide all。
- 後端效能：類別欄位改為「每個類別標籤判斷一次再重新對應 code」，749,950 細胞時第一次讀取 `cell_type` 從 0.77 秒降到 0.04 秒；同時移除沒有任何細胞的類別，避免圖例出現 0 筆的項目。新增 2 個測試，共 16 個測試通過。
- 以 749,950 細胞的合成資料（`python -m sde demo --n-cells 750000`）測試：經 Vite proxy 取得 spatial / UMAP 座標（各 6 MB）、類別 code、單一基因表現量，每個請求都在 0.05 秒內完成。

### 決策

| 決策 | 理由 |
|---|---|
| deck.gl 固定 9.1.15，並明確安裝 `@deck.gl/widgets@9.1.15` | `@deck.gl/react@9.1` 的 peer dependency 會拉到 widgets 9.4，與 core 9.1 衝突；全部固定同一版本 |
| 位置在前端補成 3 維（z = 0）再交給 deck.gl | deck.gl 的 shader 使用 3 維位置；每個 embedding 只轉換一次，750k 細胞約多 9 MB，可接受 |
| Spatial 視圖 y 軸朝下（`flipY`），UMAP y 軸朝上 | 組織座標是影像座標系（與 notebook 中 `invert_yaxis()` 一致）；UMAP 依一般數學座標 |
| Spatial 點半徑以微米計（5 µm），UMAP 點半徑以像素計（1.5 px），最小 0.6 px | Spatial 放大時點的大小接近真實細胞；UMAP 沒有物理尺度 |
| 隱藏類別用 alpha = 0，而不是重新篩選資料 | 只要重算顏色 buffer，位置 buffer 不變，切換即時 |
| 暫不處理 bundle 大小警告（約 880 kB） | 本地執行，不經網路下載；之後如需要再做 code splitting |
| 不在 deck.gl 開啟 picking | 階段 2 不需要滑鼠點選細胞；picking 會讓 GPU 多畫一次，留到需要時再開 |

### 待處理

- **畫面尚未目視確認**：需要使用者在瀏覽器開 http://localhost:5173 確認兩個視圖、著色、圖例與 750k 細胞縮放是否流暢（PLAN.md 階段 2 的完成標準）。
- 下一步：階段 3（Xenium 細胞多邊形）。
