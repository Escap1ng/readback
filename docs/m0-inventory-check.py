#!/usr/bin/env python3
"""M0 规则清单的自查：抄没抄全、分类分没分完、表格塌没塌、自述数字对不对。

用法:
  python docs/m0-inventory-check.py                 # 只跑本仓自足检查（不需要旧仓）
  python docs/m0-inventory-check.py [--src ../kvba] # 旧仓在位时，额外对照源码查覆盖率
  python docs/m0-inventory-check.py --self          # 负向对照:每段都必须报问题，否则该段是假的

设计约束（2026-09-21 改）：**默认不依赖旧仓**。旧仓 `../kvba` 的 5 个提交里有导入锚点
`ddcbf4f`，它至今不在任何远程上，所以"必须能访问旧仓才验得出"等于把本仓的自查能力
绑在一台机器上。现在：旧仓在位则多查一类（常量/函数覆盖），不在位则明确报"降级"，
而不是失败、也不是假装全绿。

只在 M0 阶段有用：等规则迁进新仓、目录 v1 落地，这个脚本应当被删除，
而不是留在仓里当"永远绿的检查器"。
"""
import argparse
import collections
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).resolve().parent
DOC = HERE / "M0-rules-inventory.md"
SRC_FILES = {
    "gate/mod.rs": (124, 420),
    "insight/mod.rs": (104, 512),
    "workunit/mod.rs": (107, 300),
}
ALWAYS_REQUIRED_CONSTS = [
    "SCORE_THRESHOLD", "LAST_CARD_WINDOW_SECS", "THEME_COOLDOWN_SECS", "THEME_MUTE_SECS",
    "DEDUP_WINDOW_SECS", "ACTIVITY_WINDOW_SECS", "DECISION_LOG_KEEP", "DECISION_LOG_TRIM_AT",
    "INTERRUPT_CONFIDENCE", "MAX_PENDING", "TTL_SECS", "FACTS_MERGE_EVERY", "ROLLING_LIMIT",
    "ROLLING_MAX_BYTES", "CONTENT_DEDUP_SECS", "CONTENT_DEDUP_MAX", "MAX_WORKUNIT_EVENTS",
    "WORKUNIT_KEEP", "INSIGHT_KEEP", "HISTORY_MAX", "SCHEMA", "EVENT_TYPES", "MAX_DIFF_CHARS",
    "MAX_INTENT_CHARS", "MAX_FILES", "PENDING_OPTIONS", "UNSATISFIED_MARK",
    "PROMPT_PENDING_MARK", "TIP_POOL",
]
DISPOSITIONS = ("种子", "结构件", "打扰机", "教训")
SEP = "\x00"


def rule_rows(text):
    """返回 [(规则号, 处置 or None, 是否标 ★)]。"""
    out = []
    for line in text.split("\n"):
        m = re.match(r"^\| ([A-I]-\d\d) \|", line)
        if m:
            disp = next((d for d in DISPOSITIONS if d in line), None)
            out.append((m.group(1), disp, "★" in line))
    return out


def group_of(rid):
    return rid[0]


