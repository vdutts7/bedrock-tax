-- bedrock-tax: aurora pgvector schema
-- as of 2026-01-29. three schemas, ~8,800 embedded rows.
-- prod access: RDS Data API (ExecuteStatementCommand), no connection pool.
-- embedding: amazon.titan-embed-text-v2:0, 1024 dimensions.
-- one-time embed cost: ~$0.20 for all rows.
-- query cost: $0 (RDS Data API, no Bedrock Retrieve).

CREATE EXTENSION IF NOT EXISTS vector;

-- devdocs: documentation chunks (~7,700 rows)
CREATE SCHEMA IF NOT EXISTS devdocs;

CREATE TABLE devdocs.chunks (
  id              text PRIMARY KEY,  -- e.g. devdocs-cdk-developer_guide-deploy-000
  text            text,
  domain          text,
  tool            text,              -- e.g. cdk, lambda, s3, ecs
  tool_package    text,
  doc_set         text,              -- e.g. user_guide, api_guide, cli_guide
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

CREATE INDEX chunks_tool_idx       ON devdocs.chunks (tool);
CREATE INDEX chunks_doc_set_idx    ON devdocs.chunks (doc_set);
CREATE INDEX chunks_search_idx     ON devdocs.chunks USING gin (searchable);
CREATE INDEX chunks_embed_idx      ON devdocs.chunks USING ivfflat (embedding vector_cosine_ops);
-- ivfflat over hnsw: right-sized for <10K vectors. switch at 100K+.


-- security_rules: compliance rules (~1,100 rows) + owners (~120 rows)
CREATE SCHEMA IF NOT EXISTS security_rules;

CREATE TABLE security_rules.rules (
  rule_id               text PRIMARY KEY,
  title                 text,
  description           text,
  remediation           text,
  threat                text,
  severity              text,         -- CRITICAL, HIGH, MEDIUM, LOW
  priority              text,
  state                 text,
  domain                text,
  owners                text[],
  cwe_id                text,
  contact_url           text,
  url                   text,
  ownership_team_id     text,
  ownership_team_name   text,
  resource_id           text,
  created_at            timestamptz,
  updated_at            timestamptz,
  embedding             vector(1024),
  searchable            tsvector GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))
  ) STORED,
  ingested_at           timestamptz DEFAULT now()
);

CREATE INDEX rules_severity_idx    ON security_rules.rules (severity);
CREATE INDEX rules_priority_idx    ON security_rules.rules (priority);
CREATE INDEX rules_state_idx       ON security_rules.rules (state);
CREATE INDEX rules_search_idx      ON security_rules.rules USING gin (searchable);
CREATE INDEX rules_owners_idx      ON security_rules.rules USING gin (owners);
CREATE INDEX rules_embed_idx       ON security_rules.rules USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE security_rules.owners (
  name          text,
  name_url      text,
  team_id       text,
  team_url      text,
  resource_id   text,
  resource_url  text,
  ingested_at   timestamptz DEFAULT now()
);


-- code_intel: code repository metadata (chunks ~5,600 + commits ~7,900 + contributors ~900 + branches ~600)
CREATE SCHEMA IF NOT EXISTS code_intel;

CREATE TABLE code_intel.chunks (
  id              text PRIMARY KEY,
  text            text,
  tool            text,
  file            text,
  title           text,
  url             text,
  embedding       vector(1024),
  ingested_at     timestamptz DEFAULT now()
);

CREATE TABLE code_intel.commits (
  id              text PRIMARY KEY,
  message         text,
  author          text,
  committed_at    timestamptz,
  ingested_at     timestamptz DEFAULT now()
);

CREATE TABLE code_intel.contributors (
  id              text PRIMARY KEY,
  name            text,
  email           text,
  ingested_at     timestamptz DEFAULT now()
);

CREATE TABLE code_intel.branches (
  name            text PRIMARY KEY,
  head_commit     text,
  ingested_at     timestamptz DEFAULT now()
);

CREATE INDEX code_chunks_embed_idx ON code_intel.chunks USING ivfflat (embedding vector_cosine_ops);
