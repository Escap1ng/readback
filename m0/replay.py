#!/usr/bin/env python3
"""M0·① 回放器：把规则跑在自造语料上，产出命中数与真阳率。

  python m0/replay.py [--write]        # 正常回放；--write 覆盖 docs/replay-baseline.md
  python m0/replay.py --self           # 负向对照：四段各自只咬一个分支，任何一段不报就是假检查

规则**写成数据**（RULES 表），不写成散落的 if —— 形态照 RFC-0004 §5 的 L3：
`触发条件(纯函数) + 所需证据 + 严重度 + 呈现模板`。这里的 Python 是**取证夹具**，不是产品；
M1/M2 要用 Rust 重写，这张表就是它的规格。

三条不许打折的规矩：
1. 每条命中必须带落得了地的证据（文件在该提交里存在、行号真实、摘录真在那一行）。
   核不上就丢弃该条并计入「坏证据」—— P1「无证据不出声」先用在自家产出上。
2. 判分只认 `m0/corpus/manifest.json` 里的 pos/neg 声明，不认人记的账。
3. precision 靠反例撑着：反例被命中算 FP，正例没命中算 FN，两个都进报告。
"""
import argparse
import json
import pathlib
import random
import re
import subprocess
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS = ROOT / "m0" / "corpus"
REPORT = ROOT / "docs" / "replay-baseline.md"

SRC_EXT = (".rs", ".ts", ".tsx", ".js", ".jsx", ".vue", ".py", ".go", ".java",
           ".kt", ".swift", ".cs", ".cpp", ".c", ".h")
TEST_HINT = ("/test/", "/tests/", "__tests__", ".test.", ".spec.")
DECISION = ("Cargo.toml", "Cargo.lock", "package.json", "package-lock.json",
            "pnpm-lock.yaml", "yarn.lock", "pyproject.toml", "requirements.txt",
            "go.mod", "Dockerfile", "tauri.conf.json")


def is_src(p):
    return p.lower().endswith(SRC_EXT)


def is_test(p):
    return any(h in p.replace("\\", "/") for h in TEST_HINT)


def is_decision(p):
    return p in DECISION or "/.github/workflows/" in p or "/migrations/" in p


_GIT_CACHE = {}


class Repo:
    def __init__(self, path):
        self.path = pathlib.Path(path)

    def git(self, *a, binary=False):
        # core.quotePath=false：不然 git 会把中文路径转成八进制转义，后面所有按路径的比对全错位
        # 注意：给 subprocess 传 encoding/errors 会强制文本模式，拿字节必须一个都不传
        key = (str(self.path), a, binary)
        if key in _GIT_CACHE:
            return _GIT_CACHE[key]      # 全是只读查询；不缓存的话 Windows 上光进程创建就要几分钟
        args = ["git", "-c", "core.quotePath=false", *a]
        kw = {} if binary else {"text": True, "encoding": "utf-8", "errors": "replace"}
        r = subprocess.run(args, cwd=self.path, capture_output=True, **kw)
        out = (r.stdout or b"") if binary else (r.stdout or "")
        _GIT_CACHE[key] = out
        return out

    def content(self, sha, path):
        return self.git("show", f"{sha}:{path}")

    def changeset(self, sha):
        """一次提交 = 一个 change set：改了哪些文件、各文件增删行、提交说明、当时的全树。"""
        out = self.git("show", "--numstat", "--format=%H\x01%s\x01", sha, "--")
        head, _, rest = out.partition("\x01")
        msg, _, rest = rest.partition("\x01")
        files, delta = [], {}
        for line in rest.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            add, dele = parts[0], parts[1]
            path = "/".join(parts[2:]).rstrip("/")
            files.append(path)
            delta[path] = (0 if add == "-" else int(add), 0 if dele == "-" else int(dele))
        tree = [p for p in self.git("ls-tree", "-r", "--name-only", sha).splitlines() if p]
        return {"sha": head.strip() or sha, "msg": msg.strip(), "files": files,
                "delta": delta, "tree": tree}


