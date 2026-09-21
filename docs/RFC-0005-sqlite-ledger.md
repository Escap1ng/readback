# RFC-0005：账本从扁平 JSON 换成 SQLite（M0·③）

- 状态：**Proposed**。可执行部分已验（`python m0/schema-check.py` 约束/迁移/对拍全过；`--self` 负向对照全咬住；`--mutation` 逐条摘 CHECK 反向覆盖无漏，三段 exit 0），未验的单独列在本文 §7。
- 关系：落实 `RFC-0004` §5 的 L2「替换 扁平 JSON → SQLite」；字段名沿用前身仓 `WorkUnit`/`ChangeSet`/`TestResult`/`Insight`/`Evidence`（结构体在 `workunit/mod.rs`、`insight/mod.rs`），所以 RFC-0003 §4 的数据模型不因换表而改名。
- **DDL 的唯一正本在 `m0/schema.sql`**，本文不复制它——同一份定义抄两处，正是 `M0-rules-inventory.md` §H 第 4 行点名的那个缺陷形态。

## 1. 为什么换

旧仓是"扁平 JSON 整文件重写"，上限 WorkUnit 100 / Insight 300 / 历史卡 500 / 决策日志 200（`RFC-0004` §2.3 第 3 行，含行号）。三个后果都是**账本会自己不诚实**：

1. 裁掉 oldest 是静默的 → 读者无法知道少了什么（§H 最后一行）。
2. 没有任何东西挡"被引用的记录先消失"。
3. 缺字段就是缺字段——没有约束会提醒你这行少了一列。

第 2 条本轮真撞上了：样本里 insight 还指着被 cap 裁掉的 work_unit，外键当场把导入拦下来。这不是设想的场景，是 `m0/schema-check.py` 跑出来的。

## 2. 范围与非目标

**范围**：账本的存储结构与约束、旧数据的迁移口径、schema 版本策略。
**非目标**：多设备同步（`crypto/` 的留出口照 `RFC-0004` §10）、查询语言或插件机制、分库策略（一人一文件，M0 没有并发读者）、ORM 与迁移框架。

## 3. RFC-0004 §2.3 点名的五个缺口，逐个落到列上

| 「账本没存」 | 新表里的落点 | 靠什么保证不糊弄 |
|---|---|---|
| 分支 | `work_unit.branch` | 可空。**没有分支就是 NULL，不许写 `"main"` 兜底** |
| token / 成本 | `tokens_in`、`tokens_out`、`cost_usd_milli`、`provider` | `CHECK (>= 0)`；成本是整数毫微单位，不是 float——累计误差会把"这轮花了多少"变成假数字 |
| 回合起始基线 | `base_commit`、`head_commit`、`baseline_ok` | `baseline_ok` 明写"采到了没有"。旧仓只有 `collection_error` 一句话，读者得自己猜 |
| unit 间关联 | `prev_unit_id`（链）＋ `unit_link`（边） | 链是一维的、边是 `kind ∈ {follows,duplicates,reverts,same-goal}` + `confidence 0..1`，`CHECK (unit_id <> related_id)` 禁自环 |
| 人工结论回指 | `human_answer(unit_id, claim_id, verdict, restatement)` | 答了却没结论 → `CHECK` 拒；判 `wrong` 却没复述也没标 `skipped` → `CHECK` 拒（M3 的复述通过率全靠这两条不松） |

## 4. 断言与证据：P1 的结构化落点

`claim` 表把「无证据不出声」写成约束，而不是写成一个约定：

- `evidence_id NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT` —— 没有证据的断言**在这张表里不存在**。
- `text` 为空或纯空白 → `CHECK` 直接拒。
- `verified ∈ {0,1}` ＋ 部分索引 `idx_claim_unverified`：出报告前扫这一张索引，`verified=0` 的句子不进产物。旧仓同一条判据只有 `debug_assert!`（release 不校验），所以它事实上从不生效。
- 本轮实测：样本里 3 条证据只有 1 条能在树里落地（另两条一个文件不存在、一个引用的是命令而非文件），`verified=0` 计 2；挂着断言的那条证据 `DELETE` 被 RESTRICT 拦下。

## 5. 版本策略

`meta(id=1, schema_version, min_reader, created_at, product_version)`，`CHECK (min_reader >= 1 AND min_reader <= schema_version)`——这条 CHECK 存在的理由是：写端比读端还新这种配置错误，光靠约定挡不住。

`schema_version >= 1` 没有单独写：上面那条 CHECK 已经蕴含它（`min_reader >= 1` 且 `min_reader <= schema_version` ⇒ `schema_version >= 1`）。`--mutation` 摘掉它时**没有任何用例会变红**——冗余约束的样子就是这个，删掉比留着诚实。

