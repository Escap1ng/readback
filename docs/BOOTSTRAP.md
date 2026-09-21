# BOOTSTRAP — 需要人来跑的步骤

这里列的是**必须由你在自己的终端执行**的联网与账号动作。每条给出：命令 → 它在证明什么 → 请把什么带回仓库。Agent 沙箱不做这些事（前一个项目已证明：沙箱里启动产品会造出一个写不了数据目录的残缺实例，再把环境问题误读成产品缺陷）。

## 0. 先把旧仓那 5 条推上去（证据锚点是单点的）

排在建仓之前的理由：`README.md:25`、`RFC-0004:6`、`LEGACY-MANIFEST.md:3` 三处都承诺"旧仓 `ddcbf4f` 及之前可按行号取到原文"，而 2026-09-21 实测**这个对象不在远程 `main` 上**——远程 `main` = `ed8f700`（`ls-remote` 与本地缓存一致），本地领先 5 条、远程无独有提交，是纯 fast-forward。不推，全部 `file:line` 指针就只在这台机器上成立。

```bash
git -C ../kvba fetch origin
git -C ../kvba rev-list --count HEAD..origin/main    # 必须 = 0；非 0 说明远程被别人动过，先合再推，别硬推
git -C ../kvba push origin main                       # 5 条，含锚点 ddcbf4f 与那条 clippy 修复 1b6a2c6
```

- 证明什么：`git -C ../kvba merge-base --is-ancestor ddcbf4f origin/main` 的退出码从非 0 变 **0**。
- 带回什么：这一条命令的退出码，以及推完后 GitHub Actions 那次 CI 的颜色（`1b6a2c6` 修的正是被 `-D warnings` 挡住的三处 `.err().expect()`，`RFC-0004:147` 挂着的"最后一次红 CI"要靠它闭合）。

## 1. 名字占用核验（先于建仓）

```bash
npm view readback name version            # 404 = npm 裸名可用
cargo search readback --limit 20           # 列表里没有同名 crate = 可用
gh search repos readback --limit 20        # 看是否有同域同名项目（尤其 AI/代码审查类）
gh api /users/readback --jq .login         # 404 = 该用户名/组织未被占
```

- 证明什么：三处命名空间能否拿到，以及会不会被读成某个已有项目的仿作（`claude-receipts` 就是因为这个被弃用，见 RFC-0004 §10）。
- 带回什么：四条命令各自的结果。裸名被占 → 采用作用域名 `@readback/cli`，**仓库名与二进制名不变**；若 GitHub 上已有同域同名且活跃的项目 → 停下来重议名字，别共存。

### 结果（2026-09-21 实测；前两条本机跑得出，后两条被沙箱策略挡住）

| 核验 | 命令 | 结果 | 处置 |
|---|---|---|---|
| npm 裸名 | `npm view readback name version description` | **已占**：`0.0.0-alpha.10`，航空管制通话转写（`borisdiakur/readback`，keywords `atc`/`aviation`/`vatsim`/`ivao`） | 不同域，不构成仿作；退作用域名 |
| crates.io | `cargo search readback --limit 20` | **已占**：`readback = "0.0.0"`，Tauri IPC 库的占名预留（描述原文 "This release reserves the crate name"） | crate 名改 `readback-cli`（实测未占）。§3 不做⑥ 本就不走 `cargo install`，所以这条不挡 M1 |
| GitHub 同名项目 | `gh search repos readback --limit 20` | **未做**——本机 auto 模式禁止外部服务查询 | 你来跑。命中同域且活跃的项目 → 停下重议名字 |
| GitHub 用户名/组织 | `gh api /users/readback --jq .login` | **未做**，同上 | 你来跑。404 = 未被占 |
| 作用域名能不能拿到 | `npm view @readback/cli version` → 404；`npmjs.com/~readback` → 403 | **未验证**：404 只说明这个包不存在，不说明 `@readback` 这个 scope 拿得到——它取决于 npm 上有没有叫 `readback` 的用户/组织，而那个页面本机 403 | 你登录后跑 `npm org ls readback`。拿不到 scope → 用 `@<你的用户名>/readback`，仓库名与二进制名仍不变 |

两个备选名也一并查了（`RFC-0004:131`）：`blindspot` 在 npm（扫 Node 项目缺哪些常用工具的 DX CLI）与 crates.io（装/更新单二进制应用的安装器）**双双被占，且两处都是同域**，按 §10 判据 ④ 出局；`witness` 在 npm（0.0.2，词典义占位）与 crates.io（0.3.0，文件监视器）也双双被占。**三个候选全灭**，`readback` 靠"作用域名 + crate 改名"活下来，仓库名与二进制名不变。结论已写进 `RFC-0004` §10 的引用块，原来那句"本机无法定论"作废。