def check_declared_numbers(text, rows):
    """查文档「统计与下一步」里每个自述数字对不对。

    数字读不到也算失败——否则改个措辞就能把这条检查静默绕过去。
    """
    problems = []
    n = len(rows)
    dist = collections.Counter(d for _, d, _ in rows if d)
    grp = collections.Counter(group_of(r) for r, _, _ in rows)
    seed_grp = collections.Counter(group_of(r) for r, d, _ in rows if d == "种子")
    stars = sum(1 for _, _, s in rows if s)
    interrupt = dist.get("打扰机", 0)

    def want(pattern, actual, label, fmt="%d"):
        m = re.search(pattern, text)
        if not m:
            problems.append(f"自述数字读不到: {label}（模式 `{pattern}`）—— 措辞变了，检查器瞎了")
            return None
        return m, fmt % actual, label

    # 总数
    w = want(r"共 \*\*(\d+) 条\*\*规则", n, "规则总数")
    if w and w[0].group(1) != w[1]:
        problems.append(f"总数对不上: 文中 {w[0].group(1)} 实际 {w[1]}")
    # 分组
    w = want(r"分组 A-(\d+) / B-(\d+) / C-(\d+) / D-(\d+) / E-(\d+) / F-(\d+)", 0, "分组计数")
    if w:
        declared = {g: int(w[0].group(i + 1)) for i, g in enumerate("ABCDEF")}
        for g in "ABCDEF":
            if declared[g] != grp.get(g, 0):
                problems.append(f"{g} 组条数对不上: 文中 {declared[g]} 实际 {grp.get(g, 0)}")
    # 处置分布
    for label, key in (("种子", "种子"), ("结构件", "结构件"), ("打扰机", "打扰机"), ("教训", "教训")):
        pat = rf"{label} (\d+)" if label != "种子" else r"种子 (\d+)"
        w = want(pat, dist.get(key, 0), f"处置分布·{label}")
        if w and w[0].group(1) != w[1]:
            problems.append(f"{label} 数对不上: 文中 {w[0].group(1)} 实际 {w[1]}")
    # ★ 数
    w = want(r"标 ★ 的 (\d+) 条", stars, "★ 标记数")
    if w and w[0].group(1) != w[1]:
        problems.append(f"★ 数对不上: 文中 {w[0].group(1)} 实际 {w[1]}")
    # 打扰机占比（连分母一起核，防止拿错的总数算出个像样的百分数）
    w = want(r"打扰机 (\d+) 条，占 (\d+) 条的 (\d+)%", interrupt, "打扰机占比")
    if w:
        if int(w[0].group(1)) != interrupt:
            problems.append(f"打扰机条数二次不一致: 占比句里 {w[0].group(1)} 实际 {interrupt}")
        if int(w[0].group(2)) != n:
            problems.append(f"打扰机占比的分母不对: 文中 {w[0].group(2)} 条 实际总数 {n}")
        pct = round(interrupt * 100 / n) if n else 0
        if int(w[0].group(3)) != pct:
            problems.append(f"打扰机占比对不上: 文中 {w[0].group(3)}% 算出 {pct}%")
    # 种子拆分：括号里逐组相加必须等于标题那个数，且每组等于实际
    w = want(r"B 组 (\d+) \+ C 组 (\d+) \+ D 组 (\d+)", 0, "种子分组拆分")
    if w:
        parts = {g: int(w[0].group(i + 1)) for i, g in enumerate("BCD")}
        for g in "BCD":
            if parts[g] != seed_grp.get(g, 0):
                problems.append(f"种子拆分 {g} 组对不上: 文中 {parts[g]} 实际 {seed_grp.get(g, 0)}")
        head = re.search(r"的种子正好 (\d+) 条", text)
        if not head:
            problems.append("自述数字读不到: 种子总数那句（『的种子正好 N 条』）")
        elif int(head.group(1)) != sum(parts.values()):
            problems.append(f"种子拆分加起来 {sum(parts.values())} 不等于标题声明的 {head.group(1)}")
    # 种子拆分的错误形态（把结构件混进种子）在结构上已经不可能重犯：
    # 拆分只能写成「B 组 N + C 组 N + D 组 N」，每组都与实际处置分布对拍。
    return problems


def check_tables(text):
    problems = []
    lines = text.split("\n")
    i = 0
    tables = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            blk = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                blk.append((i + 1, lines[i].replace("\\|", SEP)))
                i += 1
            tables += 1
            widths = {ln: r.count("|") for ln, r in blk}
            if len(set(widths.values())) != 1:
                problems.append(f"列数不齐 {widths}")
            cells = blk[1][1].replace("|", "").strip() if len(blk) > 1 else ""
            if not cells or not set(cells) <= set("-: "):
                problems.append(f"表头下缺分隔行,行 {blk[0][0]}")
        else:
            i += 1
    return problems, tables


def check_src_coverage(text, src_root):
    """需要旧仓源码的一段：常量抄没抄全 + 函数索引漏没漏。"""
    problems = []
    consts = set()
    for p in (src_root / "src-tauri" / "src").rglob("*.rs"):
        body = p.read_text(encoding="utf-8", errors="replace")
        consts |= set(re.findall(r"pub const ([A-Z][A-Z0-9_]+)\s*:", body))
    fns = set()
    for name, (lo, hi) in SRC_FILES.items():
        path = src_root / "src-tauri" / "src" / name
        lines = path.read_text(encoding="utf-8").split("\n")
        for n in range(lo - 1, min(hi, len(lines))):
            m = re.match(r"\s*(?:pub )?fn (\w+)", lines[n])
            if m:
                fns.add(m.group(1))
    missing = sorted(c for c in ALWAYS_REQUIRED_CONSTS if c not in text)
    if missing:
        problems.append("参数表漏抄: " + ", ".join(missing))
    unpointed = sorted(f for f in fns if f not in text)
    if unpointed:
        problems.append("函数索引漏抄: " + ", ".join(unpointed))
    if consts and not any(c in text for c in consts):
        problems.append("一个常量名都没匹配上 —— 源码路径给错了吗?")
    return problems, len(fns)


