# readback

**回读** — the radio-procedure step where the receiver repeats an instruction back, proving they actually understood it. That is what this tool asks of code your AI agent wrote.

> **Status: M0 — evidence tooling only.** Nothing here ships as the product yet. The executable code in the repo is measurement tooling that is meant to be thrown away once the rules migrate: `docs/m0-inventory-check.py` and `m0/*.py`. One exception: `m0/schema.sql` is the DDL that M1 is meant to implement, not a fixture. M0 is a data-collection milestone, not a feature milestone; see `docs/RFC-0004-mass-market-ledger.md` §6. Any claim below that is not yet true is written as a target, never as a feature.

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
- **当前只有取证夹具，没有产品代码。** `docs/m0-inventory-check.py` 与 `m0/*.py` 是给规则跑数用的，规则迁完就该删——留着就成了永远绿的检查器。唯一的例外是 `m0/schema.sql`：它是 M1 要照着落地的 DDL 正本，不是用完即弃的夹具。需要人肉联网执行的步骤（改名核验、建远程仓、签名与公证询价）写在 `docs/BOOTSTRAP.md`。

## Layout

```
docs/RFC-0004-mass-market-ledger.md    founding strategy: 定位、四层形态、里程碑 M0–M4、旧代码处置
docs/RFC-0005-sqlite-ledger.md         M0·③ 交付物：账本 扁平 JSON → SQLite 的提案（含迁移口径与"哪些没验过"）；DDL 正本不在这份文档里
docs/BOOTSTRAP.md                     steps that require a human terminal (name checks, remote repo, code signing)
docs/PLAN.md                          执行计划与 TODO（T0–T6 泳道，每行带复验命令）；转公开前的收口清单在 BOOTSTRAP §7
docs/HANDOFF.md                       任务交接：换会话/换机器怎么冷启动、本轮改了什么、已踩过的坑
docs/M0-rules-inventory.md            M0·④ 交付物：旧仓 46 条确定性启发式逐条抄成数据（含"哪些缺陷形态今天根本没有检测器"的初判）
docs/m0-inventory-check.py            上面那份清单的自查（漏抄 / 未分类 / 表格塌陷 / 自述数字对不对），`--self` 负向对照；规则迁完就该删
m0/build-corpus.py                    M0·① 语料生成器：18 个缺陷形态 + 5 类反例，同 seed 逐字节可复现，产物落在被 .gitignore 挡住的 `m0/corpus/`
m0/replay.py                          把 20 条规则（写成数据表）跑在语料上；每条命中必须带可核证据，核不上就丢弃并计数
m0/schema.sql                         M0·③ 的 DDL 唯一正本（STRICT 表 + 约束）；RFC-0005 有意不复制它
m0/schema-check.py                    三段验证：约束真会拒吗 / 拒绝真由该约束造成吗（`--self`）/ 摘掉约束有没有人报（`--mutation`）
m0/legacy-sample.json                 自造迁移样本，字段名取自旧仓真实结构体；真实运行数据不入库（见 BOOTSTRAP §5）
docs/replay-baseline.md               上两者的输出（生成物，数字不手填）：命中数 / 真阳 / 假阳 / 未登记 + 人工抽核还欠着
docs/manual-audit.md                  人工抽核工作单：20 行、每条规则各 1 条，判定列留空——填完 M0·① 才收口
docs/LEGACY-MANIFEST.md               什么从前身仓库导进了 `docs/legacy/`、什么有意留在原仓、以及怎么复验
docs/legacy/                          前身仓库的只读档案（复盘、交接报告、RFC-0003、原始规格、旧 README、对拍脚本）——**只读，改了就破坏档案**
```
