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
