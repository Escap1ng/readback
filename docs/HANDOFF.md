# 任务交接（HANDOFF）

写于 2026-09-21。给**换会话或换机器**接手的人：这里只放"不看它就接不上"的东西。计划本身在 `PLAN.md`，里程碑判据在 `RFC-0004` §6，需要人 + 网络的步骤在 `BOOTSTRAP.md`——本文不重述它们，只给指针和坑。

## 接手第一步：三条命令定位置

```bash
python docs/m0-inventory-check.py            # 期望：结论:通过，exit 0
python docs/m0-inventory-check.py --self     # 期望：报出多段问题、exit 0，并明说跳过了哪段
python m0/build-corpus.py --seed 7 --repos 20 --full   # 语料是可删重建的派生物，不入库
python m0/replay.py --self                   # 期望：四段负向对照全咬住（约 22s，Windows 上靠只读缓存）
```

```bash
while read -r new want; do got=$(git rev-parse "HEAD:$new"); case "$got" in
  "$want"*) echo "OK   $new";; *) echo "DRIFT $new  文中 $want  实为 ${got:0:16}";; esac
done <<'L'
docs/legacy/README.md 17695a5978ab5b57
docs/legacy/HANDOVER.md b08cc9ebcc8258f8
docs/legacy/复盘与工程约定.md a1cd04d750a61cd1
docs/legacy/InitPrompt.md 3973b172d9e5a8fb
docs/legacy/doc-parity.py 8d7bee8f465a55f5
docs/legacy/rfcs/RFC-0003-workunit-cognition-ledger.md 77f19d76a6901380
L
```

期望 **6 行全 `OK`**。三条命令**全都不需要旧仓、不需要网络**——这就是本轮解耦要买到的东西。任何一条报红而你认为"应该是它错了"，先去改文档，别改判据。

## 本轮改了什么、为什么

| 改动 | 为什么 |
|---|---|
| 立 `docs/PLAN.md`：T0–T6 泳道，每行带复验命令 | 里程碑判据原来只活在 RFC-0004 §6 那一段里，没人能照着走 |
| **T0 四条文档自述缺陷全修**（RFC-0004:76 的"本仓库 47 commits"、四处残留 `kvba` 目标口径、清单 :165 种子拆分加起来 21、:166 "打扰机占一多半"实为 22%） | 这些句子全仓没有一处能自证；自查器当时只查"处置标没标" |
| **自查器改成默认不读旧仓**，并把自述数字纳进断言（总数/分组/处置分布/★/占比与分母/拆分加和，**读不到也算失败**） | 旧仓 `../kvba` 只在这台机器上；把自查绑在它上面 = 换台机器就没人验得了。"读不到也算失败"是防改措辞把检查静默绕开 |
| `LEGACY-MANIFEST` 复验拆两级：第一级单仓自证（带阴性对照），第二级两边对拍降级为"旧仓在位时才做"；本机的绝对路径从文档里撤掉 | 同上。旧仓位置是机器状态，不是仓库契约 |
| M0·① 语料口径改向：主料=自造 20 个含已知缺陷的快照仓库 + 本仓历史，前身仓 47 commits 降为可选加料 | 解耦之后 ① 不再等人和网络，可立刻开工 |
| 建远程仓 `Escap1ng/readback`、`LICENSE`=Apache-2.0、名字占用核验结论落文档（三个候选名全被占） | 见 `BOOTSTRAP.md` §1/§2/§4 |
| 立 `BOOTSTRAP.md` §0 与 §7 | §0：旧仓那 5 条（含导入锚点）还压在本地；§7：转公开前的五条收口清单 |
| T3 做了半程：`m0/build-corpus.py`（18 形态 + 5 类反例，同 seed 可复现）+ `m0/replay.py`（20 条规则写成数据表）→ `docs/replay-baseline.md` | §6 要的验收是"命中数 + **人工核对**的真阳率"。机器判定已出（真阳 84 / 假阳 22 / 未登记 108，precision 79%，坏证据 0），**人工抽 20 条没做**，所以 M0·① 只记半程，不许据此进 M2 |

## 现在卡着的三件事，各自等谁

1. **等网络与人，agent 做不了**：`BOOTSTRAP.md` §0（推旧仓 5 条，解锁全部 `file:line` 指针对外可核性）、§1 剩下三条（`gh search repos`、`gh api /users/readback`、`npm org ls readback`——本机 auto 模式禁外部服务查询）、§5（取那份真实转录）。
2. **等你拍板才能公开**：`BOOTSTRAP.md` §7 那张表。第 1 条最重——`docs/legacy/` 6 份档案来自**仍然私有**的前身仓，公开本仓等于公开那份 60KB 事故集。仓现在就是因此退回私有的。
3. **谁都能接着做、不依赖任何外部条件**：T3 的剩余半步（从 `docs/replay-baseline.md` 抽样表里**人工抽 20 条**写回真阳判定——这是 M0·① 收口的唯一缺口）、T4（M0·③ SQLite 迁移 RFC）、T5（§H 缺口表 → 38 类映射）。目录 v1 该先砍哪条规则，基线已经给了答案：C-02 与 D-03 都是要先重写的（一个太吵，一个分不清"带不带错误处理"）。

## 七个已踩过的坑（省你两小时）

- **`git status` 干净不等于工作区字节干净**。4 份档案在盘上是 CRLF、在库里是 LF（`git ls-files --eol` 看 `w/crlf`），clean 滤镜让状态隐形。别拿工作区 sha256 当判据，本仓判据是 blob 对象号。
- **直连 `github.com:443` 会随机挂**，而 `api.github.com` 照常通。push 失败先探代理再重试，用一次性参数 `git -c http.proxy=http://127.0.0.1:<端口>`，**别写进 git 配置**（端口会变）。
- **检查器必须能红**。新加的任何断言都要配阴性对照：`--self` 那 5 段、档案循环改错一位期望值必须报 `DRIFT`。首跑就全绿的检查器，多半是它自己错了。
- **本机无 `link.exe` / SDK 库** → `cargo test`、`cargo clippy` 只能 CI 验；`cargo fmt` 与 `rustc --emit=metadata` 本机可跑。所以第一个 Rust 提交必须连 CI 三件套一起落，且先证明 CI 能变红（`BOOTSTRAP.md` §6）。
- **git 默认把非 ASCII 路径转成八进制转义**。任何按路径做比对/取内容的脚本都要带 `-c core.quotePath=false`，否则中文文件名对不上、证据核不上，规则会静默变成"永远不命中"。
- **Windows 上"每条命中起一次 `git show`"会慢到跑不完**：第一版回放 4 分钟不结束，给只读查询加一层进程内缓存后 22 秒。写这类工具从一开始就缓存，别等超时。
- **负向对照的夹具必须复用真实 id**：拿一个假 id 的"恒真规则"永远不可能被判成假阳（假阳的定义是"命中了登记为 neg 的文件"），于是负向对照自己成了一条假绿。第一版就是这样骗过了我——四段里两段"没咬住"才发现。

## 一条记要：解耦 ≠ 删指针

`file:line` 与 blob 号继续指向旧仓，那是**取证锚点**，删掉结论就退化成"作者说过"（`RFC-0004:6` 原话）。解耦去掉的是**运行依赖**：不访问旧仓也能把本仓验一遍。还差一步没做到：`M0-rules-inventory.md` 的 G 组仍引用旧事件契约名 `kvba.event.v1`，而 §10 要求新仓带自己的 `schemaVersion`——迁 schema 时一并收掉，别让它以旧名进入新仓。
