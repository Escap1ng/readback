# 人工抽核工作单（M0·① 的另一半）

`docs/replay-baseline.md` 里的 79% 是**机器判定**——机器只知道自己登记过的 pos/neg。
§6 的验收要的是「人工核对的真阳率」，所以这张表由**你**填，不由我填。

**怎么填**：最后一列写 `真`（确实是该抓的缺陷）/ `误`（不该抓，是误报）/ `待定`。
填完跑 `python m0/replay.py --audit-check` 核对，再 `python m0/replay.py --write`
把人工结论折回基线报告。**一条都别替我勾**——这 20 条的价值就在它是别人看的。

抽样规则：seed=7，每条规则各 1 条（20 行）。摘录已直接抄在下面，
判定不依赖 `m0/corpus/` 还在不在；坐标留着供你想看上下文。

| # | 规则 | 名称 | 机器判定的桶 | 仓库 | 提交 | 文件:行 | 摘录 | 判定 |
|---|---|---|---|---|---|---|---|---|
| 1 | C-02 | 改源未改测 | 未登记 | repo-08 | 530b7633 | `src/pull.rs:1` | `pub async fn pull(u: &str) -> Result<String, Error> {` |  |
| 2 | C-04 | 外部调用无错误分支 | 真阳 | repo-05 | 907fdb6a | `src/fetch.rs:1` | `use reqwest; // 新增外部调用` |  |
| 3 | C-05 | 决策文件变更 | 真阳 | repo-09 | 31c7525f | `Cargo.toml:1` | `[package]` |  |
| 4 | D-01 | 大改 ≥20 行 | 未登记 | repo-20 | 6895abc2 | `src/core.rs:1` | `pub fn handle(x: i32) -> i32 {` |  |
| 5 | D-02 | 中改 8..20 行 | 未登记 | repo-01 | ec5def60 | `src/agg.rs:1` | `pub fn run(data: &[u8]) -> u8 {` |  |
| 6 | D-03 | 新增外部调用 | 假阳 | repo-02 | 02a1803f | `src/pull.rs:2` | `match reqwest::get(u).await {` |  |
| 7 | D-04 | 异常路径未见保护 | 真阳 | repo-20 | bb07784c | `src/agg.rs:2` | `panic!("no data");` |  |
| 8 | D-05 | 遗留标记 | 真阳 | repo-01 | 8158c410 | `src/parser.ts:2` | `// TODO: 处理转义` |  |
| 9 | D-06 | 删除代码文件 | 真阳 | repo-16 | 175c9b6a | `src/legacy.py:1` | `def old():` |  |
| 10 | D-07 | 裸 throw | 真阳 | repo-20 | 0bf73d90 | `src/client.js:2` | `if (!p) { throw new Error('no path'); }` |  |
| 11 | D-08 | 影响面 ≥3 文件 | 真阳 | repo-01 | a66d2dba | `src/a.rs:1` | `pub fn a() {` |  |
| 12 | D-09 | 纯格式化 | 真阳 | repo-12 | 5d473000 | `src/util.py:1` | `def f(a, b):` |  |
| 13 | D-10 | 纯文档 | 未登记 | repo-03 | 847a87f0 | `docs/guide.md:1` | `# 指南` |  |
| 14 | G-01 | 文档断链 | 真阳 | repo-01 | d84a39be | `README.md:3` | `见 [架构说明](docs/arch-v2.md)。` |  |
| 15 | G-02 | 文档数字与常量漂移 | 真阳 | repo-01 | 6a4758a7 | `README.md:3` | `队列最多 5 张，超出即丢弃。` |  |
| 16 | G-03 | 无 eol 规则 | 未登记 | repo-07 | 5674b060 | `<repo>:None` | `提交 5674b060 的全树里查该属性` |  |
| 17 | G-04 | .cmd 用 LF+非 ASCII | 真阳 | repo-12 | 2611617e | `dev.cmd:2` | `rem 构建前端` |  |
| 18 | G-05 | 凭空生成的数字文件名 | 真阳 | repo-01 | bfb1d6db | `18:1` | `(空文件)` |  |
| 19 | G-06 | 计数器只算一侧 | 真阳 | repo-02 | a0e16500 | `src/stats.rs:1` | `pub struct Stats { pub answers: u32, pub dismissed: u32 }` |  |
| 20 | G-07 | 清除写成赋空串 | 真阳 | repo-01 | 04fba6e8 | `src/keyring.rs:7` | `pub fn forget(k: &mut Keyring) { k.set(""); }` |  |

## 填完之后

- `python m0/replay.py --audit-check` 会报：填了几条、坐标是否仍与当前语料一致。
- 全填完则 `--write` 会算出「人工核对真阳率」并折进基线报告；M0·① 才算收口。