- M1 起用 `migrations/NNN_名字.sql` 顺序应用；**只加列，不在原地删列**；要删就走 `min_reader` 提升。
- 不承诺跨大版本读旧库（M0 没有用户，别为不存在的人付兼容成本）。
- 账本一律带 `schemaVersion`（`RFC-0004` §10 末行的要求），落在 `meta` 一处，不逐行冗余。
- **两个版本号不是一回事**，别合并：`meta.schema_version` 管**账本**的表结构；钩子/转录送来的**信封**另有一个契约版本（前身仓叫 `kvba.event.v1`，`M0-rules-inventory.md` SCHEMA 行）。新仓的信封契约名定为 `readback.event.v1`，落在信封上而不是账本列里——账本只在 `work_unit.source ∈ {git,transcript,hook,import}` 记它是从哪一路进来的。这样 `HANDOFF.md` 末尾那条记要（"迁 schema 时一并收掉，别让它以旧名进入新仓"）就有了落点，`docs/legacy/` 里那个旧名继续只作为**取证引用**存在。

## 6. 迁移：旧扁平 JSON → 表

| 旧文件 | 去向 | 不做 |
|---|---|---|
| `work_units.json` | `work_unit` + `event` + `file_change` + `command_run` | 不丢 `scope`/`collection_error` 的语义：后者变成 `baseline_ok=0` |
| `insights.json` | `evidence` + `claim` | 不把 `confidence` 当严重度用 |
| 历史卡 / 队列 / 冷却 / 预算 | **不迁** | 随 `gate/` 与弹卡形态一起退役（`RFC-0004` §7 现有代码处置） |
| `decision_log` | **不迁** | 它是打扰机的日志，不是账本 |

三条硬口径，都是撞出来的而不是设计的：

1. **项目身份 = 归一化路径的 sha256**（反斜杠→正斜杠、去尾分隔符、casefold），不沿用旧 `project_id`。旧仓复盘 §四 02 记的就是拿原始路径字符串做摘要，同一项目在磁盘上裂成两个记忆目录。实测：同一目录两种写法导进来，project 行数 2 而不是 3。
2. **旧 `tests[].evidence` 里的 `"exit 0"` 是文本**，导入后 `exit_code_src` 只能是 `parsed` 不是 `structured`。协议没带回来的东西不许伪装成带回来了——这条就是旧仓 `TestStatus::Unknown` 不伪造通过（C-03）的同一族规矩。
3. **cap 语义改成"保留最近 N 条，外加所有仍被引用的条"**，被裁的写进 `pruning_log(dropped, kept_through, reason)`。裁剪日志按事件累加、不去重——它是日志不是状态。

幂等实测：同一份样本导两次，数据行数不变。

## 7. 实测 / 未验证（不得越级表述）

**本机实测（2026-09-21，Python 3.14.5 / 自带 SQLite 3.50.4）**，三段命令全 exit 0：

| 命令 | 它证明什么 |
|---|---|
| `python m0/schema-check.py` | 51 项 = 40 条"该被拒的插入"全部真被拒 + 11 条迁移与证据对拍口径（cap 语义、幂等、路径归一、`parsed` 不冒充 `structured`、RESTRICT 真在拦） |
| `python m0/schema-check.py --self` | 7 段负向对照全咬住，含"关掉 `PRAGMA foreign_keys` 后 dangling-FK 必须插得进去"——它证明上面那些拒绝真是外键造成的，不是巧合 |
| `python m0/schema-check.py --mutation` | 反向覆盖：逐条把每条 `CHECK` 摘成 `CHECK (1)`，摘完必须**至少有一个用例变红**。当前 33/33 无漏 |

`--mutation` 是本轮跑出来的，第一次的结果不是 33/33 而是 **11/34**：23 条 CHECK 摘掉后没有任何用例理会它们——那些约束写没写都一样。补齐 22 条用例后，剩下的一条（`schema_version >= 1`）被证明被另两条蕴含，于是删掉而不是豁免（见 §5）。还顺手抓到一处**张冠李戴的红**：`unit_link` 的置信度用例引用了一条不存在的 unit，它其实是被外键拒的，CHECK 从未被验过——夹具里补了一条真 unit。

这三段没覆盖的，仍然不算验过 —— **M1 之前不得当事实写进代码**：
- 产品打包的 rusqlite 版本是否 ≥ 3.37（`STRICT` 的下界）。本机通不代表打包后通。
- 每个连接都要开 `PRAGMA foreign_keys=ON`；漏开一处，全部外键测试白做。rusqlite 侧要在连接建立处统一开，并写一条集成测试证明它。
- **删除路径只验了 `RESTRICT` 那一半**：`ON DELETE CASCADE`（删 project/unit 时下游）与 `SET NULL`（`prev_unit_id`、`claim_id`）今天没有任何用例会碰。M1 写账本修剪器之前先补，别到时候拿"外键都测过了"当依据。
- WAL / fsync 的实际吞吐，以及 5k unit × 平均 6 条证据下的查询延迟：本轮**没量过**，所以本文一个性能数字都没有。
- 真实运行数据的迁移：只验过自造样本 `m0/legacy-sample.json`。真实数据在 `%APPDATA%\dev.kvba.app\`，只读取样归人（`BOOTSTRAP.md` §5 同源）。

## 8. 对 M1 / M2 的接口

M1 的 CLI 只做两件事：写 `work_unit`/`evidence`，读 `verified=1` 的 `claim` 出报告——产物优先（P2）意味着报告是这张表的投影，不是另一份真相。目录 v1 每条规则的「所需证据」字段直接对应 `evidence.kind`，规则命中就落一行 `claim`。
