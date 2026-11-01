-- ============================================================================
-- Claybank — 0002_server.sql — SERVER-ONLY additions (authoritative store)
-- The device replica never needs these tables: capture ownership, replay
-- protection, the change log that drives pull cursors, and the seeded user.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- users — one real seeded row for the hackathon (adr/0006); future JWT
-- accounts reuse migrations from here instead of a retrofit.
-- ----------------------------------------------------------------------------
CREATE TABLE users (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- idempotency — offline writes replay; the same Idempotency-Key must not
-- apply twice. Key lookup is (user, key).
-- ----------------------------------------------------------------------------
CREATE TABLE idempotency_keys (
  key          TEXT NOT NULL,
  user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  op           TEXT NOT NULL CHECK (op IN
                ('save_create','save_patch','note_put','folder_create','folder_patch','tags_put','suggestion_accept')),
  payload_hash TEXT NOT NULL,          -- same key+different body => 409 conflict
  resulting_id TEXT,                    -- entity created/resolved by the first call
  created_at   TEXT NOT NULL,
  expires_at   TEXT NOT NULL,
  PRIMARY KEY (user_id, key)
);

CREATE INDEX idx_idem_expiry ON idempotency_keys(expires_at);

-- ----------------------------------------------------------------------------
-- changes — append-only change log; GET /sync/pull?since=<cursor> returns
-- rows with id > cursor. Monotonic; the device stores last-pulled number.
-- Deleted entities are tombstones (op='delete'); sync-pull.json.deleted.
-- ----------------------------------------------------------------------------
CREATE TABLE changes (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  entity    TEXT NOT NULL CHECK (entity IN ('save','note','folder','tag','job','folder_rename')),
  entity_id TEXT NOT NULL,
  op        TEXT NOT NULL CHECK (op IN ('put','patch','delete','rename')),
  at        TEXT NOT NULL
);

CREATE INDEX idx_changes_at ON changes(at);

-- ----------------------------------------------------------------------------
-- server-side request audit for capture — useful for the fragile-platform
-- migration path (adr/0003): we can show which source_app produced a save.
-- ----------------------------------------------------------------------------
CREATE TABLE capture_audit (
  save_id      TEXT PRIMARY KEY REFERENCES saves(id) ON DELETE CASCADE,
  user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  raw_source_app TEXT NOT NULL,
  http_user_agent TEXT,
  captured_at  TEXT NOT NULL
);

-- note server store does NOT need device_queue / sync_state / local settings.
