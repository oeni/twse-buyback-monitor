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

## 日報長什麼樣

有事的一天，`output/2026-08-11.md` 會像這樣（真實申報案；日期為民國紀年，115 年＝2026 年）：

```markdown
# 2026-08-11 庫藏股

## 新公告（4）

- **5292 華懋**（上市）｜決議 115/08/10｜預定 3,000,000 股｜價格 121.00–275.00｜期間 115/08/11～115/10/08｜目的 轉讓股份予員工
- **8436 大江**（上櫃）｜決議 115/08/10｜預定 500,000 股｜價格 88.00–173.00｜期間 115/08/11～115/10/09｜目的 轉讓股份予員工

## 執行進度（2）

- **9921 巨大**｜決議 115/05/08｜執行狀態：N → Y；已買回股數：空白 → 4,000,000；買回比例：空白 → 100.00；已買回金額：空白 → 287,003,263
```

[`examples/`](examples/) 收錄連續五個監控日的完整產出——基準日、有事的一天、
安靜的一天、兩個資料異常日——以及累積出的異動紀錄與執行 log。這些檔案由
`examples/regenerate.py` 把 2026 年 8 月的真實申報資料重播過真實管線生成，
CI 會確保它們與程式輸出永遠一致。

## 每天自動跑

設一次排程就不用管它。Windows：

```bat
schtasks /Create /TN twse-buyback-monitor /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 18:00 ^
  /TR "cmd /c cd /d C:\path\to\twse-buyback-monitor && python -m twse_buyback"
```

Linux/macOS cron：

```cron
0 18 * * 1-5  cd /path/to/twse-buyback-monitor && python -m twse_buyback
```

MOPS 在台灣上班時間更新資料，收盤後（18:00 台北時間）跑一次即可涵蓋當日申報。
執行失敗會回傳非零結束碼且不動舊基準，下一次執行自動復原。

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

## 運作方式

```text
抓取（上市＋上櫃）      POST MOPS 查詢；回應看起來不完整就重試
        │              （缺 </html> 結尾、筆數相對上次基準崩跌）
        ▼
與基準比對              新案／欄位異動／消失的案件
        │
        ▼
分類                    決議日太舊 → 回補，不當新聞；
        │              不合理暴增與消失 → 標記異常
        ▼
落地                    YYYY-MM-DD.md · snapshot_latest.csv ·
                        changes_log.csv · run.log
```

案件的識別鍵是「市場＋股號＋決議日＋目的＋買回起日」——全部是申報時就固定
的欄位。進度欄位變動是既有案件的更新，永遠不會被當成新案。snapshot 只會被
「通過所有檢查的回應」覆蓋，所以某一天的壞資料不會污染之後的每一天。

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
