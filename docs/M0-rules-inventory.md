# M0·④ 规则清单：把旧仓的确定性启发式逐条抄成数据（不改语义）

- 目的：RFC-0004 §5 的 L3「缺陷形态目录」的原料。先抄准，再筛选，最后才谈新增——**这一步不做任何改进**。
- 口径：判据按源码原文转写，阈值与字面量原样保留；`处置` 列只是分类标记，不代表已决定取舍。
- 出处：全部行号指向前身仓库 KVBA v0.2.0（`ddcbf4f` 及之前可取到原文）。测量时间 2026-09-20，逐条读码而非摘要。
- 处置图例：**种子** = 可直接进目录 v1 的判断；**结构件** = 账本地基，不是判断；**打扰机** = 只为"何时弹卡"服务，形态本身要淘汰；**教训** = 判据已过时但背后的规矩要迁成规则或测试。

## A 组：回合边界与事件归组

| ID | 判据（转写） | 需要的证据 | 现输出 | 出处 | 处置 |
|---|---|---|---|---|---|
| A-01 | `event_type == "turn.ended"` 且 `intent.trim() != "子代理回合结束"` | 事件 id | WorkUnit 收口切口 | `workunit/mod.rs:107-113` | 结构件 |
| A-02 | `event_type == "session.ended"` 恒为边界；但若窗口内只有它一条（`len == 1`）则整单元丢弃 | 事件 id | 不产生空 WorkUnit | `workunit/mod.rs:110,157` | 结构件 |
| A-03 | 同会话判定：`session_id` 非空 → 双方 id 相等 **且** `agent_family(emitter)` 相同；id 为空 → 退化为"两边都空 + 同 emitter" | — | 事件归组 | `workunit/mod.rs:115-123` | 结构件 |
| A-04 | 起点 = 向前最近一个收口边界的下一条；单单元最多 200 条事件，超出**静默丢最旧** | — | 窗口裁剪 | `workunit/mod.rs:14,148-162` | 结构件（丢弃须留痕，见 §H） |
| A-05 | 目标推断：优先取 `message.updated` 的非空 intent；否则取任一非泛化边界语的 intent；截 500 字 | 事件 id | `WorkUnit.goal` | `workunit/mod.rs:200-215` | 结构件 |
| A-06 | 泛化边界语剔除：`回合结束` / `回合结束(停止钩子应答)` / `本轮处理结束` / `Codex 回合结束` / 前缀 `会话结束(` | — | intent 过滤 | `workunit/mod.rs:217-223` | 教训（宿主文案字面量，跨宿主必脆） |
| A-07 | 跨路内容判重：指纹相同 + 时间差 ≤5s + 缓冲 512 条 | 事件指纹 | 丢弃重复事件 | `events/mod.rs:174-182` | 结构件 |
| A-08 | `agent_family(emitter)`：前缀归一为 claude-code / opencode / codex 三族，未知族回退原始名 | — | 家族比较 | `events/mod.rs:25-36` | 结构件 |

## B 组：文件形态分类（唯一可复用的词表）

| ID | 判据（转写） | 需要的证据 | 现输出 | 出处 | 处置 |
|---|---|---|---|---|---|
| B-01 | 源文件：ASCII 小写后 ends_with 任一 —— `.rs .ts .tsx .js .jsx .vue .py .go .java .kt .swift .cs .cpp .c .h`（15 项） | 文件路径 | 参与 test-gap 判定 | `insight/mod.rs:474-482` | 种子（词表要外置成数据） |
| B-02 | 测试文件：反斜杠转正斜杠后 contains 任一 —— `/test/` `/tests/` `__tests__` `.test.` `.spec.` | 文件路径 | 从源文件集里排除 | `insight/mod.rs:484-491` | 种子 |
| B-03 | 决策文件：ends_with 任一 —— `Cargo.toml` `Cargo.lock` `package.json` `package-lock.json` `pnpm-lock.yaml` `yarn.lock` `pyproject.toml` `requirements.txt` `go.mod` `Dockerfile` `tauri.conf.json`（11 项）；或 contains `/.github/workflows/` 与 `/migrations/` | 文件路径 | 触发 Decision 洞察 | `insight/mod.rs:493-512` | 种子 |

