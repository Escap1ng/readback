#!/usr/bin/env python3
"""M0·③ 的可执行验证：把 `m0/schema.sql` 建进内存库，逐条问「这约束真会拒吗」。

  python m0/schema-check.py            # 跑约束 + 迁移 + 证据对拍三组检查
  python m0/schema-check.py --self     # 负向对照：证明上面那些"拒绝"确实是约束造成的
  python m0/schema-check.py --mutation # 反向覆盖：逐条摘掉 CHECK，看有没有哪条摘了没人报

为什么要有这个而不是只写 RFC：散文里的 `NOT NULL` 说明不了任何东西。旧仓复盘 §四 记过一整类
「文档写的和实现不一致」，schema 是最容易写不一致的东西 —— 所以让它可执行、并且可失败。
迁移样本 `m0/legacy-sample.json` 自造（字段名取自旧仓真实结构体），本脚本不需要旧仓在位。
"""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import sqlite3
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = pathlib.Path(__file__).resolve().parent
DDL = (HERE / "schema.sql").read_text(encoding="utf-8")
SAMPLE = json.loads((HERE / "legacy-sample.json").read_text(encoding="utf-8"))
NOW = 1_735_700_000

SEVERITY = {"P0": "blocker", "P1": "high", "P2": "warn", "P3": "info"}


def new_db(ddl=None):
    # 默认取全局 DDL —— `--mutation` 就是靠临时改这个全局来喂变异后的建表语句
    c = sqlite3.connect(":memory:")
    c.executescript(ddl or DDL)
    return c


def norm_path(p):
    """旧仓 §四 02 的教训：拿原始路径字符串做摘要，同一项目在磁盘上会裂成两个目录。"""
    return p.replace("\\", "/").rstrip("/").casefold()


def meta(c):
    c.execute("INSERT INTO meta VALUES (1,?,?,?,?)", (1, 1, NOW, "0.0.0-m0"))


def import_legacy(c, cap_units=1, verified_against=None, sample=None):
    """扁平 JSON → 表。幂等：同一份样本再导一次不产生新行。

    项目身份一律用**归一化路径的摘要**，不沿用旧 JSON 里的 project_id —— 旧仓 §四 02 记的
    就是拿原始路径字符串做摘要，同一项目在盘上裂成两个记忆目录。导入时旧 pid 只作为别名丢弃，
    但它得能查回来，所以记在 label 里。
    """
    sample = sample or SAMPLE
    if not c.execute("SELECT 1 FROM meta WHERE id=1").fetchone():
        meta(c)
    units = sorted(sample["work_units.json"], key=lambda w: w["work_unit"]["end_at"])
    by_path = {}
    for w in units:
        d = hashlib.sha256(norm_path(w["project_path"]).encode()).hexdigest()
        by_path.setdefault(d, []).append(w)
    inserted = pruned = 0
    # 外键让"静默裁掉还有断言指向的记录"变成不可能 —— 这正是从扁平 JSON 换到表买到的东西。
    # 所以 cap 的语义是：保留最近 N 条，外加所有仍被 claim/evidence 引用的条。
    referenced = {i["work_unit_id"] for i in sample["insights.json"]}
    for digest, items in by_path.items():
        c.execute("INSERT OR IGNORE INTO project VALUES (?,?,?,?)",
                  (digest, items[-1]["work_unit"]["project_id"], digest, NOW))
        take = list(items[-cap_units:]) if cap_units else list(items)
        have = {w["work_unit"]["id"] for w in take}
        take += [w for w in items if w["work_unit"]["id"] in referenced and w["work_unit"]["id"] not in have]
        take.sort(key=lambda w: w["work_unit"]["end_at"])
        dropped = len(items) - len(take)
        if dropped:
            pruned += dropped
            c.execute("INSERT INTO pruning_log (unit_id,table_name,dropped,kept_through,reason,at) "
                      "VALUES (?,?,?,?,?,?)",
                      (None, "work_unit", dropped, take[0]["work_unit"]["start_at"],
                       f"import cap={cap_units}", NOW))
        prev = None
        for w in take:
            u = w["work_unit"]
            cs = u["change_set"]
            c.execute(
                "INSERT OR REPLACE INTO work_unit (id,project_id,session_id,goal,mode,start_at,end_at,"
                " branch,base_commit,head_commit,baseline_ok,prev_unit_id,collected_at,source) "
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (u["id"], digest, u["session_id"], u["goal"], u["mode"], u["start_at"], u["end_at"],
                 None, cs["base_ref"], cs["head_ref"], 1 if cs["base_ref"] else 0, prev, NOW, "import"))
            prev = u["id"]
            inserted += 1
            for seq, e in enumerate(u["events"]):
                c.execute("INSERT OR IGNORE INTO event VALUES (?,?,?,?,?)",
                          (e, u["id"], seq, u["end_at"], ""))
            for f in cs["files"]:
                c.execute("INSERT OR REPLACE INTO file_change VALUES (?,?,?,?,?)",
                          (u["id"], f["path"], f["additions"], f["deletions"], f["hunks"]))
            for t in u["tests"]:
                # 旧仓 tests[].evidence 是 "exit 0" 这种文本：退出码是从文本**解析**出来的，
                # 不是协议带回来的。导进来必须保住这个区别，否则就是把猜测写成事实。
                m = re.search(r"exit\s+(-?\d+)", t["evidence"])
                code = int(m.group(1)) if m else None
                c.execute("INSERT OR REPLACE INTO command_run VALUES (?,?,?,?,?,?)",
                          (t["name"], u["id"], t["name"], code,
                           "parsed" if code is not None else "absent", u["end_at"]))
    verif = 0
    for ins in sample["insights.json"]:
        for ev in ins["evidence"]:
            ok = evidence_resolves(ev, verified_against)
            verif += 1 if ok else 0
            c.execute("INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?,?,?)",
                      (f"{ins['id']}:{ev['reference']}", ins["work_unit_id"], ev["kind"],
                       ev["reference"], None, None, ev["excerpt"]))
            c.execute("INSERT OR REPLACE INTO claim (id,unit_id,evidence_id,text,severity,rule_id,"
                      "verified) VALUES (?,?,?,?,?,?,?)",
                      (f"claim:{ins['id']}:{ev['reference']}", ins["work_unit_id"], f"{ins['id']}:{ev['reference']}",
                       ins["conclusion"], SEVERITY.get(ins["risk_level"], "warn"),
                       "imported", 1 if ok else 0))
    return {"units": inserted, "pruned": pruned, "evidence_ok": verif}


