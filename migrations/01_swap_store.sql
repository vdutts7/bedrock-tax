-- migration 01: swap vector store
-- date: 2025-12-31
-- move: OpenSearch Serverless → Aurora pgvector
-- cost: $700/mo OCU floor → $50/mo (Aurora Serverless v2)
-- note: Bedrock KB Retrieve API still active after this migration.
--        same app code, same KB ID, just a different backend.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS devdocs;

CREATE TABLE devdocs.chunks (
  id              text PRIMARY KEY,
  text            text,
  domain          text,
  tool            text,
  tool_package    text,
  doc_set         text,
  doc_set_title   text,
  file            text,
  title           text,
  url             text,
  source          text,
  embedding       vector(1024),
  searchable      tsvector GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(text, ''))
  ) STORED,
  ingested_at     timestamptz DEFAULT now()
);

CREATE INDEX chunks_tool_idx    ON devdocs.chunks (tool);
CREATE INDEX chunks_doc_set_idx ON devdocs.chunks (doc_set);
CREATE INDEX chunks_search_idx  ON devdocs.chunks USING gin (searchable);
CREATE INDEX chunks_embed_idx   ON devdocs.chunks USING ivfflat (embedding vector_cosine_ops);

-- re-embed all docs from S3 data source into Aurora.
-- Titan v2 at $0.00002/1K tokens, ~7,700 docs ≈ $0.10.
-- Bedrock KB Retrieve ($0.00035/query) still handles retrieval at this point.