## C 组：证据化判断（目录 v1 的主力）

| ID | 判据（转写） | 需要的证据 | 现输出 | 出处 | 处置 |
|---|---|---|---|---|---|
| C-01 | `tests` 中存在 `TestStatus::Failed`（**只认结构化 exitCode，文本里的 error/failed 一律不算**） | 测试事件 id + 命令名 | Risk / **P1** / conf 0.95 | `insight/mod.rs:311-348` | **种子★**（全仓唯一 P1 生产者） |
| C-02 | 有源文件变更（B-01 且非 B-02）而 `tests` 为空 | 最多 5 个文件证据 | TestGap / P2 / 0.9 | `insight/mod.rs:243-272` | **种子★** |
| C-03 | 捕获到测试命令，但其中含 `TestStatus::Unknown`（协议没带退出状态） | 测试事件 id | TestGap / P2 / **0.98** | `insight/mod.rs:275-301` | **种子★**（最高置信的陈述是"没有证据"这句） |
| C-04 | 任一源事件 `has_api_call \|\| has_error_path \|\| todo_or_fixme` | 事件 id + intent 前 180 字 | Risk / P2 / 0.68 | `insight/mod.rs:350-401` | 种子（自陈"文本信号，不等同已确认缺陷"） |
| C-05 | `change_set.files` 中有 B-03 命中 | 最多 5 个文件证据 | Decision / P2 / 0.82 | `insight/mod.rs:403-428` | **种子★** |
| C-06 | 工作区非空 → 汇总文件数、`+add/-del`、以及"行数未采集"的文件数；证据范围四档分别给 0.72/0.55/0.50/0.35 | 每个文件一条 Evidence | Explain / Info | `insight/mod.rs:135-207` | 种子（**"未分级证据"要写进结论文案**，这个模式保留） |
| C-07 | 工作区为空 → 退回 codex-notify 或 `message.updated` 的 intent，结论必须自带"仅证明 Agent 报告了什么" | 事件 id | Explain / Info / 0.45 | `insight/mod.rs:210-240` | 种子（降级话术的模板范式） |
| C-08 | 多条洞察并存时取序：Risk > Decision > TestGap > Explain > Question（数组顺序即优先级） | — | `primary()` | `insight/mod.rs:123-133` | 结构件 |
| C-09 | 值得打断：`risk ∈ {P1,P0}` **且** `confidence ≥ 0.85` | — | `interrupts()` | `insight/mod.rs:96-102` | 打扰机（阈值迁给"报告置顶排序"） |
| C-10 | 洞察 id = blake3(workUnitId \| kind \| 证据引用串联) 前 16 hex；`debug_assert!(!evidence.is_empty())` | — | 幂等 id | `insight/mod.rs:441-459` | 教训（release 不校验 = P1 闸门要替换的那一类） |

## D 组：G5-A 打分启发式（判据是种子，加法是打扰机）

共享两条已实测钉死的口径：**只遍历写事件**（`gate/mod.rs:186`）、**罚分按批只扣一次**（`:246-277`）。文本一律取 `diff_head + intent` 小写前 600 字（`:171-173`）。

