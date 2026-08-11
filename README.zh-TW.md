# twse-buyback-monitor

追蹤台股上市櫃公司的庫藏股（買回本公司股份）公告，並且分得出「真的有新聞」跟「資料源今天出包」。

台股上市櫃公司買回自家股票必須在公開資訊觀測站（MOPS）申報。本工具每天抓那張表、
跟上次比對，回報兩件事：**新公告的買回案**，以及既有案子的**執行進度異動**。

[English](README.md)

```console
$ python -m twse_buyback --data-dir ./data
new=3 changed=2
```

- 不需要 API key、不需要帳號、不需要爬蟲框架。
- 第三方依賴只有一個：`requests`。
- 全程確定性，管線裡沒有任何 LLM。

## 安裝

```bash
git clone https://github.com/oeni/twse-buyback-monitor
cd twse-buyback-monitor
pip install -e .
```

需要 Python 3.9 以上。

## 用法

```bash
# 首次執行只建 baseline，不會把既有案子當成新公告
python -m twse_buyback --data-dir ./data

# 同時印出 Markdown 報告
python -m twse_buyback --data-dir ./data --print-digest

# 讓排程在「資料看起來有問題」時也亮紅燈，而不是只有抓取失敗才紅
python -m twse_buyback --data-dir ./data --strict
```

`--data-dir` 下會產生三個檔：

| 檔案 | 內容 |
|---|---|
| `snapshot_latest.csv` | 最近一次抓到的完整表格。每次覆蓋，是所有 diff 的比較基準。 |
| `changes_log.csv` | 只追加的歷史紀錄。類型有 `new`、`changed`、`backfill`、`removed`。 |
| `run.log` | 每次執行一行，含重試與異常。 |

當成函式庫用：

```python
from pathlib import Path
from twse_buyback import Settings, run, render

result = run(Settings(data_dir=Path("data")))

for case in result.announcements:
    print(case["code"], case["name"], case["planned_shares"])

if result.anomalies:
    print("這次結果別信：", result.anomalies)

print(render(result))   # Markdown 報告
```

`run()` 只負責寫 CSV 並回報變化，不決定你要拿它做什麼——丟 Slack、寫進筆記、
觸發告警，都由你自己接。

## 這個專案真正的重點

這種工具的直覺版本三十行就寫得完：抓、解析、跟昨天比、報差異。那個版本是錯的，
而且錯得**看起來像在正常運作**。

MOPS 會間歇性回一份**在表格中途被截斷**的內容。沒有 `Content-Length` 標頭、
HTTP 狀態是 200、殘缺的內容還能完美解析——只是列數變少，而且少的永遠是尾端。
請求和回應裡沒有任何地方顯示出事了。

於是直覺版本把這份殘缺表格覆蓋到自己的 snapshot 上。隔天完整回應回來，
所有消失過的列現在「基準裡沒有、這次抓到有」——那正是「新案」的定義。
工具就報出好幾百筆全新的庫藏股公告，其中包括民國 96 年（2007）董事會決議的案子。

這不是假設，這是本工具前身實際發生的事：

```
2026-08-05T18:00:01 OK new=524 changed=0
2026-08-11T18:00:01 OK new=998 changed=0
```

```
2026-08-11,new,sii,3060,銘異,96/11/22,轉讓股份予員工,"預定3,000,000股 96/11/23~96/12/31"
```

注意那個 `OK`。每一次執行都是成功的。真正**列消失的那一天完全無聲**，
因為當初的工具只追蹤新增與變動——一個看不見刪除的 diff，就看不見資料流失。

### 本工具的處理方式

四層獨立護欄，順序是讓最便宜的擋掉最多：

**1. 結構檢查**：完整的回應以 `</html>` 結尾，中途被砍斷的不可能有。
這一層不需要任何歷史資料，所以第一次執行就有效。

**2. 完整性檢查**：列數不得相對上次的良好 snapshot 崩塌（預設至少 95%）。
這一層攔的是「剛好斷在標籤邊界、結構看起來完整」的截斷。

任一層失敗就重抓（預設 3 次）。截斷是暫時性的，重試通常就好了。
若每次都失敗，該次執行顯性 raise，而且**完全不動 snapshot** —— 壞資料永遠不會
變成基準，所以隔天的執行會自己復原。

**3. 合理性檢查**：台股正常一天的庫藏股申報是個位數。一次幾十筆會被標成異常，
而不是當成新聞報出去。

**4. 時效檢查**：民國 96 年的董事會決議不可能是今天的新聞。超過門檻
（預設 6 個月）的案子記成 `backfill`，不列入新公告。

另外會追蹤刪除。庫藏股案是歷史紀錄，不該從表裡消失；真的消失了，你會知道。

貫穿整個設計的原則是：**絕不寫入殘缺結果，也絕不讓資料品質問題偽裝成市場事件。**
每個失效都顯性 raise，每個異常都寫在報告裡，不粉飾。

## 資料源踩坑筆記

以下全部經過對線上端點實測：

- 端點是 `POST https://mopsov.twse.com.tw/mops/web/ajax_t35sc09`，
  是網站自己的內部 AJAX 呼叫，不是官方 API。它隨時可能改版；改版時本工具會 raise，不會亂猜。
- **表單的 `year` 與 `month` 參數完全無效。** 實測 115/08、115/07、114/03、110/01
  全部回同一份涵蓋民國 89 年至今的完整歷史表。有一個線上測試在斷言這件事，
  所以哪天 MOPS 真的把篩選做出來，你會從測試失敗得知。
- 資料列固定 20 個 `<td>`。線上資料列 100% 符合，所以格數不對的列是版面、不是資料。
- 標記 `累計` 的列是各公司的合計。保留在 snapshot 內，但排除在 diff 之外。
- 日期是民國紀年：115 年 = 2026 年。

## 開發

```bash
python -m unittest discover -s tests -t .              # 離線，約 0.5 秒
RUN_NETWORK_TESTS=1 python -m unittest tests.test_smoke_network   # 線上
```

線上測試斷言的是解析器賴以成立的假設，所以 MOPS 改版時，它們會告訴你是哪個假設破了。

## 授權

MIT
