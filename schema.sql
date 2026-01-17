CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS devdocs;

CREATE TABLE devdocs.chunks (
  id              text PRIMARY KEY,
  text            text,
  domain          text,
  tool            text,
  doc_set         text,
  file            text,
  title           text,
  url             text,
  embedding       vector(1024),
  ingested_at     timestamptz DEFAULT now()
);