def evidence_resolves(ev, tree):
    """P1 的落地方式：断言里的路径/行号/摘录出稿前与本地仓库对拍，核不上就不算已验证。"""
    if not tree:
        return False
    path, _, ln = ev["reference"].partition(":")
    p = pathlib.Path(tree) / path
    if not p.exists():
        return False
    body = p.read_text(encoding="utf-8", errors="replace")
    lines = body.split("\n")
    n = int(ln) if ln.isdigit() else 1
    if n > len(lines):
        return False
    return (not ev["excerpt"]) or ev["excerpt"] in lines[n - 1]


def rejects(c, sql, params):
    try:
        c.execute(sql, params)
        return False
    except sqlite3.Error:
        return True


def cases(c):
    """(名字, 该被拒的插入)。全绿不代表安全 —— 跑 --mutation 逐条摘掉 CHECK，看有没有哪条摘了没人报。"""
    c.execute("INSERT OR IGNORE INTO project VALUES ('p-x','x',?,?)",
              (hashlib.sha256(b"x").hexdigest(), NOW))
    c.execute("INSERT INTO work_unit (id,project_id,mode,start_at,end_at,collected_at,source) "
              "VALUES ('u1','p-x','agent',10,20,?, 'git')", (NOW,))
    # 第二条真存在的 unit：unit_link 的用例必须引用真实行，否则它会被外键拒掉，
    # 于是"CHECK 生效了"是一次张冠李戴的红
    c.execute("INSERT INTO work_unit (id,project_id,mode,start_at,end_at,collected_at,source) "
              "VALUES ('u-b','p-x','human',30,40,?,'git')", (NOW,))
    c.execute("INSERT INTO event VALUES ('seed','u1',0,?,'')", (NOW,))
    c.execute("INSERT INTO evidence (id,unit_id,kind,reference) VALUES ('e1','u1','file','a.rs:1')")
    good_claim = ("INSERT INTO claim (id,unit_id,evidence_id,text,severity) "
                  "VALUES ('c1','u1','e1','有证据的断言','high')")
    c.execute(good_claim)
    return [
        ("外键：claim 挂不存在的证据",
         "INSERT INTO claim (id,unit_id,evidence_id,text,severity) VALUES ('x','u1','nope','文','high')"),
        ("CHECK：断言正文为空就不许发声",
         "INSERT INTO claim (id,unit_id,evidence_id,text,severity) VALUES ('x2','u1','e1','   ','high')"),
        ("CHECK：严重度只能是四档",
         "INSERT INTO claim (id,unit_id,evidence_id,text,severity) VALUES ('x3','u1','e1','文','urgent')"),
        ("CHECK：end_at 不能早于 start_at",
         "INSERT INTO work_unit (id,project_id,mode,start_at,end_at,collected_at,source) "
         "VALUES ('u2','p-x','agent',30,20,?, 'git')"),
        ("CHECK：有退出码必须有来源",
         "INSERT INTO command_run (id,unit_id,cmd,exit_code,exit_code_src,ran_at) "
         "VALUES ('t1','u1','cargo test',0,'absent',?)"),
        ("CHECK：没退出码却声称 structured 是伪造通过",
         "INSERT INTO command_run (id,unit_id,cmd,exit_code,exit_code_src,ran_at) "
         "VALUES ('t2','u1','cargo test',NULL,'structured',?)"),
        ("CHECK：unit_link 不许自己连自己",
         "INSERT INTO unit_link VALUES ('u1','u1','follows',1.0)"),
        ("CHECK：置信度必须在 0..1",
         "INSERT INTO unit_link VALUES ('u1','u-b','duplicates',1.5)"),
        ("STRICT：tokens_in 塞字符串",
         "INSERT INTO work_unit (id,project_id,mode,start_at,end_at,collected_at,source,tokens_in) "
         "VALUES ('u3','p-x','agent',1,2,?,'git','很多')"),
        ("CHECK：答了却没结论不行",
         "INSERT INTO human_answer (id,unit_id,asked_at,answered_at,verdict) "
         "VALUES ('h1','u1',?,?,'pending')"),
        ("CHECK：判 wrong 却没复述内容也没标 skipped",
         "INSERT INTO human_answer (id,unit_id,asked_at,answered_at,restatement,verdict) "
         "VALUES ('h2','u1',?,?, '','wrong')"),
        ("CHECK：min_reader 不得高于 schema_version",
         "INSERT INTO meta VALUES (1,1,2,?,'0.0.0')"),
        ("CHECK：裁剪日志的 dropped 必须 > 0",
         "INSERT INTO pruning_log (table_name,dropped,kept_through,reason,at) VALUES ('work_unit',0,1,'r',?)"),
        ("CHECK：证据行号区间不许倒挂",
         "INSERT INTO evidence (id,unit_id,kind,reference,line_start,line_end) VALUES ('e2','u1','file','a.rs',9,3)"),
        ("CHECK：路径摘要长度不足",
         "INSERT INTO project VALUES ('p-y','y','too-short',?)"),
        ("CHECK：路径摘要 64 位但不是十六进制",
         # 只有 length()=64 的话这条就混进去了 —— GLOB 那半边约束的存在理由
         "INSERT INTO project VALUES ('p-z','z','" + "z" * 64 + "',?)"),
        ("UNIQUE：同一 unit 里 seq 不能重复",
         "INSERT INTO event VALUES ('e9','u1',0,?,'')"),
        # ↓ 下面 22 条是 `--mutation` 逼出来的：它逐条把 CHECK 摘成 CHECK (1)，
        #   摘之前有 23 条约束摘掉后没有任何用例会变红 —— 那些 CHECK 写没写都一样。
        ("CHECK：meta 只许一行（id=1）",
         "INSERT INTO meta VALUES (2,1,1,?,'0.0.0')"),
        ("CHECK：min_reader 至少 1",
         "INSERT INTO meta VALUES (1,1,0,?,'0.0.0')"),
        # schema_version>=1 那条已删（--mutation 证明它被下面两条蕴含）。这里守的还是同一个下界：
        # min_reader 至少 1 ⇒ schema_version 不可能为 0 而仍合法
        ("CHECK：schema_version=0 进不来（蕴含自 min_reader 两条）",
         "INSERT INTO meta VALUES (1,0,1,?,'0.0.0')"),
        ("CHECK：项目别名不许空白",
         "INSERT INTO project VALUES ('p-l','   ','" + "a" * 64 + "',?)"),
        ("CHECK：mode 只许三档",
         "INSERT INTO work_unit (id,project_id,mode,start_at,end_at,collected_at,source) "
         "VALUES ('u-m','p-x','bot',1,2,?,'git')"),
        ("CHECK：baseline_ok 只能 0/1",
         "INSERT INTO work_unit (id,project_id,mode,start_at,end_at,collected_at,source,baseline_ok) "
         "VALUES ('u-bl','p-x','agent',1,2,?,'git',5)"),
        ("CHECK：tokens_in 不许为负",
         "INSERT INTO work_unit (id,project_id,mode,start_at,end_at,collected_at,source,tokens_in) "
         "VALUES ('u-ti','p-x','agent',1,2,?,'git',-1)"),
        ("CHECK：tokens_out 不许为负",
         "INSERT INTO work_unit (id,project_id,mode,start_at,end_at,collected_at,source,tokens_out) "
         "VALUES ('u-to','p-x','agent',1,2,?,'git',-1)"),
        ("CHECK：成本（毫微单位）不许为负",
         "INSERT INTO work_unit (id,project_id,mode,start_at,end_at,collected_at,source,cost_usd_milli) "
         "VALUES ('u-co','p-x','agent',1,2,?,'git',-1)"),
        ("CHECK：来源只许 git/transcript/hook/import",
         "INSERT INTO work_unit (id,project_id,mode,start_at,end_at,collected_at,source) "
         "VALUES ('u-src','p-x','agent',1,2,?,'magic')"),
        ("CHECK：unit_link 的 kind 只许四档",
         "INSERT INTO unit_link VALUES ('u1','u-b','supersedes',1.0)"),
        ("CHECK：事件 seq 不许为负",
         "INSERT INTO event VALUES ('e-neg','u1',-1,?,'')"),
        ("CHECK：命令不许空白",
         "INSERT INTO command_run (id,unit_id,cmd,exit_code,exit_code_src,ran_at) "
         "VALUES ('t-c','u1','  ',0,'parsed',?)"),
        ("CHECK：退出码来源只许四档",
         "INSERT INTO command_run (id,unit_id,cmd,exit_code,exit_code_src,ran_at) "
         "VALUES ('t-s','u1','cargo test',0,'guessed',?)"),
        ("CHECK：additions 不许为负",
         "INSERT INTO file_change VALUES ('u1','a.rs',-1,0,0)"),
        ("CHECK：deletions 不许为负",
         "INSERT INTO file_change VALUES ('u1','d.rs',0,-1,0)"),
        ("CHECK：hunks 不许为负",
         "INSERT INTO file_change VALUES ('u1','h.rs',0,0,-1)"),
        ("CHECK：证据 kind 只许六档",
         "INSERT INTO evidence (id,unit_id,kind,reference) VALUES ('e-k','u1','vibes','a.rs:1')"),
        ("CHECK：证据引用不许空白",
         "INSERT INTO evidence (id,unit_id,kind,reference) VALUES ('e-r','u1','file','   ')"),
        ("CHECK：verified 只能 0/1",
         "INSERT INTO claim (id,unit_id,evidence_id,text,severity,verified) "
         "VALUES ('c-v','u1','e1','文','high',2)"),
        # 带复述内容，才只违反 verdict 那一档 —— 否则它会连带撞上"答了要复述"那条
        ("CHECK：人工判定只许五档",
         "INSERT INTO human_answer (id,unit_id,asked_at,answered_at,verdict,restatement) "
         "VALUES ('h-v','u1',?,?,'guessed','我复述了')"),
        ("CHECK：裁剪日志的表名不许空白",
         "INSERT INTO pruning_log (table_name,dropped,kept_through,reason,at) "
         "VALUES ('  ',1,1,'r',?)"),
        ("CHECK：裁剪日志必须写原因",
         "INSERT INTO pruning_log (table_name,dropped,kept_through,reason,at) "
         "VALUES ('work_unit',1,1,'  ',?)"),
    ]