| ID | 判据（转写） | 分值 | 现输出 | 出处 | 处置 |
|---|---|---|---|---|---|
| D-01 | `line_delta ≥ 20` | +30 | 大改 | `gate/mod.rs:194-196` | 种子（"变更规模分档"进目录） |
| D-02 | `8 ≤ line_delta < 20` | +15 | 值得看一眼 | `gate/mod.rs:197-200` | 种子 |
| D-03 | `has_api_call` 或文本含 `http`/`axios`/`fetch`/`reqwest`/`api key` | +25（按批一次） | 新增外部调用 | `gate/mod.rs:202-214` | **种子★**（目录里换成"diff 出现调用点"而非文本关键词） |
| D-04 | (`has_error_path` 或含 `panic!`) 且不含 `catch`/`try {` 且 `line_delta ≥ 10` | +15 | 异常路径未见保护 | `gate/mod.rs:217-222` | 种子（注释自陈文本级误报率高，故降权） |
| D-05 | `todo_or_fixme` 或文本含 `todo`/`fixme` | +15 | 遗留标记 | `gate/mod.rs:225-228` | **种子★**（最接近可确定性核实的一条） |
| D-06 | intent 含 `删除`/`remove `/`rm ` 且涉及 6 个代码扩展名之一 | +15 | 删除代码文件 | `gate/mod.rs:230-239` | 种子（无依赖分析 → 升格为"删了什么、谁还引用"） |
| D-07 | 文本含 `throw` 且不含 `catch` | +12 | 裸 throw | `gate/mod.rs:241-244` | 种子 |
| D-08 | 本批写事件触及去重后 ≥3 个文件 | +10 | 影响面 | `gate/mod.rs:262-269` | 种子 |
| D-09 | `line_delta < 5` 且文本含 `format`/`rename`/`重构` | −30 | 纯格式化 | `gate/mod.rs:246-249,270-273` | 种子（作"抑制判断"，不作打扰判断） |
| D-10 | 本批文件全部是 `.md`/`README`/`docs/` | −30 | 纯文档 | `gate/mod.rs:251-257,274-277` | 种子（同上） |
| D-11 | 分数 `clamp(-100, 200)` | — | 上下界 | `gate/mod.rs:280` | 打扰机 |
| D-12 | P0（旧）：`有网络信号 && 批内无任何 diff 含 catch`，或 intent 含 `不完整`/`未覆盖`/`无覆盖` | 布尔 | `scoring.p0` → 卡片 severity | `gate/mod.rs:288-295` | 教训（与 C-01 抢同一语义，"中文文案当证据"的反面教材） |

## E 组：抑制、去重与路由

| ID | 判据（转写） | 现输出 | 出处 | 处置 |
|---|---|---|---|---|
| E-01 | 写事件：`tool_name ∈ {edit, write, patch}` 且 `event_type ∈ {tool.completed, tool.started}` | 分支路由的事实基础 | `gate/mod.rs:124-127` | 结构件（宿主字面量，需外置） |
| E-02 | 知识信号：任一 `turn.ended` 或 `tool_name == "think"` | 知识分支入口 | `gate/mod.rs:130-134` | 打扰机 |
| E-03 | 主题级指纹 `branch\|theme\|首个引用文件`；正文级指纹 `branch\|theme\|正文前 120 字小写`；各取 blake3 前 16 hex | 去重键 | `gate/mod.rs:141-151` | 教训（**两口径不可混用**这条规矩要写进目录） |
| E-04 | `dedup_hit`：pending 卡片指纹相同，或历史卡片在 20min 窗口内指纹相同 → 拦 | G6 拒绝 | `gate/mod.rs:401-416` | 打扰机 |
| E-05 | 频控 25s / 同主题冷却 10min / 用户静默 1h（force 与破冰可旁路前两者，**静默期任何路径都不旁路**） | G2 拒绝 | `gate/mod.rs:20-24,442-482` | 打扰机（但"静默期 = 用户唯一否决权，永不放宽"要迁成数据） |
| E-06 | 队列硬闸：`pending ≥ 3` 直接拒，连"来一道"也不破例 | G1 拒绝 | `gate/mod.rs:423-434`、`queue/mod.rs:15` | 打扰机 |
| E-07 | 路由回落：写信号达标才走审查，否则回落知识；两者皆无时 G4/G5-A 分别给出**可执行**的拒绝原因 | G4 路由 | `gate/mod.rs:436-517` | 打扰机（"拒绝原因必须可执行"要迁） |
| E-08 | 自动路由三分支：收口边界 → WorkUnit；`emitter == "claude-code-watcher"` → LegacyWatcher（走完整门控）；其余 → AwaitBoundary（只攒窗口不评估） | 链路选择 | `workflow.rs:10-27` | 结构件（离线化后要重画） |

## F 组：知识主题与破冰（整组随知识分支退役）

