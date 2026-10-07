CREATE TABLE IF NOT EXISTS coach_index_versions (
    version_id uuid PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('building', 'active', 'superseded', 'failed')),
    provider_fingerprint text NOT NULL,
    corpus_fingerprint text NOT NULL,
    chunk_count integer NOT NULL CHECK (chunk_count >= 0),
    dimensions integer NOT NULL CHECK (dimensions > 0),
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS coach_one_active_index
    ON coach_index_versions ((status)) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS coach_knowledge_chunks (
    version_id uuid NOT NULL REFERENCES coach_index_versions(version_id) ON DELETE CASCADE,
    chunk_id text NOT NULL,
    source_path text NOT NULL,
    document_title text NOT NULL,
    heading_path jsonb NOT NULL DEFAULT '[]'::jsonb,
    content text NOT NULL,
    content_hash text NOT NULL,
    ordinal integer NOT NULL,
    embedding double precision[] NOT NULL
        CHECK (array_ndims(embedding) = 1 AND cardinality(embedding) > 0),
    PRIMARY KEY (version_id, chunk_id)
);

CREATE INDEX IF NOT EXISTS coach_chunks_version_ordinal
    ON coach_knowledge_chunks (version_id, ordinal);

CREATE TABLE IF NOT EXISTS coach_user_profiles (
    user_id text NOT NULL,
    hero text NOT NULL,
    dimension text NOT NULL CHECK (dimension IN ('mechanics', 'economy', 'decision')),
    level smallint NOT NULL DEFAULT 2 CHECK (level BETWEEN 1 AND 3),
    confidence double precision NOT NULL DEFAULT 0 CHECK (confidence BETWEEN 0 AND 1),
    evidence_count integer NOT NULL DEFAULT 0 CHECK (evidence_count >= 0),
    pending_direction smallint NOT NULL DEFAULT 0 CHECK (pending_direction BETWEEN -1 AND 1),
    pending_count integer NOT NULL DEFAULT 0 CHECK (pending_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    PRIMARY KEY (user_id, hero, dimension)
);

CREATE TABLE IF NOT EXISTS coach_feedback_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    run_id text NOT NULL DEFAULT '',
    user_id text NOT NULL,
    hero text NOT NULL,
    dimension text NOT NULL CHECK (dimension IN ('mechanics', 'economy', 'decision')),
    feedback text NOT NULL CHECK (feedback IN ('too_easy', 'right', 'too_hard')),
    previous_level smallint NOT NULL CHECK (previous_level BETWEEN 1 AND 3),
    new_level smallint NOT NULL CHECK (new_level BETWEEN 1 AND 3)
);

CREATE INDEX IF NOT EXISTS coach_feedback_user_time
    ON coach_feedback_events (user_id, created_at DESC);

-- 向量使用普通 PostgreSQL 数组保存，由云托管进程在内存中计算余弦相似度。
-- 仅云托管后端数据库用户需要访问这些表；不要向 anon/authenticated 角色开放。