## 2. 建远程仓并推送

```bash
gh repo create readback --public --source=. --remote=origin --push
```

- 证明什么：本仓首次成为可被他人 clone 的东西。
- 带回什么：仓库 URL。
- 原文写的是 `--private`「直到第 4 条（license）有结论」；**2026-09-21 license 已定 Apache-2.0（见 §4），故改为公开建仓**。仓名仍用 `readback`：GitHub 仓名在用户命名空间下（`Escap1ng/readback` 实测不存在），不受 npm/crates.io 占用影响——§1 的处置本就是"仓库名与二进制名不变"。
- 建仓前仍需你跑 §1 那两条被沙箱挡住的核验（`gh search repos readback`、`gh api /users/readback`）；若命中同域且活跃的同名项目，按 §1 停下重议。

## 3. 签名与公证询价（决定 M1 的形态）

- Windows 代码签名证书（OV/EV）、Apple Developer 账号 + notarization，各自问清**年费、签发周期、是否需要 USB Key 或硬件令牌**。
- 证明什么：M1「两台干净机器 ≤3 分钟看到首份报告」这条验收在财务上是否成立。
- 带回什么：三个数字（价格、周期、硬件要求）。拿不到预算 → 按 RFC-0004 §8 的退出判据，砍掉安装包，只发 CLI + GitHub Action。

## 4. License 决定

**已定（2026-09-21）：Apache-2.0。** `LICENSE` 已入库。

- 取证（不是默写）：从 `https://www.apache.org/licenses/LICENSE-2.0.txt` 取原文，11358 字节、纯 ASCII、0 个 CR 字节（与本仓 `.gitattributes` 的 `eol=lf` 一致）、sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`。交叉验证：本机 cargo registry 里 `aead-0.5.2`、`aes-0.8.4` 两份独立发布的 `LICENSE-APACHE`，归一化空白后**词序列与官方原文逐词相同**（各 1581 词）；`adler2-2.0.1` 仅头部 URL 写法不同（`http://…/licenses/` vs `https://…/LICENSE-2.0`）。结构自查：9 条编号条款齐全，APPENDIX 在第 179 行。
- 复验：`sha256sum LICENSE` 应等于上面那串；`git ls-files --eol LICENSE` 应为 `w/lf`。
- 边界怎么划：M4 的团队治理付费面**不靠 license 卡**，靠托管/服务端收——这样 `RFC-0004` §8「撑不开就退成纯账本」那条退路不必重谈授权。
- 原文那句"在那之前 README 不提开源"随之作废：现在 README 可以写明 Apache-2.0。
- 遗留一条：APPENDIX 里的 `Copyright [yyyy] [name of copyright owner]` 是模板占位，`LICENSE` 本身按惯例保持原文不动；真正的版权行等 M1 有代码时写进源文件头或 `NOTICE`。

## 5. M0·② 的取样：转录里到底有没有退出码

在自己的终端跑（只读，不改任何文件）：

```bash
ls -1 "$HOME/.claude/projects" | head          # 有没有会话目录
head -c 2000 "$(find "$HOME/.claude/projects" -name '*.jsonl' | head -1)"   # 结构长什么样
```

- 证明什么：`tool_result` 那一类消息里是否带可解析的退出码 / `is_error`。判据是「≥90% 的 shell 类调用能取到 0/非 0」。
- 带回什么：**结论 + 一条脱敏样本的字段名清单**（不要带回原文）。真实转录含私有内容，`.gitignore` 已经把语料目录挡住了，别绕过它。
- 若这一条判据失败：RFC-0004 §8 已写好退路（L1 退 git-only），不需要重开讨论。
- 取样前提（2026-09-19 本机实测）：这台机器的 `$HOME` 下**没有 `.claude` 目录**，前一个项目留下的 12 条事件里也只有 0 条带 exitCode。所以样本要从真正跑过 agent 的那台机器取——这也是 M0 被排在一切新功能之前的原因：**我们至今没有任何证据说"零接线也能拿到验证证据"，它仍然只是一个假设。**

## 6. 工作流（CI）刻意还没建

没有代码就没有 CI。第一个提交如果是 `.github/workflows/` 而没有可跑的测试，它就恒绿——恒绿的检查器不是证据，是噪音（前一个项目为此写过整节复盘）。等第一个 `cargo init --lib` 的提交落地时，再一次性带上 fmt / clippy `-D warnings` / test 三件套，并且**先证明它能变红**。