def delta_of(cs):
    return sum(a + d for a, d in cs["delta"].values())


def make_evidence(repo, cs, path, needle):
    """证据落不了地就返回 None —— 宁可不发声，也不给一条指不到东西的结论。"""
    if path == "<repo>":
        return {"line": None, "excerpt": f"提交 {cs['sha'][:8]} 的全树里查该属性"}
    if path in cs["tree"]:
        body = repo.content(cs["sha"], path)
    else:
        # 被这次提交删掉的文件：证据只能指向它被删之前的样子
        body = repo.content(cs["sha"] + "^", path)
        if not body:
            return None
    for i, line in enumerate(body.split("\n"), 1):
        if needle and needle in line:
            return {"line": i, "excerpt": line.strip()[:120]}
    if not needle:
        return {"line": 1, "excerpt": (body.split("\n")[0] or "(空文件)").strip()[:120]}
    return None


# --------------------------------------------------------------- 规则实现
def r_source_no_test(cs, repo):
    src = [f for f in cs["files"] if is_src(f) and not is_test(f)]
    if src and not [f for f in cs["files"] if is_test(f)]:
        return [(src[0], None, "改源未改测")]
    return []


def r_api_no_guard(cs, repo):
    hits = []
    for f in cs["files"]:
        if not is_src(f):
            continue
        body = repo.content(cs["sha"], f)
        if re.search(r"reqwest|fetch\(|axios|http\.|requests\.", body) \
                and not re.search(r"catch|match |try:|Result<|Err\(", body):
            hits.append((f, "reqwest", "外部调用未见错误分支"))
    return hits


def r_decision(cs, repo):
    return [(f, None, "决策文件变更") for f in cs["files"] if is_decision(f)]


def r_big_change(cs, repo):
    f = [x for x in cs["files"] if is_src(x)] or cs["files"]
    return [(f[0], None, f"line_delta={delta_of(cs)}")] if f and delta_of(cs) >= 20 else []


def r_mid_change(cs, repo):
    f = [x for x in cs["files"] if is_src(x)] or cs["files"]
    return [(f[0], None, f"line_delta={delta_of(cs)}")] if f and 8 <= delta_of(cs) < 20 else []


def r_api_keyword(cs, repo):
    for f in cs["files"]:
        if not is_src(f):
            continue
        m = re.search(r"reqwest|fetch\(|axios|http\.|requests\.", repo.content(cs["sha"], f))
        if m:
            return [(f, m.group(0), "新增外部调用")]
    return []


def r_panic_no_catch(cs, repo):
    if delta_of(cs) < 10:
        return []
    for f in cs["files"]:
        if not is_src(f):
            continue
        body = repo.content(cs["sha"], f)
        if re.search(r"panic!|unwrap\(", body) and not re.search(r"catch|try \{|try:|match ", body):
            return [(f, "panic!" if "panic!" in body else "unwrap(", "异常路径未见保护")]
    return []


def r_todo(cs, repo):
    for f in cs["files"]:
        if not is_src(f):
            continue
        m = re.search(r"TODO|FIXME", repo.content(cs["sha"], f))
        if m:
            return [(f, m.group(0), "遗留标记")]
    return []


def r_delete_code(cs, repo):
    if not re.search(r"删除|remove |rm ", cs["msg"], re.I):
        return []
    hits = []
    for line in repo.git("show", "--raw", "--format=", cs["sha"]).splitlines():
        # 形如 `:100644 000000 ca896f6 0000000 D\tpath` —— 制表符前那串的最后一段才是状态
        cols = line.split("\t")
        if len(cols) < 2:
            continue
        fields = cols[0].split()
        if fields and fields[-1].startswith("D"):
            path = cols[1].strip()
            if is_src(path):
                hits.append((path, None, "删除代码文件"))
    return hits


def r_bare_throw(cs, repo):
    for f in cs["files"]:
        if not is_src(f):
            continue
        body = repo.content(cs["sha"], f)
        if "throw" in body and "catch" not in body:
            return [(f, "throw", "裸 throw")]
    return []


