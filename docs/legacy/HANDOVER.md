# KVBA 交接报告

> **用途**：30 秒建立全局认知 + 看清"什么还没被证明"。安装与配置一律看 [README](../README.md)，别在这里找步骤。
> **最后核对**：2026-09-18（工作树 `ed8f700`+）。文中每个数字都注明量于何时。
> **本文只写代码里读不出来的东西**：状态、取舍、没做什么、被推翻过什么。

## 0. 本文的写法

1. 状态条目一律带日期与判据；无判据的推测必须写成"猜测"。
2. 已修/已作废的结论不留在正文，移入 §7 变更记录 —— 正文只放还活着的问题。
3. 与 README / [复盘](复盘与工程约定.md) 重复的内容只给指针，不复制一份来腐烂。

## 1. 一句话与一页图

**KVBA（Keep-Vibe-Brot-Away，「项目伴读」）**：Tauri 2 桌面常驻工具，在开发者与 Coding Agent（Claude Code / opencode / Codex）协作的等待间隙递知识卡片、抛思考问题。设计哲学是**防腐拒侵入**——不接管执行，只接管间隙；失败静默降级，永不阻塞 Agent。

```text
宿主（Claude Code hooks / Node 钩子 / JSONL watcher、opencode 插件、Codex notify）
  → 统一「归一化事件」POST 127.0.0.1:<随机端口>/kvba/events（握手 token，仅回环）
  → Rust 核心：events → workflow 路由 → workunit 收口 → insight(带证据) → queue
                兼容支路：gate G1~G7 → llm 出稿（手动「来一道」与 JSONL watcher）
  → 悬浮胶囊（48×48 圆点）：普通洞察只入队，仅高置信高风险主动展开
TS 前端（Vue 3）：CapsuleDot / CapsulePanel / SettingsView（设置·历史·决策日志）
```

队列上限 `MAX_PENDING = 3`；每次门控与投递决策都写决策日志，可在面板看层级与拒绝原因。

## 2. 模块地图

| 模块 | 位置 | 一句话职责 |
|---|---|---|
| WorkUnit 聚合 | `src-tauri/src/workunit/` | **自动出卡主路径**：以 `turn.ended`/有效 `session.ended` 收口一个回合；`git.rs` 以 `diff --numstat HEAD` 读工作区快照，失败降级为事件声明的文件证据。`tests[].status` 只由 `excerpt.exitCode` 决定，**采不到一律 `Unknown`** |
| 证据化 Insight | `src-tauri/src/insight/` | 确定性生成 `explain`/`test-gap`/`risk`/`decision`，每条必须含 `conclusion + evidence + suggestedAction + confidence`；`primary()` 按 risk→decision→test-gap→explain 选一条投影。**`P1` 唯一生产者**＝"本回合有测试命令非 0 退出"；投递判据只在 `insight::interrupts()` 一处 |
| 链路编排 | `src-tauri/src/workflow.rs` | 三分支：`WorkUnit`（有回合边界）/`LegacyWatcher`（仅 claude-code-watcher，走完整门控）/`AwaitBoundary`（普通工具事件只攒窗口） |
| 兼容门控 | `src-tauri/src/gate/` | G1 队列 → G2 频控 25s/冷却 10min → G3 活性 → G4 路由 → G5 信号分（阈值 40，只算写事件）→ G6 正文去重 20min → G7 放行。2026-09-06 起降级为兼容支路，25 项夹具单测 |
| 事件摄入 | `src-tauri/src/events/` | 落盘与 `emitter` 无关的内容指纹 5s 判重；`events.log` 条数 + 字节双上限滚动 |
| 记忆层 | `src-tauri/src/memory/` | 项目 facts（扫 package.json/README，一次 LLM ≤50KB，消费 ≥20 条或会话结束才增量合并）+ 对话窗口（3 条 ≤3KB，零 LLM） |
| LLM | `src-tauri/src/llm/` | 三 provider + SSE；**不下发 max_tokens**（Anthropic 强制，`ANTHROPIC_REQUIRED_MAX=8192`）；输入侧 `fit_tokens ≤3.5k`；每日预算与连败冷却 |
| 加密 | `src-tauri/src/crypto/` | AES-256-GCM，密钥 = HKDF-SHA256(机器指纹)；密钥永不离开本机，文件损坏只降级不 panic |
| 队列/HTTP/窗口/托盘 | `queue/` `http/` `windows.rs` `tray.rs` | 卡片状态与出稿来源分账、本机端点、胶囊窗口、托盘驻留 |
| 前端 | `src/components/` | 三态由 Rust 事件驱动（`card.new`/`panel:show`），前端零轮询 |
| 适配器 | `adapters/` | claude-code（Rust bridge + watcher）、claude-code-hook（Node mjs 零编译）、opencode-plugin（TS）、codex-notify（Node mjs） |

**特色机制**：会话开场破冰（每会话首评放行一张贴士，旁路频控/冷却/G6，**不旁路**队列上限与静默期）；静默期 1h 是用户唯一否决权，永不放宽；知情度卡必须最后生成。

