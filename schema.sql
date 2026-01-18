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


-- security_rules: compliance rules (~1,100 rows) + owners (~120 rows)
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
