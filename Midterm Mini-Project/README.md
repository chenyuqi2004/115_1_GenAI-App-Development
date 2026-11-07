# 職缺適配分析器

比對職缺描述與自己的技能簡述，整理出已符合、待補強和還需要確認的項目，再給出投遞建議。

- **App 網址：** 待填（尚未部署）
- **雲端驗收：** 未測
- **部署設定：** Repo `chenyuqi2004/115_1_GenAI-App-Development`、分支 `main`、Main file path `Midterm Mini-Project/app.py`

## 使用者與問題

使用者是準備投遞實習或工作的學生。逐條對照職缺和自己的經歷很花時間，也容易高估自己符合的程度，或忽略職缺根本沒寫清楚的地方。

這個工具只處理一個任務：依使用者貼上的兩段文字做比對。所有結果都只依這兩段文字，不依職稱或產業常識推測。

## 為什麼採用 Pydantic

輸出有五個欄位，其中四個是文字清單。用 `ProjectResult` 模型定義比手寫 JSON Schema 更好讀，SDK 會自動轉成 strict Schema，並用同一個模型驗證回應，不必再手寫一份欄位檢查。

## 安裝與啟動

需要 Python 3.14，在本資料夾執行：

```bash
# macOS／Linux
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r ../requirements.txt
python -m pip check
cp .env.example .env
python -m streamlit run app.py
```

```powershell
# Windows
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r ..\requirements.txt
python -m pip check
Copy-Item .env.example .env
python -m streamlit run app.py
```

套件清單放在 Repo 根目錄的 `requirements.txt`，不放在本資料夾。Streamlit Community Cloud 安裝入口同層的清單時，會把資料夾名稱中的空格拆開而安裝失敗（`Invalid requirement: 'Mini-Project/requirements.txt'`）；說明書第 3-1 節也允許放在 Repo 根目錄。

## 設定方式

| 設定 | 說明 |
|---|---|
| `OPENAI_API_KEY` | 必填才能啟用 API；本機放 `.env`，雲端放平台 Secrets |
| `OPENAI_MODEL` | 選填，預設 `gpt-5.4-mini` |

Secrets 優先於環境變數。雲端格式參考 `.streamlit/secrets.example.toml`。`.env` 和 `.streamlit/secrets.toml` 已被 `.gitignore` 排除，不可提交。

## 輸入與輸出欄位

**輸入：** 職缺描述、我的技能簡述。兩欄都必填，合計最多 6000 字元，超過時會提示縮短，不會默默截斷。

**輸出：**

| 欄位 | 型別 | 畫面標籤 | 用途 |
|---|---|---|---|
| `required_skills` | `list[str]` | 職缺要求 | 列出職缺明確提到的技能或條件 |
| `matched_skills` | `list[str]` | 我已符合 | 每項附上技能簡述中的依據，方便回查 |
| `skill_gaps` | `list[str]` | 待補強 | 決定投遞前要補什麼 |
| `missing_info` | `list[str]` | 還需要確認的資訊 | 列出影響判斷但沒有提供的資訊 |
| `application_advice` | `str` | 投遞建議 | 兩三句建議；資訊不足時明說無法判斷 |

所有欄位都必填，模型禁止多餘欄位；清單可以是空的，文字和清單項目不能全空白。

## 操作範例

測試資料放在 [sample_data/測試資料.md](sample_data/測試資料.md)，全部為虛構，並附上人工核對重點。

1. 保持 API 關閉，貼上案例 A 的兩段文字，按「開始分析」。畫面提示輸入檢查通過，沒有 AI 結果，0 次請求。
2. 勾選「啟用真實 API」，再按一次「開始分析」。畫面顯示當筆原文和五個欄位。
3. 對照原文逐欄核對；每項職缺要求都應出現在「我已符合」或「待補強」，數量不符時畫面會提醒。
4. 換成案例 B，確認沒有補造技能，投遞建議有說明無法判斷。

實際輸入與輸出記錄在[設計與驗收紀錄](第08週_課堂簡化版_專題設計與驗收紀錄.md)。

## 實測與未測項目

| 項目 | 狀態 |
|---|---|
| 輸入檢查、API 開關、結果保存與清除、錯誤分流 | 離線測試通過（2026-11-07，macOS／Python 3.14.10，模擬 HTTP） |
| App 在本機啟動 | 已確認（2026-11-07，只確認服務啟動，未以真人瀏覽器操作） |
| 真實 API：正常資料 | 未測 |
| 真實 API：資訊不足 | 未測 |
| 真人瀏覽器操作 | 未測 |
| Streamlit Community Cloud 部署 | 未測 |

離線測試不連線、不計費，只證明程式流程，不代表模型輸出的品質。重新執行：

```bash
python -X utf8 tests/test_app_offline.py
```

## 成本與限制

- **請求數：** API 預設關閉；開啟後每次有效提交最多 1 次請求，不自動重試。規劃正常與資訊不足各 1 次，共 2 次，額外重測另計，失敗也可能計費。
- **資料傳送：** `store=False` 仍會把內容傳到 OpenAI，請勿輸入個資或機密。
- **內容正確性：** 格式合格不代表內容正確，結果仍須對照原文核對。
- **分類檢查：** 程式只比對分類的數量，無法確認每項技能是否分類正確。
- **依據有限：** 技能簡述寫得越少，能判定符合的項目越少；結果不代表實際能力或錄取機會。
- **保存範圍：** 結果只保存在當次瀏覽階段，不會寫入檔案。

## AI 協助說明

Claude Code 協助改寫起點程式、撰寫離線測試與虛構測試資料、起草本 README 和驗收紀錄。

自己的修改與親自驗證事項：待填。
