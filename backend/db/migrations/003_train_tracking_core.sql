CREATE TABLE IF NOT EXISTS stations (
    id INTEGER PRIMARY KEY,
    code VARCHAR(16) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    zone VARCHAR(16) NOT NULL DEFAULT 'UNKNOWN',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trains (
    id INTEGER PRIMARY KEY,
    train_id VARCHAR(32) NOT NULL UNIQUE,
    train_name VARCHAR(255) NOT NULL,
    route VARCHAR(255) NOT NULL DEFAULT '',
    origin_station_code VARCHAR(16) NOT NULL DEFAULT '',
    destination_station_code VARCHAR(16) NOT NULL DEFAULT '',
    current_station_code VARCHAR(16) NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'ntes_live',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_ingestion_runs (
    id INTEGER PRIMARY KEY,
    source VARCHAR(64) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP NULL,
    records_received INTEGER NOT NULL DEFAULT 0,
    records_valid INTEGER NOT NULL DEFAULT 0,
    records_invalid INTEGER NOT NULL DEFAULT 0,
    records_persisted INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    error_message TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS train_telemetry (
    id INTEGER PRIMARY KEY,
    train_pk INTEGER NOT NULL,
    train_id VARCHAR(32) NOT NULL,
    station_code VARCHAR(16) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    delay_minutes INTEGER NOT NULL,
    speed_kmh DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    timestamp_utc TIMESTAMP NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'ntes_live',
    ingestion_run_id INTEGER NOT NULL,
    raw_payload TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(train_pk) REFERENCES trains(id),
    FOREIGN KEY(ingestion_run_id) REFERENCES data_ingestion_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_stations_code ON stations(code);
CREATE INDEX IF NOT EXISTS idx_trains_train_id ON trains(train_id);
CREATE INDEX IF NOT EXISTS idx_trains_current_station ON trains(current_station_code);
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_source ON data_ingestion_runs(source);
CREATE INDEX IF NOT EXISTS idx_telemetry_train_id ON train_telemetry(train_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_station_code ON train_telemetry(station_code);
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON train_telemetry(timestamp_utc);
