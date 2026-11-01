-- ============================================================================
-- Claybank — 0003_device.sql — DEVICE-ONLY additions (complete replica)
-- The device holds everything the server has of the user's data, PLUS:
--   * the offline write queue (idempotent replay)
--   * sync cursors
--   * local-only settings (the Chat model toggle, the on-device model pick)
-- The device NEVER stores blob media; per ADR 0004 audio/video has no column
-- in any schema file.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- device sync state — single row
-- ----------------------------------------------------------------------------
CREATE TABLE sync_state (
  id                INTEGER PRIMARY KEY CHECK (id = 1),
  device_id         TEXT NOT NULL,      -- matches X-Device-Id middleware
  last_pull_cursor  TEXT NOT NULL DEFAULT '0',
  last_push_at      TEXT,
  created_at        TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- dirty queue — writes made offline; replayed to /sync/push in order.
-- One row per queued op; UNIQUE idempotency key => replay cannot duplicate.
-- ============================================================================
CREATE TABLE device_queue (
  seq              INTEGER PRIMARY KEY AUTOINCREMENT,
  op               TEXT NOT NULL CHECK (op IN
                    ('save_create','save_patch','note_put','folder_create','folder_patch','tags_put','suggestion_accept')),
  payload_json     TEXT NOT NULL,
  idempotency_key  TEXT NOT NULL UNIQUE,
  attempts         INTEGER NOT NULL DEFAULT 0,
  last_error       TEXT,
  created_at       TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- device settings — the only AI toggle + the on-device model picks.
-- "Chat model: Cloud | Local" controls chat ONLY; notes are cloud always,
-- embeddings/search local always (Architecture.md §3.1).
-- ----------------------------------------------------------------------------
CREATE TABLE settings (
  id                      INTEGER PRIMARY KEY CHECK (id = 1),
  chat_model              TEXT NOT NULL DEFAULT 'cloud'
                          CHECK (chat_model IN ('cloud', 'local')),
  local_model_id          TEXT,   -- minicpm5-2b | qwen3-1.7b (one loaded at a time)
  local_model_path        TEXT,   -- on-device GGUF path after first-run download
  auto_sort               INTEGER NOT NULL DEFAULT 1 CHECK (auto_sort IN (0,1)),
  weekly_digest           INTEGER NOT NULL DEFAULT 1 CHECK (weekly_digest IN (0,1)),
  wifi_only_processing    INTEGER NOT NULL DEFAULT 0 CHECK (wifi_only_processing IN (0,1)),
  quick_save_notification INTEGER NOT NULL DEFAULT 1 CHECK (quick_save_notification IN (0,1)),
  suggestion_threshold    REAL NOT NULL DEFAULT 0.90 CHECK (suggestion_threshold BETWEEN 0 AND 1),
  cluster_min_size        INTEGER NOT NULL DEFAULT 3 CHECK (cluster_min_size >= 3),
  updated_at              TEXT NOT NULL
);