| ID | 判据（转写） | 出处 | 处置 |
|---|---|---|---|
| F-01 | 框架 → 主题五桶映射（vue/nuxt→`vue-lifecycle`，react/next/remix→`react-lifecycle`，svelte，tauri/rust→`rust-ownership`，nest/express/fastify/laravel→`backend-async`），未命中落主题池 | `gate/mod.rs:301-320` | 打扰机 |
| F-02 | 通用主题池 4 条 + `pool_pick`：blake3 首字节 % 池长（确定性伪随机，可复现） | `gate/mod.rs:323-334` | 打扰机 |
| F-03 | 候选 = 项目主题 + 主题池；取"未被静默 && 最久未问"，全被静默时仍返回最久未问者，以便给出可执行拒绝原因而不是换题硬递 | `gate/mod.rs:341-375` | 教训（**"没有轮换就会被自己的去重层彻底堵死"**——任何多输出策略都要留这条） |
| F-04 | `framework-unknown` 知情度卡必须最后生成；破冰态禁止出知情度卡 | `gate/mod.rs:382-388` | 教训（铁律"知情度卡最后生成"） |
| F-05 | 破冰/force 旁路矩阵：旁路 G2 频控与主题冷却、G6 近似指纹；**不旁路** G1 队列、G3 活性、静默期、出稿后正文护栏 | `gate/mod.rs:117-120,442-482` | 打扰机（但"例外必须逐项列举，不能写成总开关"要迁成规矩） |

## G 组：参数总表（目录 v1 不该继承的"魔法数"）

| 常量 | 值 | 出处 | 常量 | 值 | 出处 |
|---|---|---|---|---|---|
| `SCORE_THRESHOLD` | 40 | `gate/mod.rs:18` | `MAX_PENDING` | 3 | `queue/mod.rs:15` |
| `LAST_CARD_WINDOW_SECS` | 25 | `gate/mod.rs:20` | `TTL_SECS` | 7200 | `queue/mod.rs:16` |
| `THEME_COOLDOWN_SECS` | 600 | `gate/mod.rs:22` | `FACTS_MERGE_EVERY` | 20 | `queue/mod.rs:21` |
| `THEME_MUTE_SECS` | 3600 | `gate/mod.rs:24` | `ROLLING_LIMIT` / `ROLLING_MAX_BYTES` | 200 / 512 KiB | `events/mod.rs:14,18` |
| `DEDUP_WINDOW_SECS` | 1200 | `gate/mod.rs:26` | `CONTENT_DEDUP_SECS` / `_MAX` | 5 / 512 | `events/mod.rs:174-175` |
| `ACTIVITY_WINDOW_SECS` | 90 | `gate/mod.rs:28` | `MAX_WORKUNIT_EVENTS` | 200 | `workunit/mod.rs:14` |
| `DECISION_LOG_KEEP` / `_TRIM_AT` | 200 / 400 | `gate/mod.rs:30,32` | `WORKUNIT_KEEP` / `INSIGHT_KEEP` | 100 / 300 | `workunit/mod.rs:15`、`insight/mod.rs:8` |
| `INTERRUPT_CONFIDENCE` | 0.85 | `insight/mod.rs:96` | 截断长度族 | 600/220/180/240/160/120/80/500 字 | `gate/mod.rs:172,148`、`insight/mod.rs:225,384,452,323`、`workunit/mod.rs:213,258` |
| `DECISION_LOG_KEEP` | 200 | `gate/mod.rs:30` | `DECISION_LOG_TRIM_AT` | 400 | `gate/mod.rs:32` |
| `CONTENT_DEDUP_SECS` | 5 | `events/mod.rs:174` | `CONTENT_DEDUP_MAX` | 512 | `events/mod.rs:175` |

协议与输入上限（这批是**事件契约的一部分**，新账本要原样继承或显式改版）：

