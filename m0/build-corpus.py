#!/usr/bin/env python3
"""M0·① 回放语料生成器：自造含**已知**缺陷的快照仓库。

  python m0/build-corpus.py [--seed 7] [--repos 20]

产物落在 `m0/corpus/`（`.gitignore` 已挡住，**不入库**）：每个快照是一个真 git 仓，
一个形态一次提交；同目录写 `manifest.json` 声明"哪条规则本该在哪个文件的哪一提交命中"
（kind=pos）与"哪个文件长得像但不许命中"（kind=neg）。判分只认这份清单。

为什么自造：真实转录还没有（M0·② 未证伪），而 §6 要的是**命中数与真阳率**，那需要
"已知答案在哪"的语料。缺陷形态取自前身仓复盘 §四（38 类，`docs/legacy/复盘与工程约定.md`
第 26 行作废 → 38），不是凭空发明；`review_row` 字段记的就是那一行号。

同 seed 逐字节可复现：作者、提交时间、文件名、内容全固定，seed 只决定"哪些形态进哪个仓"。
"""
import argparse
import json
import os
import pathlib
import random
import shutil
import stat
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DATE = 1735689600  # 2025-01-01T00:00:00Z —— 固定，保证 sha 可复现
NAME = "M0 Corpus Builder"
MAIL = "m0@example.invalid"


def git(repo: pathlib.Path, *args, stamp: int = 0):
    ts = str(BASE_DATE + stamp * 60)
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": NAME, "GIT_AUTHOR_EMAIL": MAIL,
        "GIT_COMMITTER_NAME": NAME, "GIT_COMMITTER_EMAIL": MAIL,
        "GIT_AUTHOR_DATE": f"@{ts} +0000", "GIT_COMMITTER_DATE": f"@{ts} +0000",
        "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C",
    })
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=env)


def write(repo: pathlib.Path, rel: str, content: str, newline="\n"):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8", newline=newline)


def lines(body):
    return "\n".join(body) + "\n"


# --------------------------------------------------------------- 形态登记表
# 每个形态：一个函数，往 repo 里落文件（可含 remove），返回
#   {"pos": {规则id: [该命中的文件]}, "neg": {规则id: [不该命中的文件]}}
# pos/neg 的差别就是判分的依据；neg 是"长得像但正确"的反例，缺了它 precision 无从谈起。

def doc_deadlink(repo, rnd):
    """§四 22/23：文档引用了不存在的文件（断链 / 文件名漂移）。"""
    write(repo, "docs/实现规划.md", "# 实现规划\n\n先读 `docs/arch-v2.md`，配置见 `deploy/hooks.json`。\n")
    write(repo, "README.md", "# demo\n\n见 [架构说明](docs/arch-v2.md)。\n")
    return {"pos": {"G-01": ["docs/实现规划.md", "README.md"]}}


def readme_number_drift(repo, rnd):
    """§四 19：README 写的常量与代码里的不一致。"""
    write(repo, "src/queue.rs", "pub const MAX_PENDING: usize = 3;\n\npub fn cap() -> usize { MAX_PENDING }\n")
    write(repo, "README.md", "# demo\n\n队列最多 5 张，超出即丢弃。\n")
    return {"pos": {"G-02": ["README.md"]}}


def no_gitattributes(repo, rnd):
    """§四 15：仓库没有 eol 规则，修好的 CRLF 在别人机器上原样复发。"""
    write(repo, "src/lib.rs", "pub fn load() -> String { String::new() }\n")
    return {"pos": {"G-03": ["<repo>"]}}


def cmd_lf_nonascii(repo, rnd):
    """§四 13：.cmd 用 LF + 非 ASCII 注释，cmd.exe 按字节流解析会把指令边界错位。"""
    write(repo, "dev.cmd",
          "@echo off\nrem 构建前端\nif exist a.txt (\n  echo ok\n) else (\n  echo miss\n)\n")
    return {"pos": {"G-04": ["dev.cmd"]}}