def run(conn=None):
    c = conn or new_db()
    res = []
    for name, sql in cases(c):
        res.append((name, rejects(c, sql, (NOW,) * sql.count("?"))))
    return res


def normal():
    checks = []
    c = new_db()
    stats = import_legacy(c, cap_units=1)
    checks.append(("cap=1 时导入 3 条、裁掉 1 条（被断言引用的那条不许裁）",
                   stats["units"] == 3 and stats["pruned"] == 1))
    checks.append(("被裁掉这件事留在了 pruning_log 里",
                   c.execute("SELECT COUNT(*) FROM pruning_log").fetchone()[0] == 1))
    checks.append(("幂等：导两次数据行数不变（裁剪日志按事件各记一次，不去重）", _idempotent()))
    checks.append(("退出码从文本解析的必须标 parsed，不许标 structured",
                   c.execute("SELECT exit_code_src FROM command_run WHERE exit_code=0").fetchone()[0] == "parsed"))
    checks.append(("同一项目的两种路径写法只能落成一个 project", _path_variants()))
    c2 = new_db()
    import_legacy(c2, cap_units=0)
    checks.append(("cap=0 全量导入后 unit 链建起来了（alpha 3 条 → 2 条 prev）",
                   c2.execute("SELECT COUNT(*) FROM work_unit WHERE prev_unit_id IS NOT NULL").fetchone()[0] == 2))
    checks.append(("缺基线的那次导入把 baseline_ok 记成 0，不假装采集到了",
                   c2.execute("SELECT baseline_ok FROM work_unit WHERE id='wu-0002'").fetchone()[0] == 0))
    tree = pathlib.Path(tempfile.mkdtemp(prefix="rbtree"))
    try:
        (tree / "src").mkdir()
        # 样本里那条证据写的是 `src/report.rs:11`，所以这棵树必须真有第 11 行；
        # 造不满 11 行就是拿用例子的巧合冒充测试
        (tree / "src" / "report.rs").write_text(
            "\n".join([f"// filler line {i}" for i in range(1, 11)]
                      + ["pub fn severity(v: &str) -> &'static str {", "    v", "}"]) + "\n",
            encoding="utf-8")
        c3 = new_db()
        out = import_legacy(c3, cap_units=0, verified_against=tree)
        checks.append(("3 条证据里只有 1 条真能在仓库里落地", out["evidence_ok"] == 1))
        checks.append(("幽灵证据支撑的断言被标 verified=0（P1 闸门要扫的就是它）",
                       c3.execute("SELECT COUNT(*) FROM claim WHERE verified=0").fetchone()[0] == 2))
        checks.append(("对拍成功的断言标 verified=1",
                       c3.execute("SELECT COUNT(*) FROM claim WHERE verified=1").fetchone()[0] == 1))
        blocked = rejects(c3, "DELETE FROM evidence WHERE id=?", ("in-0001:src/report.rs:11",))
        checks.append(("有断言挂着的证据删不掉（ON DELETE RESTRICT 真在拦）", blocked))
    finally:
        shutil.rmtree(tree, ignore_errors=True)
    checks += [(n, ok) for n, ok in run(new_db())]
    return checks


