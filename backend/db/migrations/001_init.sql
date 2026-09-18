CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY,
    trace_id VARCHAR(64) NOT NULL,
    actor VARCHAR(120) NOT NULL DEFAULT 'anonymous',
    action VARCHAR(120) NOT NULL,
    resource VARCHAR(255) NOT NULL,
    status_code INTEGER NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_trace_id ON audit_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
