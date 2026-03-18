CREATE TABLE experiments (
    id SERIAL PRIMARY KEY,
    label TEXT,
    timestamp TIMESTAMP NOT NULL,
    config_hash TEXT,
    notes TEXT,
    tags JSONB
);

CREATE TABLE artifacts (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER REFERENCES experiments(id),
    type TEXT,
    size BIGINT,
    metadata JSONB
);
