# policy-mcp (Phase 4)

政策/法規公告感測器。政策訊號(疫苗 EUA、關稅、健保藥價、太空法)埋在政府網站,**不會出現在新聞 RSS**,需專屬 collector。

## Tools

| Tool | 說明 |
|---|---|
| `list_policy_sources()` | 列出候選政府來源 + 爬取可行性 |
| `fetch_policy_announcements(source, limit)` | 抓近期公告(RSS 可行者實作;HTML-only 回 not_implemented) |

## 來源可行性研究(HANDOFF P4.1)

| source | 名稱 | 可行性 | 備註 |
|---|---|---|---|
| `mohw` | 衛福部 | RSS(待驗證 feed 路徑) | 疫苗 EUA、健保藥價 |
| `fsc` | 金管會 | needs_html_scrape | 金融法規、ETF 核准;新聞稿 HTML |
| `ey` | 行政院 | needs_html_scrape | 重大政策、補助 |
| `ly` | 立法院公報 | needs_html_scrape | 三讀法案;lis.ly.gov.tw 結構複雜 |

## 限制(誠實聲明)

- 目前只有 RSS-feasible 來源能實際抓取;HTML-only 來源回 `not_implemented` + TODO,**不假裝有資料**。
- HTML 爬蟲需 retry + diff(政府網站結構常變)。