def check(doc_text, src_root=None):
    """src_root 为 None 时只跑本仓自足的四类检查。"""
    problems = []
    rows = rule_rows(doc_text)
    if not rows:
        return ["文档里一条规则行都没解析到 —— 表头格式变了?"], 0
    for rid, d, _ in rows:
        if d is None:
            problems.append(f"未标处置: {rid}")
    problems += check_declared_numbers(doc_text, rows)
    tp, tables = check_tables(doc_text)
    problems += tp
    nfns = 0
    if src_root is not None:
        sp, nfns = check_src_coverage(doc_text, src_root)
        problems += sp
    dist = collections.Counter(d or "未分类" for _, d, _ in rows)
    print(f"规则 {len(rows)} 条 / 表格 {tables} 张 / 分组 {dict(sorted(collections.Counter(group_of(r) for r, _, _ in rows).items()))}")
    print("处置分布:", dict(dist), "| ★", sum(1 for _, _, s in rows if s))
    if src_root is None:
        print("[降级] 未对照旧仓源码（常量/函数覆盖这一类没查）—— 要查就加 --src <旧仓路径>")
    else:
        print(f"已对照旧仓源码 {src_root}：覆盖常量 {len(ALWAYS_REQUIRED_CONSTS)} 个 / 函数 {nfns} 个")
    return problems, len(rows)


CASES = {
    "无规则行": ("| X-01 | 只有两列\n|---|", "src_free"),
    "处置未标": ("| A-99 | a | b | c | d | e | 待定 |\n|---|---|---|---|---|---|", "src_free"),
    "自述数字错": (
        "# t\n**口径**：共 **99 条**规则，分组 A-1 / B-0 / C-0 / D-0 / E-0 / F-0；"
        "处置分布 **种子 1（其中标 ★ 的 0 条最该先进目录）** / 结构件 0 / 打扰机 0 条，占 0% / 教训 0。\n"
        "| A-99 | a | b | c | d | e | 种子 |\n|---|---|---|---|---|---|", "src_free"),
    "表格塌陷": ("| A-99 | a | b | c | d | e | 种子 |\n| 漏列 | 种子 |\n", "src_free"),
    "覆盖全缺": ("| A-99 | a | b | c | d | e | 种子 |\n|---|---|---|---|---|---|", "needs_src"),
}


def selftest(src):
    """每段都必须咬住；没执行到的段落要明说，不能算绿。"""
    hits, skipped = {}, []
    for name, (text, kind) in CASES.items():
        if kind == "needs_src" and src is None:
            skipped.append(name)
            continue
        hits[name] = check(text, src)[0]
        print(f"  [{name}] 报出 {len(hits[name])} 项: " + (hits[name][0][:70] if hits[name] else "无"))
    ok = True
    ok &= bool(hits.get("无规则行"))
    ok &= any("未标处置" in p for p in hits.get("处置未标", []))
    ok &= any("对不上" in p or "读不到" in p for p in hits.get("自述数字错", []))
    ok &= any("列数不齐" in p or "缺分隔行" in p for p in hits.get("表格塌陷", []))
    if src is not None:
        h = hits.get("覆盖全缺", [])
        ok &= any("参数表漏抄" in p for p in h) and any("函数索引漏抄" in p for p in h)
    if not ok:
        print("负向对照: 有分支是假的 —— 别信这份自查")
        return 1
    if skipped:
        print(f"负向对照: 已执行的 {len(hits)} 段全咬住了，但跳过了 {skipped}（缺旧仓）—— 这不算全绿")
    else:
        print(f"负向对照: {len(CASES)} 段全咬住了")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=None,
                    help="旧仓路径（给定了才查常量/函数覆盖率）。默认不查，本仓自足。")
    ap.add_argument("--src-if-present", action="store_true",
                    help="按默认位置探测旧仓（父目录的 kvba），在位就多查一类，不在位就降级")
    ap.add_argument("--self", action="store_true", dest="selftest")
    a = ap.parse_args()

    src = None
    if a.src:
        src = pathlib.Path(a.src)
        if not src.exists():
            print(f"[FAIL] 指定了 --src 但路径不存在: {src}")
            return 1
    elif a.src_if_present:
        guess = HERE.parent.parent / "kvba"
        src = guess if guess.exists() else None

    if a.selftest:
        return selftest(src)

    problems, _ = check(DOC.read_text(encoding="utf-8"), src)
    for p in problems:
        print("[LOST] " + p)
    print(f"结论:{'通过' if not problems else str(len(problems)) + ' 项待补'}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
