-- ============================================================================
-- Claybank — 0001_core.sql
-- Shared core schema: applied identially to the server store (authoritative)
-- and the device store (complete replica). Server-only and device-only
-- additions live in 0002_server.sql / 0003_device.sql.
--
-- Conventions (Docs/GLOSSARY.md, Docs/DataModel.md):
--   * ids are UUIDv7 TEXT; times are ISO-8601 UTC "Z" TEXT
--   * kind enum: video | article | unknown  (one enum, same as api/schemas)
--   * folders are the ONLY container: zero or one folder per save, depth <= 3
--   * reserved folder names rejected at the DB level, not just the API
--   * media is never stored: no BLOB columns except the embedding vectors,
--     which are DERIVED from text (rebuildable) and pinned by index_meta
--   * confidence / suggestion / processing state are job+save metadata,
--     NEVER contents of note frontmatter
--   * agent_trace is stored on the job but EXCLUDED from sync payloads
-- ============================================================================

PRAGMA foreign_keys = ON;
-- Device replica also runs WAL for concurrent reads while the pipeline writes.
PRAGMA journal_mode = WAL;

-- ----------------------------------------------------------------------------
-- folders — the only container; projects with a finish line, not topic shelves
-- ----------------------------------------------------------------------------
CREATE TABLE folders (
  id          TEXT PRIMARY KEY,
  parent_id   TEXT REFERENCES folders(id) ON DELETE RESTRICT,
  name        TEXT NOT NULL COLLATE NOCASE,
  depth       INTEGER NOT NULL DEFAULT 0 CHECK (depth BETWEEN 0 AND 3),
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  archived_at TEXT,
  -- Reserved names (Rules.md §3) — the Inbox is a state, not a folder:
  CHECK (UPPER(name) NOT IN ('OTHER', 'MISC', 'UNSORTED', 'INBOX'))
);

-- depth must be 0 for roots...
CREATE TRIGGER trg_folders_root_depth
AFTER INSERT ON folders
WHEN NEW.parent_id IS NULL
BEGIN
  SELECT CASE WHEN NEW.depth <> 0
    THEN RAISE(ABORT, 'folder_depth_exceeded') END;
END;

-- ...parent.depth+1 for children, and only onto non-archived parents.
CREATE TRIGGER trg_folders_child_depth
AFTER INSERT ON folders
WHEN NEW.parent_id IS NOT NULL
BEGIN
  SELECT CASE WHEN NEW.depth <> (SELECT depth + 1 FROM folders WHERE id = NEW.parent_id)
    THEN RAISE(ABORT, 'folder_depth_exceeded') END;
  SELECT CASE WHEN (SELECT archived_at FROM folders WHERE id = NEW.parent_id) IS NOT NULL
    THEN RAISE(ABORT, 'folder_archived') END;
END;

CREATE TRIGGER trg_folders_reparent_depth
AFTER UPDATE OF parent_id ON folders
WHEN NEW.parent_id IS NOT NULL
BEGIN
  SELECT CASE WHEN NEW.depth <> (SELECT depth + 1 FROM folders WHERE id = NEW.parent_id)
    THEN RAISE(ABORT, 'folder_depth_exceeded') END;
END;

-- ----------------------------------------------------------------------------
-- saves — capture is durable; extraction fields arrive later (enrichment)
-- ----------------------------------------------------------------------------
CREATE TABLE saves (
  id                         TEXT PRIMARY KEY,
  raw_url                    TEXT NOT NULL,             -- as captured
  url                        TEXT NOT NULL,             -- canonicalized (dup key)
  platform                   TEXT NOT NULL,             -- derived from host (server-computed)
  source_app                 TEXT NOT NULL DEFAULT 'unknown',
  user_context               TEXT NOT NULL DEFAULT '',
  kind                       TEXT NOT NULL DEFAULT 'unknown'
                             CHECK (kind IN ('video', 'article', 'unknown')),
  has_audio                  INTEGER NOT NULL DEFAULT 0 CHECK (has_audio IN (0,1)),
  has_timeline               INTEGER NOT NULL DEFAULT 0 CHECK (has_timeline IN (0,1)),
  has_images                 INTEGER NOT NULL DEFAULT 0 CHECK (has_images IN (0,1)),
  duration                   INTEGER CHECK (duration IS NULL OR duration >= 0),
  title                      TEXT,
  needs_review               INTEGER NOT NULL DEFAULT 0 CHECK (needs_review IN (0,1)),
  -- zero or one folder per save; NULL = Inbox-as-state:
  folder_id                  TEXT REFERENCES folders(id) ON DELETE SET NULL,
  -- ONE suggested folder per save — both columns or neither (metadata layer):
  suggested_folder_path      TEXT,
  suggested_folder_confidence REAL CHECK (suggested_folder_confidence IS NULL
                                          OR (suggested_folder_confidence >= 0
                                             AND suggested_folder_confidence <= 1)),
  captured_by_device         TEXT,
  user_id                    TEXT,                      -- device replica stores the owner id only
  captured_at                TEXT NOT NULL,
  created_at                 TEXT NOT NULL,
  updated_at                 TEXT NOT NULL,
  CHECK ((suggested_folder_path IS NULL) = (suggested_folder_confidence IS NULL))
);

