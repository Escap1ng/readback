# 遗留资产清单（`docs/legacy/`）

从前身仓库 KVBA v0.2.0 导入的**只读档案**。导入锚点：旧仓 `main` 的 `ddcbf4f`。旧仓在本机的目录位置**不写进本文档**——那是机器状态，不是仓库契约；需要两面对拍时现场确认（见第 4 节第二级）。

## 铁规则

1. **`docs/legacy/` 下的文件一律不改。** 要修正内容 → 在旧仓改、提交，再重新导一次并重算下面的哈希。就地编辑副本会把"档案"变成"另一份维护中的文档"——旧仓复盘 §四 第 21 行记的就是这么来的（README 改版删小节，把生效路径变成了孤岛）。
2. **副本必须与旧仓提交逐字节同一（以 git blob 对象号为准）。** 复验命令见第 4 节；对不上就是有人在两边各改了一半。不要拿工作区字节的 sha256 当判据——那会随检出机器的 `core.autocrlf` 漂。
3. 旧仓转只读遗产，不再往它提新特性；但**它的工作区不能被清空**（下表"留在旧仓"栏），因为删掉就等于毁掉唯一的可编译参考实现，而这个仓库还有别人的提交。

## 已导入（blob 对象号，2026-09-20）

| 文件 | 字节 | git blob（旧仓 = 新仓） | 为什么值得留 |
|---|---|---|---|
| `复盘与工程约定.md` | 59896 | `a1cd04d750a61cd1` | **最值钱的单一文件**：§六 铁律、§四 38 类真实缺陷形态（目录 v1 的种子语料）、§八 未闭合清单。§H 那张缺口表就是从它推的 |
| `HANDOVER.md` | 12912 | `b08cc9ebcc8258f8` | 交接视角的现状与"已知问题及解决方案"，含 LLM 稿件 2/5 含假事实的那次实测记录 |
| `rfcs/RFC-0003-workunit-cognition-ledger.md` | 6807 | `77f19d76a6901380` | 数据模型与回合边界的原始决策；RFC-0004 §4 继承的就是它，引用要能在本地闭合 |
| `InitPrompt.md` | 29368 | `3973b172d9e5a8fb` | 原始规格：问题定义、七层门控的设计动机、里程碑与待决事项。解释"为什么长这样" |
| `README.md` | 19400 | `17695a5978ab5b57` | 四路接线的**成本证据**（RFC-0004 §2.3 首行引用 `README.md:80-182`）：没有它，那些"首卡 5+ 步"的结论只剩作者说法 |
| `doc-parity.py` | 6447 | `8d7bee8f465a55f5` | 防丢事实对拍器（带 `--self` 负向对照）。§H 认定"文档断言与实现对拍"是目录 v1 该收的第一批规则之一——工具形态已经在它身上验证过 |

口径为什么是 blob 而不是文件 sha256：这台机器 `core.autocrlf=true`，复制出来的工作区字节带 CRLF，而本仓 `.gitattributes` 强制 `eol=lf` ——**字节哈希会随谁在哪台机器上检出而变**，正应了旧仓复盘 §四 第 15 行那条教训（"换行符契约属于仓库，要靠 `.gitattributes` 固定"）。blob 对象号两边相同即内容同一（已逐份验过 6/6 全 SAME）。

导入后新仓的自查与清单类文件仍留在原位：`docs/M0-rules-inventory.md`、`docs/m0-inventory-check.py`、`docs/RFC-0004-mass-market-ledger.md` 是**本仓的工作物**，不是档案。

## 留在旧仓（有意不迁）