| 常量 | 值 | 出处 | 作用 |
|---|---|---|---|
| `SCHEMA` | `kvba.event.v1` | `events/mod.rs:9` | 事件契约版本；新仓要带自己的 `schemaVersion` |
| `EVENT_TYPES` | 5 项：`tool.completed`/`tool.started`/`turn.ended`/`message.updated`/`session.ended` | `events/mod.rs:37-43` | 全部路由判据的取值域 |
| `MAX_DIFF_CHARS` | 6000 | `events/mod.rs:11` | 进 LLM 前的 diff 截断（**截断即证据损失**，见 §H） |
| `MAX_INTENT_CHARS` | 500 | `events/mod.rs:12` | intent 截断 |
| `MAX_FILES` | 32 | `events/mod.rs:13` | 单事件文件数上限 |
| `HISTORY_MAX` | 500 | `queue/mod.rs:19` | 卡片历史上限 |
| `PENDING_OPTIONS` | `满意` / `不满意` / `自定义…` | `queue/mod.rs:17` | 用户唯一的三个回答口（M3 复述队列要改这里） |
| `UNSATISFIED_MARK` | `不满意` | `queue/mod.rs:25` | 连续 2 次 → 1h 静默的计数口径 |
| `PROMPT_PENDING_MARK` | `(生成中)` | `queue/mod.rs:23` | 异步产物的占位标记 |
| `TIP_POOL` | 4 项主题池 | `gate/mod.rs:323-328` | 仅服务知识分支，随 F 组退役 |

置信度取值族（每个生产者手写的字面量）：`0.35 / 0.45 / 0.5 / 0.55 / 0.68 / 0.72 / 0.82 / 0.9 / 0.95 / 0.98`。目录 v1 要把它换成"证据等级 → 置信度"的映射表，而不是逐条手写——旧仓曾因为"4 个调用点各写一个 `max_output_tokens`"制造过一桩无解悬案，同一形状的错不要再犯一次。

## H 组：覆盖对照（初判，未跑数）

复盘 §四 记了 38 类真实缺陷形态（2026-09-19 数得：表格 39 行，其中 1 行作废）。下面只是**第一批缺口指认**；完整映射要连同 M0·① 的语料一起做，不能凭这一节就宣布覆盖率。

| 已知缺陷形态 | 今天有没有确定性检测器 | 目录 v1 怎么补 |
|---|---|---|
| 文档写的常量/特性与实现不一致（README 写"队列 5 张"实为 3；写了从未实现的点击穿透） | **无**（靠人肉回扫） | 文档断言 → grep 对拍，对不上即高严重度。旧仓已有同类工具形态：`docs/doc-parity.py`、CI 里的 `matcher === "*"` 断言 |
| 网络请求无超时（Node `fetch` 无 AbortSignal、Rust `blocking` 最坏同步挂十几秒） | **无** | 调用点扫描：HTTP 调用附近无超时参数即命中 |
| 指标只有分子没有分母（`answers += 1` 把跳过也算进去） | **半有**（上一轮补了 `dismissed`） | 规则化：凡计数器有语义相反的兄弟态，必须两侧都计数 |
| 同一判据在两处各实现一遍（G6 与入队护栏口径不同） | **无** | 先作为人审项"一个概念只允许一个函数"；指纹函数被复制的形态可检测 |
| 静默兜底不报来源（模板回填冒充 LLM 稿） | **半有**（`from_llm` + 决策日志已加） | 任何 fallback 分支必须自带可观测标记，否则拒绝出稿 |
| 前端派生值非 computed / 挂载即上报覆盖真值 | **无**，且前端零测试 | 需要新的检测面：前端目前完全不在任何启发式的射程内 |
| 批处理 LF + 非 ASCII 注释、模板里给路径加引号 | **无**（`.gitattributes` 与 CI 断言算半道闸） | 文件属性类规则（换行契约、引号），命中即中严重度 |
| 单元窗口截断丢证据（A-04 超 200 条静默丢最旧） | **无** | 账本完整性规则：任何裁剪必须在产物里留"被裁掉 N 条"的痕 |

## I 组：函数索引（本文所有行号的落点，脚本生成）

用途有两个：任何人按行号跳进去，应落在下面某个函数的定义范围内；以及将来在旧仓删/迁打扰机时，这张表就是定位图。