## 3. 技术栈

Rust 后端（Axum 本地 HTTP、Reqwest + SSE、aes-gcm/hkdf、tauri-plugin-log）· Tauri 2（托盘/自启动/通知/剪贴板）· Vue 3 + TS + Vite 6 · GitHub Actions 三平台矩阵（`fmt`/`clippy -D warnings`/`vue-tsc`/`cargo test --locked` 全部阻断）+ tag 触发三平台打包。

## 4. 动手前必须知道的七条

1. 先读 [复盘与工程约定.md](复盘与工程约定.md) 的前言 5 条 + §六 铁律 + §八 未闭合——铁律优先于任何新特性。
2. **每次保存都是部署**：跨文件签名改动要把签名 + 全部调用点 + 测试写进同一次编辑；落盘前先 `cargo check`（在有工具链的机器上）。
3. **禁止静默吞错**：诊断必须能证伪它自己至少两个候选假设；健康指示器必须带计数与新鲜度。
4. **结论分级**：静态审计 < 单测 < 实测，后两类不许写成第一类。最危险的是否定性断言（"肯定没问题 / 从没运行过 / 它不存在"）。
5. **改完关键契约（字段名、命令注册、serde 别名）必须 `grep` 复验**，别信一次编辑的返回值。
6. CI 全部门禁都是阻断项：`cargo fmt --check`、`cargo clippy -- -D warnings`、`vue-tsc`、`cargo test --locked`，外加适配器 `node --check` 与配置模板校验。
7. `adapters/opencode-plugin/kvba-plugin.ts` 是正本，`.opencode/plugins/` 是部署副本，**CI 校验两者一致**；提交信息用 `feat:`/`fix:`/`refactor:`/`docs:`/`chore:`。

## 5. 当前状态（v0.2.0，2026-09-18）

- 里程碑主体完成：事件摄入、队列、门控、WorkUnit + Insight、记忆层、LLM 出稿、加密、胶囊 UI、三平台 CI/发布。
- 测试 **117 个函数**（113 `#[test]` + 4 `#[tokio::test]`，主程序与 claude-code 适配器合计；2026-09-18 当日量得）。**沿革**：本报告旧版写"全库 72 项"，当日复核为 100（96 `#[test]` + 4 `#[tokio::test]`），本轮之后才是 117 —— 记数必须写"何时量于哪个 crate"。
- 节奏参数 2026-09-03 按实测放宽（频控 25s、冷却 10min、去重 20min），新增开场破冰。
- 适配器矩阵 3 路宿主 4 个适配器；原第 4 路宿主已于 2026-09-18 下线（目录删除、CI 收窄、`agent_family` 去分支）。
- **端到端 LLM 出稿已通**：`stats.json` 为 `cardsLlm:5 / cardsTemplate:0`，`decision-log.jsonl` 四条 `G7 pass=true …(LLM 出稿)`（2026-09-03 19:35–19:38）。
- **但"链路通"不等于"内容可信"**：`history.json` 11 张真实发卡里，5 张真 LLM 稿有 2 张含可证伪的错误断言（详见 §6 第 5 条）。

## 6. 未闭合（按优先级；修掉的移入 §7）

| # | 缺陷 | 判据 / 下一步 |
|---|---|---|
| 1 | `force`（来一道）在空队列时仍被正文去重挡住，用户觉得"点了没反应" | 放开须给 `insert_card` 传「用户主动索要」标志并记入决策日志，不得做静默特例 |
| 2 | **本机无工具链的环境风险**：`fmt`/`clippy` 只在 Windows 压到 0 告警，Linux/macOS 专属路径（`crypto::machine_id()`）本地编译不到 | `crypto` 的加解密回环测试故意挂 `#[cfg(target_os = "windows")]`——因为另两条平台分支从没编译过，不要为了"多一处覆盖"放开到全平台；红了解 lint，别回退门禁 |
| 3 | opencode 插件 `tsc --strict` 只在 CI 验（本机无 SDK 类型） | 依赖 SDK 类型的新字段一律显式 `as` + 可选链（本轮 `exitCodeOf` 就是这么写的） |
| 4 | 双路同报**必然**判重失败：`intent` 参与内容指纹，而 bridge 对 Edit 产 `修改 {file}:{old_string}`、Node 钩子产 `编辑 {file}` | 与两份 sample 声称的"功能等价"相反；后果被 G5-A 放大（写事件双报抬高信号分→更易出卡）。修法是先统一 intent 口径，不是加阈值 |
| 5 | **LLM 稿件零事实校验**：路径、行数、"项目里有 X 文件"等断言出卡前不对本地仓库核对 | 实测：卡[07] 称 `gate/mod.rs` 508 行（该提交实为 879），又称存在 `src/demo/VibeCounter.tsx`（全历史从未存在）。RFC-0003 的 `evidence` 正是为此设计，但 `build_insight` 只有 `debug_assert!(!evidence.is_empty())`——release 下不校验 |
| 6 | 没有任何宿主确认会填 `excerpt.exitCode` | 协议与核心已就位；判据见复盘 §八 第 9 条。它只认适配器从宿主 `tool_response` 读到的结构化字段（`exitCodeOf`），而 Codex 与 JSONL watcher **结构上不可能**提供。若全为 `unknown`，去查宿主真实字段名，**不要调低 `interrupts()` 门槛** |
| 7 | `P0` 在洞察路径无生产者 | `RiskLevel` 只产 `Info`/`P2`/（本轮新增）`P1`，所以 WorkUnit 卡永远走不到队列替换分支；旧门控路径**有** P0（`gate::scoring.p0` → 卡片 severity），因此 `p0ReplaceQueue` 不是假开关。闭合前须先回答"什么算 P0"（产品判断） |
| 8 | `release.yml` 不依赖 CI | `release.needs: build`，只校验版本一致 → **CI 红灯的 tag 照样上架**。可选修法是 `workflow_run` 触发或加一步等 CI 成功，但需一次真实 tag 验证 |
| 9 | `gate/` 与 `insight/` 双轨并存 | 两套冷却/去重/打分，谁赢取决于 emitter；WorkUnit 卡不进门控却照样占 `MAX_PENDING`、刷 `last_card_at`、`touch_asked` —— 静默摘要与主动审查抢同一份预算 |
| 10 | 铁律 1「绝不阻塞 Agent」在两处不成立 | `claude-code-hook`/`codex-notify` 的 `fetch` 全无超时；Rust `post_event` 用 `reqwest::blocking` 最坏约 12.6s 而 sample 配 `timeout: 3`；`codex-notify` argv 为空时回退 `readFileSync(0)` 无超时 |