def _idempotent():
    c = new_db()
    import_legacy(c, cap_units=1)
    import_legacy(c, cap_units=1)
    return c.execute("SELECT COUNT(*) FROM work_unit").fetchone()[0] == 3 \
        and c.execute("SELECT COUNT(*) FROM pruning_log").fetchone()[0] == 2


def _path_variants():
    s = json.loads(json.dumps(SAMPLE))
    s["work_units.json"][0]["project_path"] = "C:\\Somewhere\\Alpha\\"   # 同一目录，另一种写法
    c = new_db()
    import_legacy(c, cap_units=0, sample=s)
    return c.execute("SELECT COUNT(*) FROM project").fetchone()[0] == 2  # alpha + beta，不裂成 3


def selftest():
    """负向对照（条数由下面的 `out` 自己报）：证明 normal() 那些"拒绝"确实是约束造成的，不是别的原因。"""
    out = {}
    # ① 外键那条测试依赖 PRAGMA —— 关掉后必须能插进去，否则它拒的不是外键
    c = new_db()
    c.executescript("PRAGMA foreign_keys=OFF;")
    res_off = run(c)
    out["关掉外键后，dangling-FK 那条必须插得进去"] = not any(
        n.startswith("外键") and ok for n, ok in res_off)
    # ② 摘掉退出码那条 CHECK 后，同一条坏数据必须能进 —— 否则"拒绝"跟 CHECK 无关。
    # 连带它前面那个逗号一起摘，不然建表语法先断 —— 断在建表上不算"约束失效被证伪"。
    mutated = re.sub(r",\s*(?:--[^\n]*\n\s*)*CHECK "
                     r"\(\(exit_code IS NULL\) = \(exit_code_src = 'absent'\)\)", "", DDL)
    out["schema.sql 里找不到那条 CHECK（说明被改写了）"] = mutated != DDL
    c2 = new_db(mutated)
    c2.execute("INSERT OR IGNORE INTO project VALUES ('p-x','x',?,?)",
               (hashlib.sha256(b"x").hexdigest(), NOW))
    c2.execute("INSERT INTO work_unit (id,project_id,mode,start_at,end_at,collected_at,source) "
               "VALUES ('u1','p-x','agent',10,20,?, 'git')", (NOW,))
    out["摘掉 CHECK 后，声称 structured 却没码的行必须进得来"] = not rejects(
        c2, "INSERT INTO command_run (id,unit_id,cmd,exit_code,exit_code_src,ran_at) "
            "VALUES ('t9','u1','cargo test',NULL,'structured',?)", (NOW,))
    # ③ 摘掉摘要 CHECK 的"十六进制"那半边：非 hex 的 64 位必须进得来，而长度不足那条
    #    仍要被拒 —— 两边各挡各的，才说明这半个约束不是装饰
    no_hex = re.sub(r"\s*AND\s+path_digest NOT GLOB '\*\[\^0-9a-f\]\*'", "", DDL)
    out["schema.sql 里找不到摘要 CHECK 的十六进制那半边"] = no_hex != DDL
    c3 = new_db(no_hex)
    c3.execute("INSERT OR IGNORE INTO project VALUES ('p-a','a',?,?)",
               (hashlib.sha256(b"a").hexdigest(), NOW))
    z64 = "INSERT INTO project VALUES ('p-z','z','" + "z" * 64 + "',?)"
    out["摘掉十六进制半边后，64 个 z 必须进得来"] = not rejects(c3, z64, (NOW,))
    out["摘掉它之后长度半边还得在（短摘要仍被拒）"] = rejects(
        c3, "INSERT INTO project VALUES ('p-b','b','too-short',?)", (NOW,))
    # ④ 裁剪日志必须是被 cap 逼出来的，不是导入路径自己乱写
    big = new_db()
    stats = import_legacy(big, cap_units=99)
    out["cap 设大到不裁剪时，pruning_log 必须是空的"] = (
        stats["pruned"] == 0 and big.execute("SELECT COUNT(*) FROM pruning_log").fetchone()[0] == 0)
    for k, v in out.items():
        print(f"  [{'咬住' if v else '没咬住'}] {k}")
    miss = [k for k, v in out.items() if not v]
    ok = not miss
    print(f"负向对照: {len(out)} 段全咬住" if ok else f"负向对照: {len(miss)}/{len(out)} 段没咬住 —— 别信这份 schema 检查")
    return 0 if ok else 1


