# Spatial Data Explorer

互動式 spatial omics 資料視覺化工具：讀取已 cluster、已 annotate 的 Xenium / MERSCOPE / CosMx 資料，在瀏覽器中檢視細胞空間分布與 UMAP、圈選細胞並做 differential expression 分析。

- 規劃：[docs/PLAN.md](docs/PLAN.md)
- 開發紀錄與決策：[docs/dev_log.md](docs/dev_log.md)

## 需求

- Python 3.10 以上
- Node.js 20 以上（含 npm）

## 啟動

第一次執行會自動建立 Python 虛擬環境、安裝前端套件；沒有指定資料時會產生一份合成的 Xenium 示範資料。

Windows（PowerShell）：

```powershell
.\scripts\dev.ps1                                              # 示範資料
.\scripts\dev.ps1 -H5ad E:\path\to\annotated.h5ad -Platform xenium
```

macOS / Linux：

```bash
./scripts/dev.sh                                               # 示範資料
./scripts/dev.sh /path/to/annotated.h5ad xenium
```

接著用瀏覽器開啟 http://localhost:5173 。

## 只啟動後端

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # macOS / Linux: .venv/bin/python
.venv/Scripts/python -m sde serve --h5ad PATH --platform xenium [--layer NAME]
.venv/Scripts/python -m pytest                      # 測試
```

## 專案結構

```
backend/    Python FastAPI 後端（套件名稱 sde）
frontend/   React + TypeScript 前端（Vite）
scripts/    開發用啟動腳本
docs/       規劃與開發紀錄
data/       本機資料（不進 git）
```

## 開發狀態

依 [docs/PLAN.md](docs/PLAN.md) 第 7 節的階段進行，目前進度見 [docs/dev_log.md](docs/dev_log.md)。
