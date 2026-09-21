# 执行计划与 TODO

- **本文管什么**：下一步做什么、谁做、怎么算过。里程碑的验收判据在 `RFC-0004-mass-market-ledger.md` §6，必须由人联网跑的步骤在 `BOOTSTRAP.md` —— 本文**都不重述**，只给指针。同一判据抄两处，正是 §H 第 4 行点名的缺陷形态。
- **状态口径**：下面每行括号里是 2026-09-21 复验它的命令。跑不出来就是本文错了，按第 4 节处理，别将错继续排期。

## 1. 站在哪（实测快照）

| 事实 | 数值 | 怎么复验 |
|---|---|---|
| 新仓 | 4 commits / 14 个跟踪文件（本文尚未提交，提交后 15）/ 无远程 / 除本文外无未提交改动 | `git rev-list --count HEAD`；`git ls-files \| wc -l`；`git remote -v` → 空；`git status --porcelain` → 只有 `?? docs/PLAN.md` 一行 |
| M0·④ 已交付且自查真能红 | 46 条规则 | `python docs/m0-inventory-check.py` → 46 条 / exit 0；`--self` → 三段都咬住 |
| M0·①②③ | 未启动；①② 卡在同一份真实转录 | RFC-0004 §6、`BOOTSTRAP.md` §5（本机 `$HOME` 无 `.claude`） |
| 档案同一性 | 6/6 SAME（两边 blob 对象号相等） | `LEGACY-MANIFEST.md` §4 那段 `while read` 循环 |
| **旧仓可搬运性（本轮新发现，最紧）** | 导入锚点 `ddcbf4f` **不在**远程 `main` 上；本地领先 5 条，且远程无独有提交（纯 fast-forward） | `git -C ../kvba ls-remote origin refs/heads/main` → `ed8f700`；`git -C ../kvba merge-base --is-ancestor ddcbf4f ed8f700` → 非 0；`git -C ../kvba rev-list --count @{u}..HEAD` → 5，`HEAD..@{u}` → 0 |

最后一条的重量：`README.md:25`、`RFC-0004:6`、`LEGACY-MANIFEST:3` 三处都把"按行号能取到原文"押在 `ddcbf4f` 上，而这个对象今天只存在于这台机器。**这个仓库的证据链，锚点是单点的。**

## 2. TODO

顺序即依赖。只有 T0 与 T1 能并行，其余别跨阶段抢。M1 的入口是 T1+T2，M2 的入口是 T3，M3/M4 在 M2 出报告之前不动。

### T0 · 清掉本仓文档的 4 处自述缺陷（agent，无需联网，今天就能做）

1. `RFC-0004:76`「建回放语料（**本仓库** 47 commits…）」——指代随迁仓漂移：47 属旧仓，新仓是 4。`:6` 的免责只覆盖了 `file:line` 和 RFC-0003，没盖住这句，而 M0·① 正卡在这个指代上。
2. `RFC-0004:16/53/68/77` 的**目标**口径仍写 `kvba`（`.kvba/review.md`、`kvba report --md`、`npx kvba@latest`），与 `:130` §10 落法和 README 的 `readback` / `.readback/report.md` 冲突 → M1 照哪条实现，文档里现在有两个答案。注意 `:36`/`:144` 的 `.kvba/next-prompt.md` 是对旧产品的历史事实，**那两处不改**。
3. `M0-rules-inventory.md:165` 的种子拆分「C 组 7 + D 组 9 + B 组 3 + E-01/A-07」对不上：D 组种子实为 10 条（D-01..D-10），E-01/A-07 的处置是结构件不是种子；这串加起来 21，而标题"正好 20"本身是对的（B3+C7+D10）。
4. 同段「打扰机占了**一多半**」——实际 10/46 ≈ 22%。括号里的枚举（E 组 5、F 组 3、D-11、C-09）是对的；"一多半"只在 E/F 两组内部成立（5/8、3/5）。

**判据**：改前后逐处 `git diff` 取证；措辞类每处出 2–3 版挑；`python docs/m0-inventory-check.py` 与 `--self` 改完仍须分别 exit 0。**顺带把"分组计数与自述数字一致"纳进那个自查器**——它现在只查处置标没标，所以 3、4 两条它是放过去的，下一次照样靠眼睛才发现。附带在 README Layout 加一行指向本文（不留孤岛，复盘 §四 第 21 行的教训）。

### T1 · 把证据搬到这台机器以外（人 + 网络，最优先的人工动作）

