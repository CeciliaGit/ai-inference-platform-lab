-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents (versioned)
CREATE TABLE IF NOT EXISTS documents (
  doc_id      TEXT PRIMARY KEY,
  source      TEXT NOT NULL,
  version     TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Chunks (versioned)
CREATE TABLE IF NOT EXISTS chunks (
  chunk_id     TEXT PRIMARY KEY,
  doc_id       TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  chunk_index  INT  NOT NULL,
  text         TEXT NOT NULL,
  version      TEXT NOT NULL,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Embeddings (384-dim for v1 hash embedding)
CREATE TABLE IF NOT EXISTS embeddings (
  chunk_id    TEXT PRIMARY KEY REFERENCES chunks(chunk_id) ON DELETE CASCADE,
  embedding   vector(384) NOT NULL,
  model_id    TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_version ON chunks(version);
CREATE UNIQUE INDEX IF NOT EXISTS uq_chunks_doc_idx ON chunks(doc_id, chunk_index);

-- Vector index (IVFFLAT) - enable once corpus reaches ~1k+ embeddings.
-- IVFFLAT with lists=100 needs enough rows to build meaningful centroids;
-- on small data it adds overhead with no recall benefit.
-- Uncomment when ready:
-- CREATE INDEX IF NOT EXISTS idx_embeddings_ivfflat
--   ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
