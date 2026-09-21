-- readback 账本 schema · M0·③ 提案（配套说明见 docs/RFC-0005-sqlite-ledger.md）
-- 这份文件是可执行的：python m0/schema-check.py 会把它建到 :memory: 并逐条验证约束真会拒。
-- 版本策略见 meta 表与 RFC §5；不要就地改这里的列而不动 schema_version。

PRAGMA foreign_keys = ON;

-- 单一真源：读端要求 >= min_reader，写端只写当前版本
CREATE TABLE meta (
  id            INTEGER PRIMARY KEY CHECK (id = 1),
  -- 不单独写 schema_version >= 1：下面那条例程已经蕴含它
  -- （min_reader >= 1 且 min_reader <= schema_version ⇒ schema_version >= 1）。
  -- `python m0/schema-check.py --mutation` 摘掉它时没有任何用例会变红 —— 冗余约束就删掉，别留装饰。
  schema_version INTEGER NOT NULL,
  min_reader    INTEGER NOT NULL CHECK (min_reader >= 1 AND min_reader <= schema_version),
  created_at    INTEGER NOT NULL,
  product_version TEXT NOT NULL
) STRICT;

CREATE TABLE project (
  id         TEXT PRIMARY KEY,          -- 稳定摘要，不是原始路径（旧仓 §四 02 的教训）
  label      TEXT NOT NULL CHECK (length(trim(label)) > 0),
  path_digest TEXT NOT NULL CHECK (length(path_digest) = 64
                                   AND path_digest NOT GLOB '*[^0-9a-f]*'),  -- sha256(hex)：长度对、字符不对也要拒
  first_seen INTEGER NOT NULL
) STRICT;

CREATE TABLE work_unit (
  id           TEXT PRIMARY KEY,
  project_id   TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  session_id   TEXT,
  goal         TEXT NOT NULL DEFAULT '',
  mode         TEXT NOT NULL CHECK (mode IN ('agent','human','unknown')),
  start_at     INTEGER NOT NULL,
  end_at       INTEGER NOT NULL CHECK (end_at >= start_at),
  -- ↓ 四个字段就是 RFC-0004 §2.3 点名的"账本没存"，逐个闭合
  branch       TEXT,                    -- 缺口①：分支
  base_commit  TEXT,                    -- 缺口③：回合起始基线（旧仓只有 base_ref:Option，且回合内提交看不见）
  head_commit  TEXT,
  baseline_ok  INTEGER NOT NULL DEFAULT 0 CHECK (baseline_ok IN (0,1)),
  tokens_in    INTEGER CHECK (tokens_in  IS NULL OR tokens_in  >= 0),   -- 缺口②：token 与成本
  tokens_out   INTEGER CHECK (tokens_out IS NULL OR tokens_out >= 0),
  cost_usd_milli INTEGER CHECK (cost_usd_milli IS NULL OR cost_usd_milli >= 0),
  provider     TEXT,
  prev_unit_id TEXT REFERENCES work_unit(id) ON DELETE SET NULL,          -- 缺口④：unit 链（同一线的前一个）
  collected_at INTEGER NOT NULL,
  source       TEXT NOT NULL CHECK (source IN ('git','transcript','hook','import'))
) STRICT;

-- 缺口④的另一半：跨会话/跨分支的关联不是链而是边，所以单独一张表，且禁自环
CREATE TABLE unit_link (
  unit_id     TEXT NOT NULL REFERENCES work_unit(id) ON DELETE CASCADE,
  related_id  TEXT NOT NULL REFERENCES work_unit(id) ON DELETE CASCADE,
  kind        TEXT NOT NULL CHECK (kind IN ('follows','duplicates','reverts','same-goal')),
  confidence  REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
  PRIMARY KEY (unit_id, related_id, kind),
  CHECK (unit_id <> related_id)
) STRICT;

CREATE TABLE event (
  id        TEXT NOT NULL,
  unit_id   TEXT NOT NULL REFERENCES work_unit(id) ON DELETE CASCADE,
  seq       INTEGER NOT NULL CHECK (seq >= 0),
  ts        INTEGER NOT NULL,
  tool_name TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (unit_id, id),
  UNIQUE (unit_id, seq)
) STRICT;

