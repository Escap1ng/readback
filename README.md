# readback

**回读** — the radio-procedure step where the receiver repeats an instruction back, proving they actually understood it. That is what this tool asks of code your AI agent wrote.

> **Status: M0 — documents only.** No runnable code lives here yet. M0 is a data-collection milestone, not a feature milestone; see `docs/RFC-0004-mass-market-ledger.md` §6. Any claim below that is not yet true is written as a target, never as a feature.

## The problem

Agents now write a large share of the code that ships, and nothing in the toolchain records **whether anyone verified it**. Comprehension debt and trust debt are the same debt: you cannot explain the change, and there is no evidence it was ever tested.

## The bet

|  |  |
|---|---|
| **Evidence or silence** | Every claim carries a pointer to a file, a commit, or a command exit code. A sentence that cannot be checked locally does not get generated — including in the UI, including in the icons. |
| **Artifact first** | The product is a file you can share: `.readback/report.md`, a PR summary block, a commit trailer, a weekly digest. Notifications and desktop widgets are subscribers to that artifact, not the product. |
| **Zero-wiring first** | `git` plus records your agent already writes on disk are enough for most of the value. Host-side hooks are an optional low-latency enhancement, never a requirement. |

## Why not just another AI code reviewer

As of mid-2026 there are big-vendor open-source AI code-review CLIs advertising five-minute setup. Reviewing code is not a moat — the model does it for free. What cannot be bought is a **local, cross-agent ledger of what happened in your session**, plus a mechanism that closes the loop by making you restate the change in your own words. That is the product here.

## Provenance

This repo inherits from a private predecessor (KVBA v0.2.0), kept as a read-only reference implementation. Its measured findings, its static-audit findings, and its still-unverified assumptions are graded separately in `docs/RFC-0004-mass-market-ledger.md` §11 — **nothing marked 未验证 may be written into code as if it were fact.** That RFC is the founding document; `docs/BOOTSTRAP.md` lists the steps that need a human and a network.

---

## 中文

`readback`（回读）要解决的是同一件事：**agent 写的代码，没人验证过，也没人能解释**。

- 三条主张：无证据不出声、产物优先、零接线优先。
- 主产物是文件（`.readback/report.md`、PR 摘要段、commit trailer、每周 digest），不是弹窗。桌面胶囊与系统通知只是这份产物的订阅者。
- 前身是私有项目 KVBA v0.2.0（保留为参考实现）。RFC-0004 §11 把结论分成「本机实测 / 静态审计 / 未验证」三级；标为未验证的不得当事实写进代码。
- **当前只有文档，没有可运行代码。** 需要人肉联网执行的步骤（改名核验、建远程仓、签名与公证询价）写在 `docs/BOOTSTRAP.md`。

## Layout

```
docs/RFC-0004-mass-market-ledger.md    founding strategy: 定位、四层形态、里程碑 M0–M4、旧代码处置
docs/BOOTSTRAP.md                     steps that require a human terminal (name checks, remote repo, code signing)
docs/M0-rules-inventory.md            M0·④ 交付物：旧仓 46 条确定性启发式逐条抄成数据（含"哪些缺陷形态今天根本没有检测器"的初判）
docs/m0-inventory-check.py            上面那份清单的自查（漏抄 / 未分类 / 表格塌陷），`--self` 三段负向对照；规则迁完就该删
```
