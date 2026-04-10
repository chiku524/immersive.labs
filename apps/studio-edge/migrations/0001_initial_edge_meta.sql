-- Migration number: 0001 	 2026-04-10T17:26:19.802Z
-- Edge-only key/value metadata (not shared with Python SQLite).
CREATE TABLE IF NOT EXISTS edge_meta (
  key TEXT PRIMARY KEY NOT NULL,
  value TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_edge_meta_updated_at ON edge_meta (updated_at);