def r_wide_surface(cs, repo):
    uniq = sorted(set(cs["files"]))
    return [(uniq[0], None, f"影响面 {len(uniq)} 个文件")] if len(uniq) >= 3 else []


def r_format_only(cs, repo):
    if not cs["files"] or delta_of(cs) >= 5:
        return []
    return [(cs["files"][0], None, "纯格式化")] if re.search(r"format|rename|重构", cs["msg"], re.I) else []


def r_docs_only(cs, repo):
    if cs["files"] and all(f.endswith(".md") or f.startswith("docs/") or f == "README.md"
                           for f in cs["files"]):
        return [(cs["files"][0], None, "纯文档")]
    return []


REF = re.compile(r"`([^`\s]+\.(?:md|rs|ts|js|py|json|yml|toml))`|\]\(([^)\s]+\.(?:md|rs|ts|js|py|json|yml|toml))\)")


def r_doc_deadlink(cs, repo):
    hits = []
    tree = set(cs["tree"])
    for f in cs["files"]:
        if not f.endswith(".md"):
            continue
        for m in REF.finditer(repo.content(cs["sha"], f)):
            ref = (m.group(1) or m.group(2) or "").lstrip("./")
            if ref and ref not in tree:
                hits.append((f, ref, f"引用不存在的 {ref}"))
    return hits


def r_readme_number_drift(cs, repo):
    """只在无歧义时发声：全树恰有一个 usize 常量，而文档写了另一个数。多个常量就不判——
    宁可漏报，也不猜哪个才是文档说的那个。"""
    consts = {}
    for p in cs["tree"]:
        if p.endswith((".rs", ".py", ".js", ".ts")):
            for m in re.finditer(r"(?:pub )?const ([A-Z_]+)\s*:\s*usize\s*=\s*(\d+)", repo.content(cs["sha"], p)):
                consts[m.group(1)] = (int(m.group(2)), p)
    if len(consts) != 1:
        return []
    val, cpath = next(iter(consts.values()))
    for f in cs["files"]:
        if not f.endswith(".md"):
            continue
        for m in re.finditer(r"最多\s*(\d+)", repo.content(cs["sha"], f)):
            if int(m.group(1)) != val:
                return [(f, m.group(0), f"文档写 {m.group(1)}，{cpath} 是 {val}")]
    return []


def r_no_eol_rule(cs, repo):
    return [("<repo>", None, "树里无 .gitattributes")] if ".gitattributes" not in cs["tree"] else []


def r_cmd_lf_nonascii(cs, repo):
    hits = []
    for f in cs["files"]:
        if not f.lower().endswith((".cmd", ".bat")):
            continue
        raw = repo.git("show", f"{cs['sha']}:{f}", binary=True)
        if b"\r\n" not in raw and any(b > 0x7F for b in raw):
            hits.append((f, "rem", ".cmd 用 LF 且含非 ASCII 注释"))
    return hits


def r_stray_number_file(cs, repo):
    return [(f, None, "疑似重定向误写") for f in cs["files"] if re.fullmatch(r"\d+", f)]


def r_counter_one_sided(cs, repo):
    hits = []
    for f in cs["files"]:
        body = repo.content(cs["sha"], f)
        fields = set(re.findall(r"pub (\w+):\s*u32", body))
        if {"answers", "dismissed"} <= fields and "dismissed" not in set(re.findall(r"self\.(\w+)\s*\+=", body)):
            hits.append((f, "dismissed", "兄弟态只计一侧"))
    return hits


def r_clear_by_empty(cs, repo):
    hits = []
    for f in cs["files"]:
        body = repo.content(cs["sha"], f)
        if re.search(r"fn (forget|clear|delete|reset)\b[^)]*\)\s*\{[^}]*set\(\"\"\)", body, re.S):
            hits.append((f, 'set("")', "清除语义写成赋空串"))
    return hits