-- M0·② 尚未证伪，所以 exit_code 必须可空，且"有没有"要说清来源
CREATE TABLE command_run (
  id            TEXT NOT NULL,
  unit_id       TEXT NOT NULL REFERENCES work_unit(id) ON DELETE CASCADE,
  cmd           TEXT NOT NULL CHECK (length(trim(cmd)) > 0),
  exit_code     INTEGER,
  exit_code_src TEXT NOT NULL DEFAULT 'absent'
                CHECK (exit_code_src IN ('structured','parsed','inferred','absent')),
  ran_at        INTEGER NOT NULL,
  PRIMARY KEY (unit_id, id),
  -- 有码必须有来源；没码只能记 absent —— 这条 CHECK 就是"不许伪造通过"的结构化落点。
  -- 至于 'inferred' 能不能算证据，是应用层判断，别写成 SQL 里不存在的函数。
  CHECK ((exit_code IS NULL) = (exit_code_src = 'absent'))
) STRICT;

CREATE TABLE file_change (
  unit_id   TEXT NOT NULL REFERENCES work_unit(id) ON DELETE CASCADE,
  path      TEXT NOT NULL,
  additions INTEGER NOT NULL CHECK (additions >= 0),
  deletions INTEGER NOT NULL CHECK (deletions >= 0),
  hunks     INTEGER NOT NULL CHECK (hunks >= 0),
  PRIMARY KEY (unit_id, path)
) STRICT;

CREATE TABLE evidence (
  id         TEXT PRIMARY KEY,
  unit_id    TEXT NOT NULL REFERENCES work_unit(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL CHECK (kind IN ('file','diff','command','test','doc','record')),
  reference  TEXT NOT NULL CHECK (length(trim(reference)) > 0),   -- 路径 / commit / 命令 id
  line_start INTEGER,
  line_end   INTEGER,
  excerpt    TEXT NOT NULL DEFAULT '',
  CHECK (line_start IS NULL OR line_end IS NULL OR line_end >= line_start)
) STRICT;

-- P1「无证据不出声」的结构化落点：断言必须挂至少一条证据
CREATE TABLE claim (
  id          TEXT PRIMARY KEY,
  unit_id     TEXT NOT NULL REFERENCES work_unit(id) ON DELETE CASCADE,
  evidence_id TEXT NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,
  text        TEXT NOT NULL CHECK (length(trim(text)) > 0),
  severity    TEXT NOT NULL CHECK (severity IN ('info','warn','high','blocker')),
  rule_id     TEXT NOT NULL DEFAULT '',
  verified    INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0,1)),  -- 0 = 未与本地仓库对拍成功
  verified_at INTEGER
) STRICT;

-- 缺口⑤：人工结论必须能回指到 unit 与 claim（M3 的复述队列靠它算通过率）
CREATE TABLE human_answer (
  id          TEXT PRIMARY KEY,
  unit_id     TEXT NOT NULL REFERENCES work_unit(id) ON DELETE CASCADE,
  claim_id    TEXT REFERENCES claim(id) ON DELETE SET NULL,
  asked_at    INTEGER NOT NULL,
  answered_at INTEGER,
  restatement TEXT NOT NULL DEFAULT '',
  verdict     TEXT NOT NULL DEFAULT 'pending'
              CHECK (verdict IN ('pending','correct','partial','wrong','skipped')),
  CHECK (answered_at IS NULL OR verdict <> 'pending'),
  CHECK (verdict = 'pending' OR length(trim(restatement)) > 0 OR verdict = 'skipped')
) STRICT;

-- M0-rules-inventory.md §H 最后一行：任何裁剪都要留"被裁掉 N 条"的痕，不然账本自己会撒谎
CREATE TABLE pruning_log (
  id           INTEGER PRIMARY KEY,
  unit_id      TEXT REFERENCES work_unit(id) ON DELETE SET NULL,
  table_name   TEXT NOT NULL CHECK (length(trim(table_name)) > 0),
  dropped      INTEGER NOT NULL CHECK (dropped > 0),
  kept_through INTEGER NOT NULL,
  reason       TEXT NOT NULL CHECK (length(trim(reason)) > 0),
  at           INTEGER NOT NULL
) STRICT;

CREATE INDEX idx_unit_project_time ON work_unit(project_id, end_at DESC);
CREATE INDEX idx_unit_prev        ON work_unit(prev_unit_id) WHERE prev_unit_id IS NOT NULL;
CREATE INDEX idx_claim_unit       ON claim(unit_id);
CREATE INDEX idx_claim_unverified ON claim(unit_id) WHERE verified = 0;   -- 出稿前的闸门扫这张
CREATE INDEX idx_answer_pending   ON human_answer(unit_id) WHERE verdict = 'pending';