def stray_number_file(repo, rnd):
    """§四 14：重定向写错，凭空生成一个名为数字的文件。"""
    write(repo, "18", "")
    write(repo, "src/main.rs", "fn main() { println!(\"hi\"); }\n")
    return {"pos": {"G-05": ["18"]}}


def counter_one_sided(repo, rnd):
    """§四 39：计数器有语义相反的兄弟态，却只累加一侧。"""
    write(repo, "src/stats.rs", lines([
        "pub struct Stats { pub answers: u32, pub dismissed: u32 }",
        "",
        "impl Stats {",
        "    pub fn on_answer(&mut self) { self.answers += 1; }",
        "    pub fn on_dismiss(&mut self) { /* 该更新的那一侧漏了 */ }",
        "}"]))
    return {"pos": {"G-06": ["src/stats.rs"]}}


def clear_by_empty_string(repo, rnd):
    """§四 11：清除语义写成赋空串，用户以为密钥删了其实条目还在。"""
    write(repo, "src/keyring.rs", lines([
        "pub struct Keyring;",
        "",
        "impl Keyring {",
        "    pub fn set(&mut self, _v: &str) {}",
        "}",
        "",
        "pub fn forget(k: &mut Keyring) { k.set(\"\"); }"]))
    return {"pos": {"G-07": ["src/keyring.rs"]}}


def api_call_without_guard(repo, rnd):
    """新增外部网络调用，且没有任何错误分支。"""
    write(repo, "src/fetch.rs", lines([
        "use reqwest; // 新增外部调用",
        "pub async fn pull(url: String) -> String {",
        "    reqwest::get(url).await.unwrap().text().await.unwrap()",
        "}"]))
    return {"pos": {"D-03": ["src/fetch.rs"], "C-04": ["src/fetch.rs"]}}


def panic_no_catch(repo, rnd):
    """错误路径不见保护，且改动量过线。"""
    body = [f"    let v{i} = data.get({i}).unwrap_or(0);" for i in range(12)]
    write(repo, "src/agg.rs", lines(["pub fn run(data: &[u8]) -> u8 {", "    panic!(\"no data\");"]
                                    + body + ["    0", "}"]))
    return {"pos": {"D-04": ["src/agg.rs"]}}


def todo_left(repo, rnd):
    """遗留标记进仓。"""
    write(repo, "src/parser.ts", lines([
        "export function parse(s: string): string {",
        "  // TODO: 处理转义",
        "  return s.trim();",
        "}"]))
    return {"pos": {"D-05": ["src/parser.ts"]}}


def bare_throw(repo, rnd):
    """裸 throw 无 catch。"""
    write(repo, "src/client.js", lines([
        "export function load(p) {",
        "  if (!p) { throw new Error('no path'); }",
        "  return p;",
        "}"]))
    return {"pos": {"D-07": ["src/client.js"]}}


def source_change_no_test(repo, rnd):
    """改了源文件，测试一个字没动。"""
    write(repo, "src/core.rs", lines(["pub fn handle(x: i32) -> i32 {"]
                                     + [f"    let a{i} = x * {i};" for i in range(1, 21)] + ["    x", "}"]))
    write(repo, "tests/core_test.rs", "// 已存在的测试，本次未更新\n")
    return {"pos": {"C-02": ["src/core.rs"]}}


def mid_change_src(repo, rnd):
    """8..20 行的中等改动：D-02 的正例（不改就等于这条种子没测过）。"""
    write(repo, "src/mid.rs", lines(["pub fn tweak(x: i32) -> i32 {"]
                                    + [f"    let t{i} = x + {i};" for i in range(1, 11)] + ["    x", "}"]))
    return {"pos": {"D-02": ["src/mid.rs"]}}