CREATE INDEX idx_saves_folder   ON saves(folder_id);
CREATE INDEX idx_saves_review   ON saves(needs_review) WHERE needs_review = 1;
CREATE INDEX idx_saves_captured ON saves(captured_at DESC);

-- canonicalized url is the duplicate key: second capture => 409 already_saved
CREATE UNIQUE INDEX idx_saves_url ON saves(url);

-- ----------------------------------------------------------------------------
-- tags — flat labels, many per save, case-insensitively unique; NOT containers
-- ----------------------------------------------------------------------------
CREATE TABLE tags (
  id   TEXT PRIMARY KEY,
  name TEXT NOT NULL COLLATE NOCASE UNIQUE
);

CREATE TABLE save_tags (
  save_id TEXT NOT NULL REFERENCES saves(id) ON DELETE CASCADE,
  tag_id  TEXT NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
  PRIMARY KEY (save_id, tag_id)
);

-- ----------------------------------------------------------------------------
-- notes — ONE per save; markdown is the source of truth (ADR 0005).
-- Frontmatter facts are parsed into typed columns ON WRITE (app-side) so the
-- indexer never re-parses arbitrary yaml. Re-litigate in 0005, not here.
-- ----------------------------------------------------------------------------
CREATE TABLE notes (
  save_id         TEXT PRIMARY KEY REFERENCES saves(id) ON DELETE CASCADE,
  markdown        TEXT NOT NULL,
  -- parsed stable facts (mirror of frontmatter; folder_path kept in sync by
  -- the app on folder rename/move — it is a bulk rewrite, see ADR 0005):
  source          TEXT,
  channel         TEXT,
  video_url       TEXT,
  duration        INTEGER,
  published       TEXT,
  saved_date      TEXT,
  folder_path     TEXT,
  tags_json       TEXT NOT NULL DEFAULT '[]',
  -- LLM-guaranteed sections + dynamic ones live INSIDE markdown; these parsed
  -- columns exist only for fast search/Ask reads:
  overview        TEXT,
  key_points_json TEXT,
  links_json      TEXT,
  transcript      TEXT,        -- TEXT ONLY; audio/video never persisted (ADR 0004)
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

-- section index (write-time, from markdown headings): powers match reasons
-- and jump targets ("match in transcript at 0:42")
CREATE TABLE note_sections (
  save_id   TEXT NOT NULL REFERENCES notes(save_id) ON DELETE CASCADE,
  heading   TEXT NOT NULL,
  anchor    TEXT NOT NULL,       -- e.g. "0:42" or heading slug
  seq       INTEGER NOT NULL,
  PRIMARY KEY (save_id, seq)
);

-- ----------------------------------------------------------------------------
-- jobs — one pipeline per save; states streamed, stages skippable/failed
-- ----------------------------------------------------------------------------
CREATE TABLE jobs (
  save_id       TEXT PRIMARY KEY REFERENCES saves(id) ON DELETE CASCADE,
  state         TEXT NOT NULL CHECK (state IN
                 ('queued','extracting','transcribing','analyzing','sorting','ready')),
  tier          INTEGER NOT NULL CHECK (tier IN (1, 2)),
  error         TEXT,
  skipped_json  TEXT NOT NULL DEFAULT '[]',
  failed_json   TEXT NOT NULL DEFAULT '[]',
  timing_json   TEXT,           -- per-stage durations (30s target / 2min cap)
  agent_trace   TEXT,           -- tier 2 ONLY; EXCLUDED from sync payloads
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- extraction cache — last tier's ExtractionResult per save (debug + tier-2
-- gating "did this kind get its required fields?"). Transient media never
-- lands here — TEXT ONLY.
-- ----------------------------------------------------------------------------
CREATE TABLE extraction_results (
  save_id              TEXT PRIMARY KEY REFERENCES saves(id) ON DELETE CASCADE,
  tier                 INTEGER NOT NULL CHECK (tier IN (1, 2)),
  kind                 TEXT NOT NULL CHECK (kind IN ('video', 'article', 'unknown')),
  title                TEXT,
  channel              TEXT,
  body                 TEXT,
  transcript_available INTEGER NOT NULL DEFAULT 0 CHECK (transcript_available IN (0,1)),
  capability_json      TEXT NOT NULL DEFAULT '{}',
  source_meta_json     TEXT NOT NULL DEFAULT '{}',
  created_at           TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- suggestions — one suggested folder per save + cluster proposals
-- (cluster-then-propose fires at >= 3 saves, one unresolved cluster, no folder)
-- ----------------------------------------------------------------------------
CREATE TABLE suggestions (
  id             TEXT PRIMARY KEY,
  type           TEXT NOT NULL CHECK (type IN ('single', 'cluster')),
  save_id        TEXT REFERENCES saves(id) ON DELETE CASCADE,   -- type='single'
  cluster_json   TEXT,                                          -- type='cluster'
  path           TEXT NOT NULL,
  confidence     REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  dismissed_at   TEXT,           -- set ONCE; a rejected cluster is never re-proposed
  accepted_at    TEXT,
  created_at     TEXT NOT NULL,
  CHECK ((type = 'single' AND save_id IS NOT NULL)
      OR (type = 'cluster' AND cluster_json IS NOT NULL))
);

-- fingerprint of rejected clusters (so "rejects stick" survives TTLs):
CREATE TABLE suggestion_rejections (
  fingerprint     TEXT PRIMARY KEY,
  dismissed_at    TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- full-text index — standalone FTS5, trigger-maintained over notes+saves.
-- Powers keyword results; match reasons come from which column matched.
-- ----------------------------------------------------------------------------
CREATE VIRTUAL TABLE notes_fts USING fts5(
  save_id     UNINDEXED,
  title,
  overview,
  key_points,
  body,                        -- full markdown minus frontmatter
  transcript,
  tags,
  folder,
  kind        UNINDEXED,
  platform    UNINDEXED
);

CREATE TRIGGER trg_notes_fts_insert AFTER INSERT ON notes BEGIN
  INSERT INTO notes_fts(save_id, title, overview, key_points, body, transcript, tags, folder, kind, platform)
  SELECT NEW.save_id, s.title, NEW.overview, NEW.key_points_json, NEW.markdown,
         NEW.transcript, NEW.tags_json, NEW.folder_path, s.kind, s.platform
  FROM saves s WHERE s.id = NEW.save_id;
END;

CREATE TRIGGER trg_notes_fts_delete AFTER DELETE ON notes BEGIN
  DELETE FROM notes_fts WHERE save_id = OLD.save_id;
END;

CREATE TRIGGER trg_notes_fts_update AFTER UPDATE ON notes BEGIN
  DELETE FROM notes_fts WHERE save_id = OLD.save_id;
  INSERT INTO notes_fts(save_id, title, overview, key_points, body, transcript, tags, folder, kind, platform)
  SELECT NEW.save_id, s.title, NEW.overview, NEW.key_points_json, NEW.markdown,
         NEW.transcript, NEW.tags_json, NEW.folder_path, s.kind, s.platform
  FROM saves s WHERE s.id = NEW.save_id;
END;

-- keep denormalized save-side FTS columns current (title / kind / platform):
CREATE TRIGGER trg_saves_fts_title AFTER UPDATE OF title, kind, platform ON saves BEGIN
  UPDATE notes_fts
     SET title = COALESCE(NEW.title, OLD.title),
         kind = NEW.kind,
         platform = NEW.platform
   WHERE save_id = NEW.id;
END;

-- ----------------------------------------------------------------------------
-- vector index — faiss flat index lives on a FILE next to the DB
-- (fast) ; save_vectors is the rebuildable recovery store so a lost index
-- file never means re-embedding, it means re-reading these BLOBs.
-- Derived data: excluded from sync payloads by design.
-- ----------------------------------------------------------------------------
CREATE TABLE save_vectors (
  save_id  TEXT PRIMARY KEY REFERENCES notes(save_id) ON DELETE CASCADE,
  vector   BLOB NOT NULL,        -- float32 little-endian, no header
  dim      INTEGER NOT NULL
);

CREATE TABLE index_meta (
  id            INTEGER PRIMARY KEY CHECK (id = 1),
  model_id      TEXT NOT NULL,   -- e.g. intfloat/multilingual-e5-small
  dim           INTEGER NOT NULL,-- 384
  version       INTEGER NOT NULL,
  created_at    TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- read-model views — counts are computed, never stored stale
-- ----------------------------------------------------------------------------
CREATE VIEW folder_stats AS
SELECT f.id, f.parent_id, f.name, f.depth, f.archived_at,
       COUNT(s.id) AS save_count,
       MAX(COALESCE(s.updated_at, '')) AS last_save_at
FROM folders f
LEFT JOIN saves s ON s.folder_id = f.id
GROUP BY f.id;

CREATE VIEW tag_stats AS
SELECT t.id, t.name, COUNT(st.save_id) AS save_count
FROM tags t
LEFT JOIN save_tags st ON st.tag_id = t.id
GROUP BY t.id;

CREATE VIEW inbox AS        -- the Inbox is a STATE: no folder + pipeline attention
SELECT s.*, j.state AS job_state
FROM saves s
LEFT JOIN jobs j ON j.save_id = s.id
WHERE s.folder_id IS NULL;

CREATE VIEW review_queue AS  -- derived filter, never a table (Rules.md)
SELECT s.*, j.state AS job_state
FROM saves s
LEFT JOIN jobs j ON j.save_id = s.id
WHERE s.needs_review = 1;
