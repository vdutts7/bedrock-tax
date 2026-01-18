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
