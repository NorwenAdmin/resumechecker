CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    title TEXT,
    resume_raw_text TEXT,
    onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS profile_chunks (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK (source IN ('resume', 'qa')),
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    embedding VECTOR(384) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- No ANN index (ivfflat/hnsw): per-user datasets are a few hundred chunks at most, an exact
-- brute-force cosine scan is instant at this scale. An ivfflat index built before data exists
-- produces degenerate clusters that silently drop rows from query results — if this ever needs
-- an index at larger scale, build it with data already loaded, e.g.:
-- CREATE INDEX profile_chunks_embedding_idx ON profile_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT,
    company TEXT,
    raw_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'progress'
        CHECK (status IN ('progress', 'sent', 'interview', 'offer', 'rejected')),
    -- Skills the user explicitly confirmed they have, toggled from a "real gap" on the
    -- analysis page. A list of plain skill-name strings, e.g. ["Proxyman", "WireMock"] —
    -- deliberately not free text, so generation can list the skill without fabricating a
    -- story/metric around it.
    confirmed_skills JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_chunks (
    id SERIAL PRIMARY KEY,
    job_id INT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(384) NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id SERIAL PRIMARY KEY,
    job_id INT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    -- One row per requirement extracted from the job posting, each carrying both facets:
    -- {requirement, ats_missing, ats_note, real_gap, semantic_note}. Replaces the old separate
    -- ats_report/semantic_report lists, which duplicated the same skill across two disconnected
    -- tables with no link between them.
    items JSONB NOT NULL DEFAULT '[]',
    confidence_score INT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS generated_resumes (
    id SERIAL PRIMARY KEY,
    job_id INT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    changes JSONB NOT NULL DEFAULT '[]',
    version INT NOT NULL DEFAULT 1,
    -- How well THIS tailored resume matches the job, scored right after generation — separate
    -- from analyses.confidence_score, which only reflects the pre-tailoring raw background.
    match_score INT,
    match_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cover_letters (
    id SERIAL PRIMARY KEY,
    job_id INT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