- **旧仓那 5 条**（含锚点 `ddcbf4f`，含 RFC-0004 §11:147 一直挂着的那条 clippy 修复 `1b6a2c6`）：远程无独有提交，是纯 fast-forward。命令与判据已写成 `BOOTSTRAP.md` §0（2026-09-21）——**待你跑**。
- **名字占用核验（`BOOTSTRAP.md` §1）**：2026-09-21 已做完本机做得到的部分并写回文档——npm 裸名被占（航空通话转写，不同域）、crates.io 被占（Tauri IPC 占名预留）、两个备选名 `blindspot`/`witness` 在两个 registry 上双双被占且 `blindspot` 两处都是同域 → **三个候选全灭**，处置是仓库名与二进制名不变、npm 退 `@readback/cli`、crate 若发用 `readback-cli`。仍**待你跑**的三条：`gh search repos readback`、`gh api /users/readback`（本机被沙箱策略挡住），以及 `npm org ls readback`（决定 `@readback` 这个 scope 到底拿不拿得到）。
- **建仓（`BOOTSTRAP.md` §2）**：已决定公开。但 §2 原文是"先保持 private，直到 §4 的 license 有结论"，§4 又写"公开之前必须定 license"——**公开与 license 未定直接冲突，必须先解掉**（要么先定 license，要么明确接受"公开但无 LICENSE 文件"，那在法律上等于保留所有权利，且与这个仓库"无证据不出声"的门面不符）。
- **带回什么**：`git -C ../kvba merge-base --is-ancestor ddcbf4f origin/main` 变成 0；三条 GitHub/npm 核验结论；一句话 license 结论 + `LICENSE` 文件；仓库 URL。

### T2 · M0·② 证伪"零接线也带验证证据"（人取样、agent 判读，依赖 T1）

- 按 `BOOTSTRAP.md` §5 跑，带回脱敏样本的**字段名清单**（不要原文）。
- 判据：≥90% 的 shell 类调用能取到 0/非 0。取不到 → 走 RFC-0004 §8 的退路（L1 退 git-only），形态不变、M2 少一类规则，**不重开讨论**。
- 硬边界：结论出来之前这只是个假设，不得写进代码、README 主张或任何产物文案（§11 的"未验证"级）。

### T3 · M0·① 回放语料 + M0 唯一的那份验收物（agent，依赖 T1）

- 旧仓 47 commits 的 numstat / 作者 / 消息（2026-09-21 复验：`git -C ../kvba rev-list --count HEAD` = 47、`shortlog -sn --all \| wc -l` = 4）；不足则自造 20 个含已知缺陷的快照仓库。真实转录进仓的一律脱敏，`*.jsonl` 已被 `.gitignore` 挡住，别绕。
- 产物：`docs/replay-baseline.md` —— 候选规则的命中数 + 人工核对的真阳率。**没有这份数不许进 M2**（§6 原文判据）。

### T4 · M0·③ SQLite 迁移 RFC（agent，可与 T2/T3 并行）

- 表：`work_unit / evidence / claim / human_answer`；补 §2.3 点名的五个缺失字段（分支、token 与成本、回合起始基线、unit 间关联、人工结论回指）。
- 判据：带 `schemaVersion`（§10 末行要求），并写清旧仓扁平 JSON 的迁入口径与裁剪留痕（§H 最后一行那条规则）。

### T5 · 让 §H 那张表变成能引用的东西（agent，依赖 T3）

- 复盘 §四 的 38 类逐类映射到目录规则，标"有检测器 / 半有 / 无"。2026-09-21 复验：`docs/legacy/复盘与工程约定.md` §四 竖线行 41 = 表头 + 分隔 + 39 数据行，其中 1 行 `~~作废~~` → 38 类，与 §2.3 的说法一致。
- H 组顶部现在写着"初判，未跑数"——T3 的数出来之前，任何地方不得把它写成覆盖率。

### T6 · 环境尾差（低优先，别占用前面的时间）

- 4 份档案的工作区字节带 CRLF（`git ls-files --eol`：HANDOVER / InitPrompt / rfcs/RFC-0003 / 复盘 均为 `i/lf w/crlf`），而 `.gitattributes` 要 `eol=lf`。`git status` 因 clean 滤镜先归一化而**永久看不见这个差**。内容同一性没坏（blob 6/6 SAME），但按工作区字节读档案就是读到 CRLF。修法：`git checkout -- docs/legacy` 重导，或 `git add --renormalize .`。
- 本机 `.git/hooks/post-commit`、`post-checkout` 是 Qoder 自己的代码统计钩子，不在版本控制里。M1 要写 git hook（§6 的 post-commit 记账 / pre-push 出报告）时**追加**，别覆盖。

## 3. 什么时候砍

- RFC-0004 §8 最后一行是留给自己的刀：任一里程碑跨 6 周仍无可演示产物 → 收缩。**M0 的"可演示产物"就是 `docs/replay-baseline.md` 那一份数**，不是更多文档。
- 触发即停的组合：T2 判据失败 **且** T3 命中率明显低于 70% → 撤判断层，退成纯账本（存档 + 检索 + 成本归属），产品仍成立（§8 第一行退路）。
- 本机执行约束照 §11 末段：无 `link.exe` / SDK 库 → `cargo test`、`cargo clippy` 只能在 CI 验；`cargo fmt` 与 `rustc --emit=metadata` 本机可跑。所有编译期验收按 CI 排期写。

## 4. 有意不进这份计划

继承 RFC-0004 §3 的六不做。另加三条本文自己的：不给 `docs/legacy/` 就地改内容（`LEGACY-MANIFEST.md` §1 铁规则 1）；不在第一个 `cargo init --lib` 之前建 CI（`BOOTSTRAP.md` §6——恒绿的检查器不是证据，是噪音）；不把 10 条打扰机迁进目录 v1（`M0-rules-inventory.md` 统计第 2 点）。

**若本文与 RFC-0004 冲突 → 以 RFC-0004 为准，改本文。**
