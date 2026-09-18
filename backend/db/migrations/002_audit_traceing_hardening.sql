CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_events(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events(actor);