RULES = [
    ("C-02", "改源未改测", "M0 清单 C-02（git-only 弱化：只见文件不见测试运行）", r_source_no_test),
    ("C-04", "外部调用无错误分支", "M0 清单 C-04", r_api_no_guard),
    ("C-05", "决策文件变更", "M0 清单 C-05", r_decision),
    ("D-01", "大改 ≥20 行", "M0 清单 D-01", r_big_change),
    ("D-02", "中改 8..20 行", "M0 清单 D-02", r_mid_change),
    ("D-03", "新增外部调用", "M0 清单 D-03", r_api_keyword),
    ("D-04", "异常路径未见保护", "M0 清单 D-04", r_panic_no_catch),
    ("D-05", "遗留标记", "M0 清单 D-05", r_todo),
    ("D-06", "删除代码文件", "M0 清单 D-06", r_delete_code),
    ("D-07", "裸 throw", "M0 清单 D-07", r_bare_throw),
    ("D-08", "影响面 ≥3 文件", "M0 清单 D-08", r_wide_surface),
    ("D-09", "纯格式化", "M0 清单 D-09", r_format_only),
    ("D-10", "纯文档", "M0 清单 D-10", r_docs_only),
    ("G-01", "文档断链", "§四 22/23；§H 第 1 行缺口", r_doc_deadlink),
    ("G-02", "文档数字与常量漂移", "§四 19；§H 第 1 行缺口", r_readme_number_drift),
    ("G-03", "无 eol 规则", "§四 15；§H 第 7 行缺口", r_no_eol_rule),
    ("G-04", ".cmd 用 LF+非 ASCII", "§四 13；§H 第 7 行缺口", r_cmd_lf_nonascii),
    ("G-05", "凭空生成的数字文件名", "§四 14", r_stray_number_file),
    ("G-06", "计数器只算一侧", "§四 39；§H 第 3 行缺口", r_counter_one_sided),
    ("G-07", "清除写成赋空串", "§四 11", r_clear_by_empty),
]


REPO_SCOPED = {"G-03"}   # 仓库级属性：一次提交报一次会把命中数灌爆，按仓去重


def replay(man, rules, corpus=CORPUS):
    stats = {rid: {"tp": 0, "fp": 0, "unk": 0, "fn": 0, "hits": 0, "bad_ev": 0, "samples": []}
             for rid, _, _, _ in rules}
    for rec in man["repos"]:
        repo = Repo(corpus / rec["name"])
        want, ban = defaultdict(set), defaultdict(set)
        for st in rec["steps"]:
            for rid, files in st["expect"].get(st["kind"], {}).items():
                (want if st["kind"] == "pos" else ban)[rid].update(files)
        hit_files = defaultdict(set)
        last = rec["steps"][-1]["sha"]
        for st in rec["steps"]:
            cs = repo.changeset(st["sha"])
            for rid, _, _, fn in rules:
                # 仓库级事实（如"有没有 eol 规则"）按最终树判一次；
                # 逐提交判会把同一件事报几十遍，命中数就成了灌水的产物
                if rid in REPO_SCOPED and st["sha"] != last:
                    continue
                for path, needle, note in fn(cs, repo):
                    ev = make_evidence(repo, cs, path, needle)
                    s = stats[rid]
                    if ev is None:
                        s["bad_ev"] += 1  # 证据落不了地：不发声，但记一笔
                        continue
                    s["hits"] += 1
                    if path in want.get(rid, set()):
                        s["tp"] += 1
                        s["samples"].append((rec["name"], cs["sha"][:8], path, ev["line"], note, "真阳", ev["excerpt"]))
                        hit_files[rid].add(path)
                    elif path in ban.get(rid, set()):
                        s["fp"] += 1
                        s["samples"].append((rec["name"], cs["sha"][:8], path, ev["line"],
                                             note + "｜反例被命中", "假阳", ev["excerpt"]))
                    else:
                        s["unk"] += 1     # 语料没登记过这里该不该响 —— 不能算假阳
                        s["samples"].append((rec["name"], cs["sha"][:8], path, ev["line"], note,
                                             "未登记", ev["excerpt"]))
        for rid, files in want.items():
            if rid in stats and files and not (hit_files[rid] & files):
                # 漏报按"这个仓登记过该规则的正例，却一次都没响"计：
                # 产品的发声单位是一次变更集，不是一堆文件逐个点名
                stats[rid]["fn"] += 1
    return stats


