# BOOTSTRAP — 需要人来跑的步骤

这里列的是**必须由你在自己的终端执行**的联网与账号动作。每条给出：命令 → 它在证明什么 → 请把什么带回仓库。Agent 沙箱不做这些事（前一个项目已证明：沙箱里启动产品会造出一个写不了数据目录的残缺实例，再把环境问题误读成产品缺陷）。

## 1. 名字占用核验（先于建仓）

```bash
npm view readback name version            # 404 = npm 裸名可用
cargo search readback --limit 20           # 列表里没有同名 crate = 可用
gh search repos readback --limit 20        # 看是否有同域同名项目（尤其 AI/代码审查类）
gh api /users/readback --jq .login         # 404 = 该用户名/组织未被占
```

- 证明什么：三处命名空间能否拿到，以及会不会被读成某个已有项目的仿作（`claude-receipts` 就是因为这个被弃用，见 RFC-0004 §10）。
- 带回什么：四条命令各自的结果。裸名被占 → 采用作用域名 `@readback/cli`，**仓库名与二进制名不变**；若 GitHub 上已有同域同名且活跃的项目 → 停下来重议名字，别共存。

## 2. 建远程仓并推送

```bash
gh repo create readback --private --source=. --remote=origin --push
```

- 证明什么：本仓首次成为可被他人 clone 的东西。
- 带回什么：仓库 URL。先保持 `--private`，直到第 4 条（license）有结论。

## 3. 签名与公证询价（决定 M1 的形态）

- Windows 代码签名证书（OV/EV）、Apple Developer 账号 + notarization，各自问清**年费、签发周期、是否需要 USB Key 或硬件令牌**。
- 证明什么：M1「两台干净机器 ≤3 分钟看到首份报告」这条验收在财务上是否成立。
- 带回什么：三个数字（价格、周期、硬件要求）。拿不到预算 → 按 RFC-0004 §8 的退出判据，砍掉安装包，只发 CLI + GitHub Action。

## 4. License 决定

- 前一个仓库没有 `LICENSE` 文件，所以这里也没有继承过来。公开之前必须定：核心开源 + 团队功能商业化的边界写在哪一层。
- 带回什么：一句话结论 + `LICENSE` 文件本身。在那之前 README 不提"开源"。

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
