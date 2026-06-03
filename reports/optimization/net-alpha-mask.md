# 口罩股 net-alpha 試算(finance P0 實作成果)

**日期**:2026-06-01 ｜ **工具**:`market_scan_validator/net_alpha.py`(`python -m market_scan_validator.net_alpha`)
**trigger**:2020-01-20(鍾南山證實人傳人,可行動的 mid trigger)｜ **資料**:yfinance 真實歷史價

> 回應金融分析師 review 的 P0:「+310% 是**毛報酬**、T-1 收盤進場、無成本、無出場——**淨的、買得到的**是多少?」

## 三情境(真實價格跑出來)

| 股票 | A 毛報酬(headline) | B 最保守 net | C +出場規則 net | C 持有日 |
|---|---|---|---|---|
| 康那香(9919) | +212% | +134% | +18% | 30 |
| 恆大(1325) | +642% | +456% | +54% | 30 |
| 南六(6504) | +84% | +38% | **−26%** | 29 |
| **平均** | **+313%** | **+209%** | **+16%** | — |

- **A**:T-1 收盤進場、持有 T+180(validator 口徑,即「+310%」那種數字)
- **B 最保守 net**:T+2 交易日進場(小型股訊號後 1-2 天開盤漲停,T-1 收盤的「成交」是假設)+ 0.5% round-trip 成本
- **C**:B 再加出場規則(−20% 停損 / 30 日 time-stop,先到先出)、net

## 怎麼讀

1. **A → B(+313% → +209%)**:光是「漲停買不到 + 交易成本」,headline 就掉約 1/3。
2. **B → C(+209% → +16%,南六轉負)**:加上基本風控後落差巨大——而且這還沒扣 beta。

## 誠實的但書(C 偏悲觀,別過度解讀)

- **C 的 30 日 time-stop 比口罩題材的 hold_period 短**:`themes.json` 寫口罩「漲快跌也快、1-3 個月」,30 天就出場會在主升段中途離場(口罩高點在 2020/3,約 T+45-60)。所以 C 是「**笨出場**」的下限,不是最佳解。
- **更好的下一步**:出場規則應吃 `themes.json` 的 `hold_period` / `actionable_window`——用題材自己的時間軸,而非固定 30 天;那會落在 B 與 C 之間。
- **raw return、未扣 beta**:高 beta 題材(航運/AI)再扣 beta 會更低([03-financial-analyst-value.md](reports/optimization/03-financial-analyst-value.md) §1)。close-based 停損(非盤中)也是簡化。

## 結論

> **真實淨報酬遠低於 headline,且高度取決於「買得到」與「怎麼出場」。** +313% 是行銷數字;扣漲停與成本剩 ~+209%;加上(即使笨的)風控可能只剩 +16%、甚至個股轉負。這**不代表沒有 alpha**——而是:**宣稱 alpha 前,必須用「net + 可成交 + 有出場」的口徑算**。下一步是把出場規則接上 `themes.json` 的 hold_period,給出「合理風控下的淨報酬」區間。

> 純函式(`round_trip_net` / `exit_with_rules`)有離線單元測試(`tests/test_net_alpha.py`);本表由 `net_alpha_report()` 以真實 yfinance 價產生。