## 7. 变更记录（不静悄悄删，也不留在正文误导人）

| 日期 | 条目 | 之前 → 之后 | 依据 |
|---|---|---|---|
| 2026-09-18 | 端到端出稿未验证（曾是最高优先） | 未验证 → **已通** | `stats.json` 新结构 + 四条 `G7 pass=true(LLM 出稿)` |
| 2026-09-18 | `parse_contract` 返回 `Option`，截断与契约不符不可分 | → 两态 `ContractParseErr`（`Unclosed` / `Shape`，facts 与卡片共用）；旧名 `FactsParseErr` 保留为类型别名，以免改写复盘文档里的历史引用 | `llm/mod.rs` |
| 2026-09-18 | `events.log` 无字节上限（实测 154KB/2 条） | → 条数 + 字节双上限 `ROLLING_MAX_BYTES=512KB`，超预算丢最旧、**至少保留一条**；纯函数 `select_log_lines` + 三项单测 | `events/mod.rs` |
| 2026-09-18 | `stats.answers` 把"手动跳过"计成回答，使 §1.5 度量不可证伪 | → 终态分账 `answered`/`dismissed`，面板与 `模板兜底` 一样并列显示。**注**：本机 `history.json` 11 张卡全部 `status=answered`、跳过 0 行，故属可证伪性修补而非数据修复 | `state.rs::note_card_closed` |
| 2026-09-18 | 第 4 路宿主适配器下线 | → 目录删除、`.gitignore` 与 CI 收窄、README/规格/本报告去名。**磁盘上残留的历史 `events.log` 仍带该 emitter，未清理**（未知 emitter 退回原始名，分组与指纹自洽） | `refactor(adapters)!` 提交 |
| 2026-09-03 | 磁盘清理共 564 MB：`adapters/claude-code/target/`（564 MB）、`dist/`（0.1 MB）、`docs/codebase-research.md`（0.03 MB） | 前两者可再生：`cargo build`（在 `adapters/claude-code` 下）/ `npm run build`；后者是一次性研究报告，结论已沉淀进本报告与复盘，避免双份维护过期，可从 `git log -- '*codebase-research*'` 取回 | 原 §9 |
| 2026-09-03 | 甄别后**保留**（非冗余）：`node_modules/`（`npm ci` 可重建，不属仓库内容）、根 `target/`（含 kvba-data 运行时数据，体积小）、`.opencode/plugins/kvba-plugin.ts`（与源文件哈希一致、CI 强制校验的部署副本） | 不变 | 原 §9 |

## 8. 数据、日志与文档索引

- 运行时数据 `%APPDATA%\dev.kvba.app\`（`endpoint/settings/queue/history/cooldown/budget/stats/secrets.enc` + `projects/<key>/{events.log,facts.json,work-units.json,insights.json}`），细节见 README。
- 日志**不在**上面那个目录：`%LOCALAPPDATA%\dev.kvba.app\logs\KVBA.log`——排查静默失败先看它。
- [README](../README.md) 安装/四种接法/端点发现 · [InitPrompt.md](InitPrompt.md) 原始规格 · [RFC-0003](rfcs/RFC-0003-workunit-cognition-ledger.md) 架构升级 · [复盘与工程约定.md](复盘与工程约定.md) **必读** · `.github/workflows/` ci.yml / release.yml
