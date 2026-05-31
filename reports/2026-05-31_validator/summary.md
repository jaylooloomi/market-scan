# PolyDig Phase 0 — Leading Edge Validator Summary

**Run date**: 2026-05-31
**Config**: `cases.json`
**Cases**: 5 themes × 3 triggers = **15 test points**

## Go/No-Go Decision

### ✅ **GO** — concept validated, proceed to Phase 1

- Cases with at least one 🟢 STRONG trigger: **4/5** (mask, shipping, ai, silicon_photonics)
- Cases with at least one leading (🟢 or 🟡) trigger: **5/5** (mask, shipping, ai, defense, silicon_photonics)

## Verdict Distribution (15 trigger-level aggregates)

| Verdict | Count | % |
|---|---|---|
| 🟢 強領先 | 6 | 40% |
| 🟡 弱領先 | 5 | 33% |
| 🔴 太晚 | 3 | 20% |
| ⚫ 無效 | 1 | 6% |
| ⚠️ 無法判定 | 0 | 0% |

## Per-Case Summary

| Case | 訊號類型 | early | mid | late |
|---|---|---|---|---|
| 口罩/防疫股 | News | 🟢 強領先 | 🟢 強領先 | 🟡 弱領先 |
| 貨櫃航運 | Data | 🟢 強領先 | 🔴 太晚 | 🔴 太晚 |
| AI 概念股第一波 | News-International | 🟢 強領先 | 🟢 強領先 | 🔴 太晚 |
| 國防/俄烏戰爭 | News-Sudden | 🟡 弱領先 | 🟡 弱領先 | 🟡 弱領先 |
| 矽光子/CPO | Roadmap | 🟢 強領先 | 🟡 弱領先 | ⚫ 無效 |

## Interpretation Guide

- **強領先 (🟢)**：事前 < +10% excess AND **任一事後窗口爆發** (post30>+30% OR post90>+50% OR post180>+80%)
- **弱領先 (🟡)**：事前 < +30% AND **任一事後窗口有明顯漲幅** (post30>+10% OR post90>+20% OR post180>+15%)
- **太晚 (🔴)**：事前已 > +30% excess → 訊號出現時市場已先漲，進場太晚
- **無效 (⚫)**：所有窗口都沒打到弱領先門檻，或事後 180 天 < +10% → 題材沒成立
- 所有「事前/事後」都是**相對於 TAIEX 同期漲跌**的 excess return
- **多窗口設計理由**：許多題材是慢熱型 (AI、矽光子)，T+30 還沒啟動但 T+180 大爆發。只看 T+30 會誤判系統價值。

## Files in this run

- [口罩/防疫股](./mask.md) — full per-ticker breakdown
- [貨櫃航運](./shipping.md) — full per-ticker breakdown
- [AI 概念股第一波](./ai.md) — full per-ticker breakdown
- [國防/俄烏戰爭](./defense.md) — full per-ticker breakdown
- [矽光子/CPO](./silicon_photonics.md) — full per-ticker breakdown