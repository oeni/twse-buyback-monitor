# 台股庫藏股監控

每天從公開資訊觀測站（MOPS）取得上市、上櫃公司的庫藏股申報，整理成
Markdown 日報，並追蹤既有案件的執行進度。

[English](README.md)

## 快速開始

```bash
git clone https://github.com/oeni/twse-buyback-monitor.git
cd twse-buyback-monitor
python -m pip install -e .
python -m twse_buyback
```

日常使用不需要加參數。每次成功執行後，檔案會寫進 repo 的 `output/`：

```text
output/
├── 2026-08-12.md
├── snapshot_latest.csv
├── changes_log.csv
└── run.log
```

當天沒有新公告或執行進度異動，仍會建立該日的 Markdown。若抓取失敗，
則不建立也不覆寫日報，避免把「資料沒抓到」誤認成「今天沒消息」。

第一次執行只建立比較基準，不會把站上既有案件列為今日新公告。

## 常用選項

```bash
# 同時在終端機印出日報
python -m twse_buyback --print-digest

# 改用其他輸出位置
python -m twse_buyback --output-dir D:\buyback-output

# 資料可解析但出現異常時，讓排程收到非零結束碼
python -m twse_buyback --strict

# 查看全部設定
python -m twse_buyback --help
```

## 輸出檔案

| 檔案 | 內容 |
|---|---|
| `YYYY-MM-DD.md` | 當日新公告與執行進度異動。 |
| `snapshot_latest.csv` | 最近一次完整資料，作為下次比較基準。 |
| `changes_log.csv` | 只追加的異動紀錄，含新增、進度、回補與消失案件。 |
| `run.log` | 執行結果、重試與資料異常。 |

CSV 採 UTF-8 BOM，可直接用 Excel 開啟。

## 資料防護

MOPS 偶爾會回傳 HTTP 200，但表格內容並不完整。本工具會拒收下列結果：

- HTML 沒有正常結尾；
- 筆數相較上次完整資料大幅減少；
- 單次出現不合理的大量新案；
- 歷史案件從表格中消失。

拒收後會自動重試；全部失敗時保留原本的 snapshot。重新出現的舊案會記成
回補，不會列為今日新公告。背景與修正記錄見
[2026 年 8 月事故報告](docs/incident-2026-08-truncated-responses.md)。

本專案使用的是 MOPS 網站內部端點，不是正式公開 API；網站改版時可能需要
同步調整解析器。

## 當成 Python 函式庫使用

```python
from twse_buyback import Settings, run

result = run(Settings())

for case in result.announcements:
    print(case["code"], case["name"], case["planned_shares"])
```

需要自訂位置時，傳入 `Settings(data_dir=...)`。

## 開發

```bash
python -m unittest discover -s tests -t .
```

線上 MOPS 測試需明確開啟：

```bash
RUN_NETWORK_TESTS=1 python -m unittest tests.test_smoke_network
```

需要 Python 3.9 以上。執行期相依套件只有 `requests`。

## 授權

MIT