def decision_files(repo, rnd):
    """动依赖清单与 CI。"""
    write(repo, "Cargo.toml", '[package]\nname = "demo"\nversion = "0.1.0"\n\n[dependencies]\nreqwest = "0.12"\n')
    write(repo, ".github/workflows/ci.yml",
          "name: ci\non: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps: []\n")
    return {"pos": {"C-05": ["Cargo.toml", ".github/workflows/ci.yml"]}}


def delete_code_file(repo, rnd):
    """删掉一个代码文件（commit message 带 remove）。"""
    write(repo, "src/legacy.py", "def old():\n    return 1\n")
    git(repo, "add", "-A", stamp=1)
    git(repo, "commit", "-q", "-m", "chore: 旧模块", stamp=1)
    (repo / "src" / "legacy.py").unlink()
    return {"pos": {"D-06": ["src/legacy.py"]}}


def docs_only(repo, rnd):
    """整批只碰文档。"""
    write(repo, "docs/notes.md", "# 笔记\n\n补一段用法说明。\n")
    write(repo, "README.md", "# demo\n\n加了个 usage 小节。\n")
    return {"pos": {"D-10": ["docs/notes.md", "README.md"]}}


def format_only(repo, rnd):
    """小改动 + 重构/格式化措辞（应被认成"纯格式化"而降权）。"""
    write(repo, "src/util.py", "def f(a, b):\n    return a + b\n")
    return {"pos": {"D-09": ["src/util.py"]}}


def wide_refactor(repo, rnd):
    """一次大改摊在 3 个文件上。"""
    for n in ("a", "b", "c"):
        write(repo, f"src/{n}.rs", lines([f"pub fn {n}() {{"]
                                         + [f"    let x{i} = {i};" for i in range(25)] + ["}"]))
    return {"pos": {"D-01": ["src/a.rs", "src/b.rs", "src/c.rs"], "D-08": ["src/a.rs", "src/b.rs", "src/c.rs"]}}


# ---- 反例：长得像，但不许命中 ----

def dec_clean_docs(repo, rnd):
    write(repo, "docs/guide.md", "# 指南\n")
    write(repo, "docs/setup.md", "# 安装\n\n见 `docs/guide.md`。\n")
    return {"neg": {"G-01": ["docs/setup.md", "docs/guide.md"]}}


def dec_number_matches(repo, rnd):
    write(repo, "src/limits.rs", "pub const MAX_ITEMS: usize = 5;\n")
    write(repo, "docs/usage.md", "上限是 5 项。\n")
    return {"neg": {"G-02": ["docs/usage.md"]}}


def dec_eol_declared(repo, rnd):
    write(repo, ".gitattributes", "* text=auto eol=lf\n*.cmd text eol=crlf\n")
    write(repo, "src/lib.rs", "pub fn ok() {}\n")
    return {"neg": {"G-03": ["<repo>"]}}


def dec_api_with_guard(repo, rnd):
    write(repo, "src/pull.rs", lines([
        "pub async fn pull(u: &str) -> Result<String, Error> {",
        "    match reqwest::get(u).await {",
        "        Ok(r) => Ok(r.text().await?),",
        "        Err(e) => Err(e.into()),",
        "    }",
        "}"]))
    return {"neg": {"C-04": ["src/pull.rs"], "D-03": ["src/pull.rs"]}}


def dec_tests_updated(repo, rnd):
    write(repo, "src/svc.py", "def go():\n    return 42\n")
    write(repo, "tests/test_svc.py", "from src.svc import go\n\ndef test_go():\n    assert go() == 42\n")
    return {"neg": {"C-02": ["src/svc.py"]}}