def check_clauses(ddl):
    """抽出每个顶层 `CHECK (…)` 的 (起, 止, 文本, 所属表)。按位置摘，不按文本 —— 同名子句可能不止一处。"""
    marks = [(mm.start(), mm.group(1)) for mm in re.finditer(r"CREATE TABLE (\w+)", ddl)]
    out, i = [], 0
    while True:
        j = ddl.find("CHECK (", i)
        if j < 0:
            return out
        k, depth = j + len("CHECK ("), 1
        while depth and k < len(ddl):
            depth += 1 if ddl[k] == "(" else (-1 if ddl[k] == ")" else 0)
            k += 1
        out.append((j, k, ddl[j:k], [t for pos, t in marks if pos < j][-1]))
        i = k


def mutation():
    """反向覆盖：逐条把 CHECK 摘成 CHECK (1)，看有没有用例因此变红。

    摘了没人报 = 那条约束写没写都一样。全绿的检查清单证明不了自己被满足过，
    只证明它没人试着违反过 —— 这就是 --mutation 存在的全部理由。
    """
    global DDL
    clauses, dead = check_clauses(DDL), []
    original = DDL
    for start, end, text, owner in clauses:
        DDL = original[:start] + "CHECK (1)" + original[end:]
        bad = [n for n, ok in normal() if not ok]
        if not bad:
            dead.append((owner, " ".join(text.split())))
        print(f"  [{'红了' if bad else '没人报'}] {owner:14s} {' '.join(text.split())[:64]}")
    DDL = original
    print(f"约束反向覆盖: {len(clauses) - len(dead)}/{len(clauses)} 条 CHECK 摘掉后有用例变红"
          + (f"；{len(dead)} 条摘了没人报 —— 上面的检查清单是假绿" if dead else "，无漏"))
    return 1 if dead else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self", action="store_true", dest="st")
    ap.add_argument("--mutation", action="store_true")
    a = ap.parse_args()
    if a.st:
        return selftest()
    if a.mutation:
        return mutation()
    checks = normal()
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  [{'OK  ' if ok else 'FAIL'}] {n}")
    print(f"检查 {len(checks)} 项 / 未过 {len(bad)}")
    if bad:
        print("未过：" + "；".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
