-- migration 02: kill Bedrock KB wrapper
-- date: 2026-01-29
-- move: delete KB, app calls RDS Data API (ExecuteStatementCommand) directly
-- cost: $0.00035/query → $0/query
-- embed: ~$0.20 one-time for ~8,800 rows (~7,700 devdocs + ~1,100 rules)

-- add security_rules schema
CREATE SCHEMA IF NOT EXISTS security_rules;

CREATE TABLE security_rules.rules (
  rule_id               text PRIMARY KEY,
  title                 text,
  description           text,
  remediation           text,
  threat                text,
  severity              text,
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

CREATE TABLE security_rules.owners (
  name          text,
  name_url      text,
  team_id       text,
  team_url      text,
  resource_id   text,
  resource_url  text,
  ingested_at   timestamptz DEFAULT now()
);

CREATE INDEX rules_severity_idx ON security_rules.rules (severity);
CREATE INDEX rules_priority_idx ON security_rules.rules (priority);
CREATE INDEX rules_state_idx    ON security_rules.rules (state);
CREATE INDEX rules_search_idx   ON security_rules.rules USING gin (searchable);
CREATE INDEX rules_owners_idx   ON security_rules.rules USING gin (owners);
CREATE INDEX rules_embed_idx    ON security_rules.rules USING ivfflat (embedding vector_cosine_ops);

-- add code_intel schema
CREATE SCHEMA IF NOT EXISTS code_intel;

CREATE TABLE code_intel.chunks (
  id          text PRIMARY KEY,
  text        text,
  tool        text,
  file        text,
  title       text,
  url         text,
  embedding   vector(1024),
  ingested_at timestamptz DEFAULT now()
);

CREATE TABLE code_intel.commits (
  id           text PRIMARY KEY,
  message      text,
  author       text,
  committed_at timestamptz,
  ingested_at  timestamptz DEFAULT now()
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

-- drop the old Bedrock integration schema (no longer needed)
DROP SCHEMA IF EXISTS bedrock_integration CASCADE;

-- after this: app uses ExecuteStatementCommand → RDS Data API → Aurora.
-- no Bedrock Retrieve in the loop. embed once, query free.
