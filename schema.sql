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
  ingested_at     timestamptz DEFAULT now()
);
