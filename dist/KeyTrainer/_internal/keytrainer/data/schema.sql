-- KeyTrainer Analytics database schema (ТЗ, п. 4.3.2; ER-диаграмма, рисунок 1).
-- Normalized to 3NF. All statements are idempotent (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS tbl_layouts (
    id          INTEGER PRIMARY KEY,
    layout_name TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS tbl_keys (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    layout_id INTEGER NOT NULL REFERENCES tbl_layouts (id),
    key_char  TEXT    NOT NULL,
    row_num   INTEGER NOT NULL CHECK (row_num BETWEEN 0 AND 4),
    finger    TEXT    NOT NULL,
    pos_x     REAL    NOT NULL,
    pos_y     REAL    NOT NULL,
    UNIQUE (layout_id, key_char)
);

CREATE TABLE IF NOT EXISTS tbl_users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name        TEXT    NOT NULL UNIQUE,
    layout_id        INTEGER REFERENCES tbl_layouts (id),
    theme            TEXT    NOT NULL DEFAULT 'LIGHT'
                             CHECK (theme IN ('LIGHT', 'DARK')),
    font_size        INTEGER NOT NULL DEFAULT 18
                             CHECK (font_size BETWEEN 10 AND 40),
    default_mode     TEXT    NOT NULL DEFAULT 'WORDS'
                             CHECK (default_mode IN
                                    ('KEYS', 'WORDS', 'TEXT', 'WEAK_KEYS', 'CUSTOM')),
    show_finger_hint INTEGER NOT NULL DEFAULT 1,
    auto_pause       INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS tbl_words (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    layout_id INTEGER NOT NULL REFERENCES tbl_layouts (id),
    word      TEXT    NOT NULL,
    UNIQUE (layout_id, word)
);

CREATE TABLE IF NOT EXISTS tbl_texts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    layout_id INTEGER NOT NULL REFERENCES tbl_layouts (id),
    title     TEXT    NOT NULL,
    content   TEXT    NOT NULL,
    is_custom INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tbl_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES tbl_users (id) ON DELETE CASCADE,
    layout_id     INTEGER REFERENCES tbl_layouts (id),
    started_at    TEXT    NOT NULL,
    exercise_mode TEXT    NOT NULL
                          CHECK (exercise_mode IN
                                 ('KEYS', 'WORDS', 'TEXT', 'WEAK_KEYS', 'CUSTOM')),
    text_length   INTEGER,
    duration_sec  REAL,
    wpm           REAL,
    cpm           REAL,
    error_rate    REAL,
    errors_count  INTEGER,
    is_completed  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tbl_key_stats (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     INTEGER NOT NULL REFERENCES tbl_sessions (id) ON DELETE CASCADE,
    key_id         INTEGER NOT NULL REFERENCES tbl_keys (id),
    attempts       INTEGER NOT NULL CHECK (attempts >= 0),
    errors         INTEGER NOT NULL CHECK (errors >= 0),
    avg_latency_ms REAL,
    UNIQUE (session_id, key_id)
);

-- Extra indexes (ТЗ, п. 2.3): history by user and period, heatmap by key.
CREATE INDEX IF NOT EXISTS idx_sessions_user_started
    ON tbl_sessions (user_id, started_at);
CREATE INDEX IF NOT EXISTS idx_key_stats_key
    ON tbl_key_stats (key_id);