| 资产 | 为什么不迁 | 什么时候迁 |
|---|---|---|
| `src-tauri/src/insight`、`workunit` 及其 109 项单测 | 单独抠出来在新仓不可编译（crate、tauri 依赖、`state.rs` 全部要一起搬）；搬成一堆读得懂但跑不动的文件，等于把资产换成负债 | M1 建 crate 时连测试一起迁，测试先行落地 |
| `gate/` 的启发式**代码** | 判据已经被 `M0-rules-inventory.md` 抄准；代码里一多半是打扰机（E/F 组），迁过来只会诱导继续调阈值 | 只迁种子类，形态按目录 v1 重写 |
| `adapters/` 4 路与 `*.sample.*` 模板 | 依赖旧仓的 CI 校验（模板即产品那条断言）；单独复制会失去守门 | M1 若保留实时增强档，随新 CLI 的安装器一起给 |
| `.github/workflows/` | 新仓现在没有可跑的东西；先建工作流就是造恒绿（`BOOTSTRAP.md` §6） | 第一个 `cargo init --lib` 提交时，与 fmt/clippy/test 三件套同批 |
| `%APPDATA%\dev.kvba.app\` 运行数据 | 不在仓库里，且是唯一记录着真实历史事件与决策日志的地方（RFC-0004 §2.3 的两条计数就来自它） | 永不搬迁；M0 取样只读不写 |

## 复验（分两级；第一级不需要旧仓）

### 第一级 · 本仓自证（默认，随时可跑）

上面那张表的 6 个 blob 对象号就是契约。只要新仓侧等于它，档案就没被就地改过——**这一级不碰旧仓、不碰网络**，在任何一台 clone 上都能跑：

```bash
while read -r new want; do
  got=$(git rev-parse "HEAD:$new")
  case "$got" in "$want"*) echo "OK   $new";; *) echo "DRIFT $new  文中 $want  实为 ${got:0:16}";; esac
done <<'L'
docs/legacy/README.md 17695a5978ab5b57
docs/legacy/HANDOVER.md b08cc9ebcc8258f8
docs/legacy/复盘与工程约定.md a1cd04d750a61cd1
docs/legacy/InitPrompt.md 3973b172d9e5a8fb
docs/legacy/doc-parity.py 8d7bee8f465a55f5
docs/legacy/rfcs/RFC-0003-workunit-cognition-ledger.md 77f19d76a6901380
L
```

判据：**6 行全 `OK`**。任一行 `DRIFT` = 有人在两边之间又改了一次，或本表忘了更新——按第 1 节铁规则处理，别顺手"改回看起来对的样子"。

为什么这一级要设成默认：旧仓那个锚点提交 `ddcbf4f` **至今不在任何远程上**（2026-09-21 实测；推它这一步写在 `BOOTSTRAP.md` §0）。把复验绑在旧仓上，等于把"档案没被改过"这件事绑在一台机器上——换台机器就没人验得了。

### 第二级 · 两边对拍（只在旧仓在位时做）

它证明的是另一件事：**新仓这份副本与旧仓那次会议上的对象仍是同一个**（重新导入、或怀疑两边各改了一半时才有必要）。`../kvba` 只是本机默认位置，不是契约：

```bash
while read -r old new; do
  a=$(git -C ../kvba rev-parse "HEAD:$old"); b=$(git rev-parse "HEAD:$new")
  [ "$a" = "$b" ] && echo "SAME $new" || echo "DIFF $new  old=$a new=$b"
done <<'L'
README.md docs/legacy/README.md
docs/HANDOVER.md docs/legacy/HANDOVER.md
docs/复盘与工程约定.md docs/legacy/复盘与工程约定.md
docs/InitPrompt.md docs/legacy/InitPrompt.md
docs/doc-parity.py docs/legacy/doc-parity.py
docs/rfcs/RFC-0003-workunit-cognition-ledger.md docs/legacy/rfcs/RFC-0003-workunit-cognition-ledger.md
L
```

判据：6 行全 `SAME`。两级各自实测过：第一级 2026-09-21 全 `OK`；第二级 2026-09-20、2026-09-21 各跑一次均全 `SAME`。比对的是**提交对象**而不是工作区字节，所以不受各人 `core.autocrlf` 影响。

`legacy/doc-parity.py` 是旧仓的工具，要在**旧仓根目录**跑（它按 `docs/HANDOVER.md` 与 `README.md` 的相对路径找文件）；在新仓直接运行会因为找不到 HANDOVER 而报一堆假缺失——这正是"档案不改、路径不假装"的理由，也是它作为档案留在这里、而不被接进本仓自查的原因。