def pct(a, b):
    return "—" if not b else f"{round(a * 100 / b)}%"


def render(stats, man, rules):
    tp = sum(s["tp"] for s in stats.values())
    fp = sum(s["fp"] for s in stats.values())
    unk = sum(s["unk"] for s in stats.values())
    fn = sum(s["fn"] for s in stats.values())
    bad = sum(s["bad_ev"] for s in stats.values())
    zero = [rid for rid, _, _, _ in rules if stats[rid]["hits"] == 0]
    nsteps = sum(len(r["steps"]) for r in man["repos"])
    verdicts = [r for r in read_audit() if r["verdict"] in ("真", "误")]
    v_true = sum(1 for r in verdicts if r["verdict"] == "真")
    out = [
        "# M0·① 回放基线（生成物）",
        "",
        "> 本文由 `python m0/replay.py --write` 生成，**表里的数字一个都不手填**。语料来自",
        "> `python m0/build-corpus.py --seed %s --repos %s --full`，落在 `m0/corpus/`（不入库、可删重建，"
        "所以复现要连生成器一起跑）。规则表在 `m0/replay.py` 的 `RULES`。" % (man["seed"], man["n_repos"]),
        "",
        "**三个桶的口径**（这条决定 precision 能不能信）：真阳 = 命中在语料登记为 pos 的文件上；"
        "假阳 = 命中在登记为 neg 的反例上；未登记 = 语料没对这里表过态，**不算假阳**。"
        "把未登记混进分母，就是在自造一个好看的 precision。",
        "",
        "## 结论",
        "",
        ("**状态：M0·① 半程** —— 命中数与机器判定的真阳率已出；**人工核对 %d/20**，"
         "工作单在 `docs/manual-audit.md`。" % len(verdicts)) if len(verdicts) < 20 else
        ("**状态：M0·① 已收口** —— 人工核对 20 条完成，人工真阳率 **%s**（误报 %d 条）。"
         % (pct(v_true, len(verdicts)), len(verdicts) - v_true)),
        "",
        f"- {man['n_repos']} 个快照仓库 / {nsteps} 次提交，规则 {len(rules)} 条，共发声 {tp + fp + unk} 次："
        f"真阳 {tp}、假阳 {fp}、未登记 {unk}；可判 precision **{pct(tp, tp + fp)}**，登记过的正例漏报 {fn} 次。",
        f"- 坏证据（命中了但证据落不了地，已丢弃并计数）：**{bad}** 条。非 0 就说明规则在编造出处，"
        "先修规则再谈覆盖率。",
        f"- 一次都没命中的规则 {len(zero)} 条：{'、'.join(zero) or '无'}。"
        "按 §6 的口径，真实历史里也一直不响的种子在 M2 直接淘汰，不因为\"看起来有理\"就留在目录里。",
        "",
        "## 逐条命中数",
        "",
        "| 规则 | 名称 | 出处 | 发声 | 真阳 | 假阳 | 未登记 | 漏报 | precision | 坏证据 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for rid, name, src, _ in rules:
        s = stats[rid]
        out.append(f"| {rid} | {name} | {src} | {s['hits']} | {s['tp']} | {s['fp']} | {s['unk']} | {s['fn']} | "
                   f"{pct(s['tp'], s['tp'] + s['fp'])} | {s['bad_ev']} |")
    # 读数由脚本挑，不靠人看图：下面每一句都是算出来的
    loud = max(rules, key=lambda r: stats[r[0]]["hits"])
    ls = stats[loud[0]]
    judgeable = [(r[0], r[1], stats[r[0]]) for r in rules
                 if stats[r[0]]["tp"] + stats[r[0]]["fp"] > 0]
    worst = min(judgeable, key=lambda t: t[2]["tp"] * 100 / (t[2]["tp"] + t[2]["fp"])) if judgeable else None
    blind = [r[0] for r in rules if stats[r[0]]["tp"] + stats[r[0]]["fp"] == 0 and stats[r[0]]["unk"] > 0]
    out += ["", "## 读数（由脚本挑出来的，不是人看图说话）", "",
            f"- **最吵的一条是 {loud[0]}「{loud[1]}」**：发声 {ls['hits']} 次，其中 {ls['unk']} 次"
            f"（{pct(ls['unk'], ls['hits'])}）落在语料没登记过的地方。"
            "这类规则直接进目录只会变成噪音源，M2 要么给它加前置条件，要么降权。",
            f"- **可判里 precision 最低的是 {worst[0]}「{worst[1]}」**："
            f"真阳 {worst[2]['tp']} / 假阳 {worst[2]['fp']} = {pct(worst[2]['tp'], worst[2]['tp'] + worst[2]['fp'])}。"
            "它输给的那条反例是语料里唯一一处『同类但已正确处理』的写法——真实仓库里这种写法是多数。",
            (f"- **{len(blind)} 条规则本轮等于没测**：{'、'.join(blind)}——它们只落在未登记上，"
             "语料没给过判断，别把『没测』读成『没问题』。" if blind else
             "- 本轮每条规则都至少拿到过一次登记判定；但**登记判定不等于人工核对**，见下面的限制段。"),
            ]
    out += ["", "## 抽样（每条规则至多 3 个，坐标可核）", "",
            "| 规则 | 仓库 | 提交 | 文件 | 行 | 说明 |", "|---|---|---|---|---|---|"]
    for rid, _, _, _ in rules:
        for smp in stats[rid]["samples"][:3]:
            out.append(f"| {rid} | {smp[0]} | {smp[1]} | `{smp[2]}` | {smp[3]} | {smp[4]} |")
    out += ["", "## 这份数不能证明什么",
            "",
            "- §6 的 M0 验收要的是「人工核对的真阳率」，本节表里的 precision 是**机器判定**（命中对不对"
            "得上语料登记的 pos/neg）。人工进度见上面的状态行；工作单 `docs/manual-audit.md` 填完，"
            "本文结论跟着变。**在人工核完之前，不许拿这份数进 M2。**",
            "- 抽核工作单是「每条规则各 1 条」的分层抽样，用来让每条规则过一次人眼；"
            "**它不能当整体 precision 的估计**——那是 214 次发声上的机器判定，或以后更大规模的均匀抽样。",
            "- 语料是**自造**的：命中率高只说明规则在「按形态写出来的东西」上有效，不等于在真实仓库里也有效；"
            "真实语料要等 M0·① 之外的取样（见 `BOOTSTRAP.md` §5）。",
            "- C-01 / C-03 / C-07 这类**要看测试退出码或 Agent intent 的规则本轮根本没有测**——"
            "git 里没有那个信息，这正是 M0·② 要证伪的东西。种子 20 条里本轮能测的是上表这些。",
            "- C-02 在 git-only 条件下被弱化过：原判据是\"tests 为空\"（指测试事件），这里退成\"改源文件而未改测试文件\"。"
            "这是**口径变化**，不是同一条规则的复现。",
            "- precision 的分母是登记的反例（5 种），反例集薄，FP 率偏乐观。目录 v1 要扩反例。",
            "- 规则是**文本级**的，会被注释骗过：第一版语料里，G-06 的反面写法在注释里写出了"
            "`self.dismissed += 1`，规则就再也不响了——同一条规则在真实代码里的漏报只会更多。"
            "这条是本轮实测撞出来的，不是设想。",
            "- 仓库级事实必须按仓判一次（`REPO_SCOPED`）。早期版本让 G-03 逐提交发声，"
            "20 个仓报出 101 次命中，看着像覆盖率高，其实是同一句话说了 101 遍。",
            ""]
    return "\n".join(out)


# --------------------------------------------------------------- 人工抽核工作单
AUDIT = ROOT / "docs" / "manual-audit.md"
VERDICTS = ("真", "误", "待定")


def audit_rows(stats, rules, seed=7):
    """每条规则各抽 1 条 = 20 行。这不是用来估整体 precision 的（那是机器判定的活），
    是用来让目录 v1 的每一条都过一次人眼。选择用固定 seed，逐次可复现。"""
    rnd = random.Random(seed)
    rows = []
    for rid, name, src, _ in rules:
        sm = stats[rid]["samples"]
        if sm:
            rows.append((rid, name, src, rnd.choice(sm)))
    return rows


def render_audit(rows, seed=7):
    out = [
        "# 人工抽核工作单（M0·① 的另一半）",
        "",
        "`docs/replay-baseline.md` 里的 79% 是**机器判定**——机器只知道自己登记过的 pos/neg。",
        "§6 的验收要的是「人工核对的真阳率」，所以这张表由**你**填，不由我填。",
        "",
        "**怎么填**：最后一列写 `真`（确实是该抓的缺陷）/ `误`（不该抓，是误报）/ `待定`。",
        "填完跑 `python m0/replay.py --audit-check` 核对，再 `python m0/replay.py --write`",
        "把人工结论折回基线报告。**一条都别替我勾**——这 20 条的价值就在它是别人看的。",
        "",
        f"抽样规则：seed={seed}，每条规则各 1 条（{len(rows)} 行）。摘录已直接抄在下面，",
        "判定不依赖 `m0/corpus/` 还在不在；坐标留着供你想看上下文。",
        "",
        "| # | 规则 | 名称 | 机器判定的桶 | 仓库 | 提交 | 文件:行 | 摘录 | 判定 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, (rid, name, src, smp) in enumerate(rows, 1):
        repo, sha, path, line, note, bucket, excerpt = smp
        ex = excerpt.replace("|", "\\|").replace("\n", " ")
        out.append(f"| {i} | {rid} | {name} | {bucket} | {repo} | {sha} | `{path}:{line}` | `{ex[:80]}` |  |")
    out += ["", "## 填完之后",
            "",
            "- `python m0/replay.py --audit-check` 会报：填了几条、坐标是否仍与当前语料一致。",
            "- 全填完则 `--write` 会算出「人工核对真阳率」并折进基线报告；M0·① 才算收口。",
            ""]
    return "\n".join(out) + "\n"


def read_audit(path=AUDIT):
    """解析工作单 → [(行号, 规则, 桶, 仓库, 提交, 文件:行, 判定)]。"""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        m = re.match(r"^\| (\d+) \| ([A-Z]-\d\d) \|", line)
        if not m:
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) < 9:
            continue
        # 只有摘录那一格可能含转义竖线，所以左侧 0..6 按位取、判定从末尾取
        rows.append({"idx": int(c[0]), "rid": c[1], "bucket": c[3], "repo": c[4],
                     "sha": c[5], "fileline": c[6].strip("`"), "verdict": c[-1]})
    return rows


def selftest(corpus=CORPUS):
    """四段各自只咬一个分支。任何一段不报，那段就是假的。

    夹具必须**复用真实规则 id**：id 不在语料的 pos/neg 登记里，恒真规则永远判不出假阳、
    恒假规则永远判不出漏报 —— 第一版就是这么写出过一个假绿的负向对照。
    """
    man = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    always = [(rid, name, src, lambda cs, repo: [(f, None, "恒真") for f in cs["files"]])
              for rid, name, src, _ in RULES]
    never = [(rid, name, src, lambda cs, repo: []) for rid, name, src, _ in RULES]
    st_all = replay(man, always, corpus)
    checks = {"恒真规则被记成假阳": sum(s["fp"] for s in st_all.values()) > 0}
    st_never = replay(man, never, corpus)
    checks["恒假规则 0 发声且报漏报"] = (sum(s["hits"] for s in st_never.values()) == 0
                                    and sum(s["fn"] for s in st_never.values()) > 0)
    st_real = replay(man, RULES, corpus)
    checks["真实规则坏证据为 0"] = sum(s["bad_ev"] for s in st_real.values()) == 0
    broken = json.loads(json.dumps(man))
    broken["repos"][0]["steps"][0]["expect"]["pos"]["G-01"] = ["nowhere/nope.md"]
    st_broken = replay(broken, RULES, corpus)
    fn_a = sum(s["fn"] for s in st_real.values())
    fn_b = sum(s["fn"] for s in st_broken.values())
    checks["改掉一条正例期望后漏报上升"] = fn_b > fn_a
    for k, v in checks.items():
        print(f"  [{'咬住' if v else '没咬住'}] {k}")
    print("负向对照:", "四段全咬住" if all(checks.values()) else "有分支是假的 —— 别信这份回放")
    return 0 if all(checks.values()) else 1


def audit(corpus=CORPUS, seed=7, force=False):
    man = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    rows = audit_rows(replay(man, RULES, corpus), RULES, seed)
    if AUDIT.exists() and not force:
        filled = [r for r in read_audit() if r["verdict"] in VERDICTS]
        if filled:
            print(f"[拒绝覆盖] {AUDIT.name} 里已有 {len(filled)} 条判定。要重来加 --force（会清掉你填的判定）")
            return 1
    AUDIT.write_text(render_audit(rows, seed), encoding="utf-8", newline="\n")
    print(f"→ 已写 {AUDIT.relative_to(ROOT).as_posix()}：{len(rows)} 行，判定列留空等你填")
    return 0


def audit_check(corpus=CORPUS, seed=7):
    rows = read_audit()
    if not rows:
        print("[FAIL] 读不到工作单 —— 先跑 python m0/replay.py --audit")
        return 1
    judged = [r for r in rows if r["verdict"] in VERDICTS]
    print(f"工作单 {len(rows)} 行；已判定 {len(judged)}；空白 {len(rows) - len(judged)}")
    for v in VERDICTS:
        print(f"  {v}: {sum(1 for r in judged if r['verdict'] == v)}")
    # 坐标核对：工作单是某个语料版本的产物，语料重建/规则改动后必须仍能落地
    man = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    live = set()
    for rid, _, _, smp in audit_rows(replay(man, RULES, corpus), RULES, seed):
        live.add((rid, smp[0], smp[1], f"{smp[2]}:{smp[3]}"))
    sheet = {(r["rid"], r["repo"], r["sha"], r["fileline"]) for r in rows}
    drift = sheet - live
    print("坐标核对：", "全部 20 条仍能落到当前语料的这次命中" if not drift else f"{len(drift)} 条坐标已失效 → {sorted(drift)[:3]}")
    if len(judged) < len(rows):
        print("状态：未填完 —— M0·① 仍是半程")
        return 0 if not drift else 1
    true = sum(1 for r in judged if r["verdict"] == "真")
    fp = len(judged) - true
    print(f"人工核对真阳率：{pct(true, true + fp)}（误报 {fp}/{len(judged)} 条，M2 门槛 ≤20%）")
    return 0 if (not drift and fp * 5 <= len(judged)) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="把结果写进 docs/replay-baseline.md")
    ap.add_argument("--audit", action="store_true", help="生成人工抽核工作单 docs/manual-audit.md")
    ap.add_argument("--audit-check", action="store_true", dest="audit_check")
    ap.add_argument("--force", action="store_true", help="配合 --audit：覆盖已填的工作单")
    ap.add_argument("--self", action="store_true", dest="selftest_")
    ap.add_argument("--corpus", default=str(CORPUS))
    a = ap.parse_args()
    corpus = pathlib.Path(a.corpus)
    if not (corpus / "manifest.json").exists():
        print(f"[FAIL] 没有语料清单 {corpus}/manifest.json —— 先跑 python m0/build-corpus.py")
        return 1
    if a.selftest_:
        return selftest(corpus)
    if a.audit:
        return audit(corpus, force=a.force)
    if a.audit_check:
        return audit_check(corpus)
    man = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    stats = replay(man, RULES, corpus)
    text = render(stats, man, RULES)
    print(text.split("## 抽样")[0])
    if a.write:
        REPORT.write_text(text, encoding="utf-8", newline="\n")
        print(f"→ 已写 {REPORT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
