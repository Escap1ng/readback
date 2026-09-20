"""对拍:压缩 docs/HANDOVER.md 前后,旧版每条事实是否仍在新版(或明确允许的 README)里。
用法:
  python doc-parity.py              # 正常对拍
  python doc-parity.py --self       # 负向对照:故意查一个不存在的标记,脚本必须报缺失并 exit 1
"""
import io
import sys

# (标记, 说明, 允许出现在 README 而非交接报告)
TOKENS = [
    ("防腐拒侵入", "定位", 0), ("MAX_PENDING = 3", "队列上限", 0),
    ("G1", "门控层级", 0), ("阈值 40", "G5", 0), ("25s", "频控", 0),
    ("10min", "冷却", 0), ("20min", "去重", 0),
    ("workunit", "模块", 0), ("insight", "模块", 0), ("workflow.rs", "模块", 0),
    ("memory/", "模块", 0), ("crypto", "模块", 0), ("tray.rs", "模块", 0),
    ("CapsuleDot", "前端", 0), ("CapsulePanel", "前端", 0), ("SettingsView", "前端", 0),
    ("exitCode", "协议", 0), ("Unknown", "不伪造通过", 0),
    ("P1", "唯一生产者", 0), ("interrupts", "投递判据唯一入口", 0),
    ("ANTHROPIC_REQUIRED_MAX", "Anthropic 特例", 0), ("fit_tokens", "输入裁剪", 0),
    ("50KB", "facts 上限", 0), ("3KB", "对话窗口", 0), ("≥20 条", "增量合并触发", 0),
    ("AES-256-GCM", "加密", 0), ("HKDF-SHA256", "密钥派生", 0), ("机器指纹", "密钥来源", 0),
    ("每次保存都是部署", "铁律", 0), ("cargo check", "落盘前", 0),
    ("证伪", "诊断要求", 0), ("静态审计", "结论分级", 0), ("grep", "契约复验", 0),
    ("kvba-plugin.ts", "正本", 0), (".opencode/plugins", "部署副本", 0),
    ("feat:", "提交风格", 0), ("clippy", "门禁", 0), ("vue-tsc", "门禁", 0),
    ("cargo test --locked", "门禁", 0), ("tag", "发布触发", 0),
    ("117", "测试数", 0), ("113", "测试数", 0), ("tokio::test", "测试数口径", 0),
    ("开场破冰", "机制", 0), ("静默期", "用户否决权", 0),
    ("cardsLlm:5", "端到端已通的证据", 0), ("cardsTemplate:0", "同上", 0),
    ("G7 pass=true", "同上", 0), ("19:35", "证据时间", 0),
    ("下线", "第 4 路宿主", 0), ("未清理", "磁盘历史数据", 0),
    ("force", "未闭合1", 0), ("machine_id", "未闭合2", 0),
    ("tsc --strict", "未闭合3", 0), ("修改 {file}", "未闭合4", 0),
    ("编辑 {file}", "未闭合4", 0), ("VibeCounter", "未闭合5 幻觉证据", 0),
    ("508", "未闭合5", 0), ("879", "未闭合5", 0), ("debug_assert", "未闭合5", 0),
    ("release.needs: build", "未闭合8", 0), ("touch_asked", "未闭合9", 0),
    ("12.6", "未闭合10", 0), ("readFileSync(0)", "未闭合10", 0),
    ("p0ReplaceQueue", "未闭合7", 0),
    ("ContractParseErr", "变更1", 0), ("FactsParseErr", "变更1 别名", 0),
    ("ROLLING_MAX_BYTES=512KB", "变更3", 0), ("select_log_lines", "变更3", 0),
    ("note_card_closed", "变更4", 0), ("154KB", "变更3", 0),
    ("dismissed", "变更4", 0), ("status=answered", "变更4 未污染", 0),
    ("564 MB", "清理记录", 0), ("codebase-research", "清理记录", 0),
    ("kvba-data", "保留记录", 0), ("node_modules", "保留记录", 0),
    ("endpoint", "数据目录", 0), ("secrets.enc", "数据目录", 0),
    ("work-units.json", "数据目录", 0), ("insights.json", "数据目录", 0),
    ("KVBA.log", "日志位置", 0), ("cooldown", "数据目录", 0),
    ("RFC-0003", "文档索引", 0), ("release.yml", "文档索引", 0),
    ("InitPrompt.md", "文档索引", 0), ("复盘与工程约定.md", "文档索引", 0),
    ("48×48", "胶囊尺寸", 1), ("active", "三态", 1), ("popup", "三态", 1),
    ("JSONL", "兜底路径", 0), ("LegacyWatcher", "路由分支", 0),
    ("AwaitBoundary", "路由分支", 0), ("decision-log", "决策日志", 0),
]


def load(path):
    try:
        return io.open(path, encoding="utf-8").read()
    except OSError:
        return ""


def compress_check(old_path, new_path, selftest=False):
    """证明一次压缩/改写没丢承重细节:被删行里的 `code`、引号短语、数字必须仍在新文本中。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    old, new = load(old_path), load(new_path)
    if selftest:
        new = ""
    old_lines = [l for l in old.splitlines() if l.strip()]
    new_line_set = set(new.splitlines())
    removed = [l for l in old_lines if l not in new_line_set]
    import re
    pat = re.compile(r"`([^`\n]{2,60})`|[「『\"]([^」』\"]{2,40})[」』\"]|(\d[\d.,kK%×-]{1,12})")
    lost, seen = [], set()
    for line in removed:
        for groups in pat.findall(line):
            tok = next((g for g in groups if g), "")
            key = tok.strip()
            if len(key) < 2 or key in seen or key in new:
                continue
            seen.add(key)
            lost.append((key, line[:60]))
    print(f"删除/改写的行 {len(removed)} 行;抽到承重标记 {len(seen)} 个;在新文本中找不回 {len(lost)} 个")
    for tok, where in lost:
        print(f"  [LOST] {tok!r}  ← 原行: {where}")
    return 1 if lost else 0


def main():
    # 控制台默认 GBK,一旦有缺失要打 ✗/中文就会崩在报告上 —— 检查器必须永远能报出问题
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    argv = sys.argv[1:]
    if "--compress" in argv:
        i = argv.index("--compress")
        return compress_check(argv[i + 1], argv[i + 2], "--self" in argv)
    selftest = "--self" in argv
    docs = load("../docs/HANDOVER.md") or load("docs/HANDOVER.md")
    readme = load("README.md") or load("../README.md")
    if selftest:
        docs = "这是一份被故意掏空的样本,不含任何标记"
        readme = ""
    missing = []
    for token, note, cross_ok in TOKENS:
        hit = token in docs or (bool(cross_ok) and token in readme)
        if not hit:
            missing.append((token, note, cross_ok))
    checked = len(TOKENS)
    print(f"对拍标记 {checked} 个,缺失 {len(missing)} 个")
    for token, note, cross_ok in missing:
        scope = "HANDOVER 或 README" if cross_ok else "HANDOVER"
        print(f"  [MISS] {token!r}  ({note})  应在 {scope}")
    if selftest:
        ok = len(missing) > 0
        print("负向对照:" + ("OK —— 脚本能报出问题" if ok else "FAIL —— 空文档都报不出缺失"))
        return 0 if ok else 1
    return 1 if missing else 0


sys.exit(main())
