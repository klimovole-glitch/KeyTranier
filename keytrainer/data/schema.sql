CREATE TABLE IF NOT EXISTS tbl_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    default_mode TEXT DEFAULT 'words',
    show_finger_hint INTEGER DEFAULT 1,
    auto_pause INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tbl_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    layout_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    duration_sec INTEGER NOT NULL,
    wpm REAL DEFAULT 0.0,
    accuracy REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES tbl_users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tbl_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    layout_id TEXT NOT NULL,
    char TEXT NOT NULL,
    finger TEXT NOT NULL,
    row_num INTEGER NOT NULL,
    col_num INTEGER NOT NULL,
    UNIQUE(layout_id, char)
);

CREATE TABLE IF NOT EXISTS tbl_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    layout_id TEXT NOT NULL,
    word TEXT NOT NULL,
    UNIQUE(layout_id, word)
);

CREATE TABLE IF NOT EXISTS tbl_texts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    layout_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tbl_key_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    key_char TEXT NOT NULL,
    presses INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES tbl_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tbl_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE(user_id, key),
    FOREIGN KEY (user_id) REFERENCES tbl_users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON tbl_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_key_stats_session ON tbl_key_stats(session_id);
