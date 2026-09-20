#!/usr/bin/env python3
"""M0 规则清单的自查：抄没抄全、分类分没分完、表格塌没塌。

用法:
  python docs/m0-inventory-check.py [--src ../kvba]        # 正常自查
  python docs/m0-inventory-check.py --self                 # 负向对照:必须报问题并 exit 1

只在 M0 阶段有用:它对照的是前身仓库的源码。等规则迁进新仓、旧仓归档后,
这个脚本应当被删除,而不是留在仓里当"永远绿的检查器"。
"""
import argparse
import collections
import pathlib
import re
import sys

import os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOC = pathlib.Path(__file__).parent / "M0-rules-inventory.md"
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
    return [l for l in text.split("\n") if re.match(r"^\| [A-I]-\d\d \|", l)]


def check(doc_text, src_root):
    problems = []
    rows = rule_rows(doc_text)
    if not rows:
        return ["文档里一条规则行都没解析到 —— 表头格式变了?"]

    # 1) 分类完整性
    for r in rows:
        if not any(d in r for d in DISPOSITIONS):
            problems.append(f"未标处置: {r.split('|')[1].strip()}")

    # 2) 参数覆盖 + 函数覆盖(对照旧仓源码)
    consts = set()
    fns = set()
    for p in (src_root / "src-tauri" / "src").rglob("*.rs"):
        body = p.read_text(encoding="utf-8", errors="replace")
        consts |= set(re.findall(r"pub const ([A-Z][A-Z0-9_]+)\s*:", body))
    for name, (lo, hi) in SRC_FILES.items():
        lines = (src_root / "src-tauri" / "src" / name).read_text(encoding="utf-8").split("\n")
        for n in range(lo - 1, min(hi, len(lines))):
            m = re.match(r"\s*(?:pub )?fn (\w+)", lines[n])
            if m:
                fns.add(m.group(1))
    missing = sorted(c for c in ALWAYS_REQUIRED_CONSTS if c not in doc_text)
    if missing:
        problems.append("参数表漏抄: " + ", ".join(missing))
    unpointed = sorted(f for f in fns if f not in doc_text)
    if unpointed:
        problems.append("函数索引漏抄: " + ", ".join(unpointed))
    if consts and not any(c in doc_text for c in consts):
        problems.append("一个常量名都没匹配上 —— 源码路径给错了吗?")

    # 3) 表格结构
    lines = doc_text.split("\n")
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
    print(f"规则 {len(rows)} 条 / 表格 {tables} 张 / 覆盖常量 {len(ALWAYS_REQUIRED_CONSTS)} 个 / 函数 {len(fns)} 个")
    dist = collections.Counter(
        next((d for d in DISPOSITIONS if d in r), "未分类") for r in rows
    )
    print("处置分布:", dict(dist))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(pathlib.Path(__file__).resolve().parent.parent.parent / "kvba"))
    ap.add_argument("--self", action="store_true", dest="selftest")
    a = ap.parse_args()
    src = pathlib.Path(a.src)
    if not src.exists():
        print(f"[FAIL] 找不到对照源码: {src}(用 --src 指定旧仓路径)")
        return 1
    if a.selftest:
        # 负向对照:三段各自只咬一个分支,任何一段没报问题就说明那个检查是假的
        cases = {
            "无规则行": "| X-01 | 只有两列\n|---|",
            "处置未标": "| A-99 | a | b | c | d | e | 待定 |\n|---|---|---|---|---|---|",
            "覆盖全缺": "| A-99 | a | b | c | d | e | 种子 |\n|---|---|---|---|---|---|",
        }
        hits = {}
        for name, text in cases.items():
            hits[name] = check(text, src)
        ok = bool(hits["无规则行"]) and any("未标处置" in p for p in hits["处置未标"]) \
            and any("参数表漏抄" in p for p in hits["覆盖全缺"]) and any("函数索引漏抄" in p for p in hits["覆盖全缺"])
        for name, probs in hits.items():
            print(f"  [{name}] 报出 {len(probs)} 项: " + (probs[0][:70] if probs else "无"))
        print("负向对照:", "三段都咬住了" if ok else "有分支是假的 —— 别信这份自查")
        return 0 if ok else 1
    problems = check(DOC.read_text(encoding="utf-8"), src)
    for p in problems:
        print("[LOST] " + p)
    print(f"结论:{'通过' if not problems else str(len(problems)) + ' 项待补'}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