| 函数 | 定义处 | 函数 | 定义处 |
|---|---|---|---|
| `is_write_event` | `gate/mod.rs:124` | `change_summary` | `insight/mod.rs:135` |
| `has_knowledge_signal` | `gate/mod.rs:130` | `test_gap` | `insight/mod.rs:243` |
| `fingerprint` | `gate/mod.rs:141` | `test_failure` | `insight/mod.rs:311` |
| `fingerprint_text` | `gate/mod.rs:147` | `event_risk` | `insight/mod.rs:350` |
| `branch_of_kind` | `gate/mod.rs:153` | `configuration_decision` | `insight/mod.rs:403` |
| `fingerprint_for_card` | `gate/mod.rs:161` | `build_insight` | `insight/mod.rs:431` |
| `fingerprint_text_for_card` | `gate/mod.rs:167` | `file_evidence` | `insight/mod.rs:461` |
| `text_lower` | `gate/mod.rs:171` | `is_source_file` | `insight/mod.rs:474` |
| `signal_score` | `gate/mod.rs:181` | `is_test_file` | `insight/mod.rs:484` |
| `theme_from_facts` | `gate/mod.rs:301` | `is_decision_file` | `insight/mod.rs:493` |
| `pool_pick` | `gate/mod.rs:330` | `is_completion_boundary` | `workunit/mod.rs:107` |
| `knowledge_candidates` | `gate/mod.rs:341` | `same_session` | `workunit/mod.rs:115` |
| `pick_knowledge_theme` | `gate/mod.rs:358` | `aggregate_at_boundary` | `workunit/mod.rs:130` |
| `knowledge_theme` | `gate/mod.rs:382` | `infer_goal` | `workunit/mod.rs:200` |
| `prefer_theme` | `gate/mod.rs:391` | `is_generic_boundary_intent` | `workunit/mod.rs:217` |
| `dedup_hit` | `gate/mod.rs:401` | `extract_tests` | `workunit/mod.rs:225` |
| `evaluate` | `gate/mod.rs:419` | `status_rank` | `workunit/mod.rs:284` |
| `analyze` | `insight/mod.rs:104` | `changes_from_events` | `workunit/mod.rs:293` |
| `primary` | `insight/mod.rs:123` | | |

## 统计与下一步

**口径**：2026-09-20 由脚本对本文档 `| X-NN |` 行做正则计数得出（非手填）。共 **46 条**规则，分组 A-8 / B-3 / C-10 / D-12 / E-8 / F-5；处置分布 **种子 20（其中标 ★ 的 6 条最该先进目录）** / 结构件 10 / 打扰机 10 / 教训 6。

三点读法：

1. **能进目录 v1 的种子正好 20 条**（C 组 7 + D 组 9 + B 组 3 + E-01/A-07 两个结构判据）——与 RFC-0004 §6·M2 的"20 条规则"量级吻合。M2 不必凭空发明规则，先把这批抄准的拿去做命中数统计。
2. **打扰机占了一多半**（E 组 5、F 组 3、D-11、C-09）。旧仓 25 项门控夹具单测锁的正是这一批；迁的时候**只带判断类夹具**，别把打扰机锁进新仓。
3. 下一步不是写代码，是给这批规则**跑数**：M0·① 的语料 + 每条规则的命中数与真阳率。命中 0 次的种子（例如 D-04 在真实历史里可能一次都不响）在 M2 直接淘汰，不因为"看起来有理"就留在目录里。

> §G 第二张表（协议与输入上限）是自查脚本发现原先漏抄的：`SCHEMA`、`EVENT_TYPES`、`MAX_DIFF_CHARS`、`MAX_INTENT_CHARS`、`MAX_FILES`、`HISTORY_MAX`、`PENDING_OPTIONS`、`UNSATISFIED_MARK`、`PROMPT_PENDING_MARK`、`TIP_POOL`、`DECISION_LOG_TRIM_AT`、`CONTENT_DEDUP_MAX` 这 12 个 `pub const` 首轮没进文档，第二轮回补。"抄完没抄全"这件事本身就该由脚本判，不由眼睛判。