FORMS = {
    "doc_deadlink": (22, doc_deadlink),
    "readme_number_drift": (19, readme_number_drift),
    "no_gitattributes": (15, no_gitattributes),
    "cmd_lf_nonascii": (13, cmd_lf_nonascii),
    "stray_number_file": (14, stray_number_file),
    "counter_one_sided": (39, counter_one_sided),
    "clear_by_empty_string": (11, clear_by_empty_string),
    "api_call_without_guard": (None, api_call_without_guard),
    "panic_no_catch": (None, panic_no_catch),
    "todo_left": (None, todo_left),
    "bare_throw": (None, bare_throw),
    "source_change_no_test": (None, source_change_no_test),
    "mid_change_src": (None, mid_change_src),
    "decision_files": (None, decision_files),
    "delete_code_file": (None, delete_code_file),
    "docs_only": (None, docs_only),
    "format_only": (None, format_only),
    "wide_refactor": (None, wide_refactor),
}
DECOYS = {
    "clean_docs": dec_clean_docs,
    "number_matches": dec_number_matches,
    "eol_declared": dec_eol_declared,
    "api_with_guard": dec_api_with_guard,
    "tests_updated": dec_tests_updated,
}
MSG = {
    "format_only": "style: 重命名内部变量并 format",
    "docs_only": "docs: 补充使用说明",
    "wide_refactor": "refactor: 拆分聚合逻辑",
    "todo_left": "feat: 先接上解析，细节待补",
    "delete_code_file": "refactor!: remove legacy module",
}


def rmtree_robust(target: pathlib.Path):
    """Windows 下 git 的 objects 文件带只读位，裸 rmtree 会 PermissionError。"""
    def onexc(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(target, onexc=onexc)


def build(out: pathlib.Path, seed: int, n_repos: int, full: bool):
    rnd = random.Random(seed)
    if out.exists():
        rmtree_robust(out)
    out.mkdir(parents=True)
    pool = list(FORMS)
    manifest = {"seed": seed, "n_repos": n_repos, "forms": {}, "repos": []}
    for k, (row, _) in FORMS.items():
        manifest["forms"][k] = {"review_row": row}
    for i in range(1, n_repos + 1):
        repo = out / f"repo-{i:02d}"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        # 覆盖率优先：--full 让每个形态在至少一个仓里出现；否则纯随机
        chosen = pool[:] if full and i == 1 else rnd.sample(pool, rnd.randint(2, 4))
        # 同一仓里"缺 eol 规则"和"已声明 eol 规则"不能共存：G-03 是仓库级事实，
        # 两个形态同时进一个仓会让期望自相矛盾，测出来的只是我自己在打自己
        dpool = [d for d in DECOYS if not (d == "eol_declared" and "no_gitattributes" in chosen)]
        decoys = rnd.sample(dpool, min(rnd.randint(1, 3), len(dpool)))
        rec = {"name": repo.name, "steps": []}
        stamp = 0
        for form in chosen + decoys:
            stamp += 1
            files = FORMS[form][1](repo, rnd) if form in FORMS else DECOYS[form](repo, rnd)
            msg = MSG.get(form, f"feat: {form.replace('_', ' ')}")
            git(repo, "add", "-A", stamp=stamp)
            r = git(repo, "commit", "-q", "--allow-empty", "-m", msg, stamp=stamp)
            sha = git(repo, "rev-parse", "HEAD", stamp=stamp).stdout.strip()
            rec["steps"].append({"form": form, "kind": "pos" if form in FORMS else "neg",
                                 "msg": msg, "sha": sha[:12], "expect": files})
        manifest["repos"].append(rec)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                       encoding="utf-8", newline="\n")
    print(f"生成 {n_repos} 个快照仓库 → {out}（seed={seed}，形态 {len(FORMS)} 种 + 反例 {len(DECOYS)} 种）")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--repos", type=int, default=20)
    ap.add_argument("--full", action="store_true", help="第一个仓把全部形态各放一次（做覆盖基线）")
    ap.add_argument("--out", default=str(pathlib.Path(__file__).resolve().parent / "corpus"))
    a = ap.parse_args()
    build(pathlib.Path(a.out), a.seed, a.repos, a.full)
    return 0


if __name__ == "__main__":
    sys.exit(main())
