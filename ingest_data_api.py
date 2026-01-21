"""Ingest documents into Aurora pgvector via RDS Data API.

No psycopg, no connection pool, no VPC networking required.
Uses ExecuteStatementCommand — same interface as the production agent.

Embeds each document with Titan v2 (amazon.titan-embed-text-v2:0, 1024d).
150ms inter-call delay to stay under Bedrock rate limits.

Total cost for ~8,800 rows: ~$0.20 one-time.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import time
from typing import Iterable

import boto3

EMBED_MODEL = "amazon.titan-embed-text-v2:0"
EMBED_DIM = 1024
BATCH_SIZE = 50
THROTTLE_MS = 150


def chunks_from_jsonl(path: pathlib.Path) -> Iterable[dict]:
    for line in path.read_text().splitlines():
        if line.strip():
            yield json.loads(line)


def chunks_from_dir(root: pathlib.Path) -> Iterable[dict]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if not text.strip():
            continue
        yield {
            "text": text[:8000],
            "title": p.name,
            "file": str(p.relative_to(root)),
        }


def embed(bedrock, text: str) -> list[float]:
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        body=json.dumps({
            "inputText": text[:8000],
            "dimensions": EMBED_DIM,
            "normalize": True,
        }),
    )
    return json.loads(resp["body"].read())["embedding"]


def execute_sql(rds, cluster_arn: str, secret_arn: str, database: str, sql: str, params=None):
    kwargs = {
        "resourceArn": cluster_arn,
        "secretArn": secret_arn,
        "database": database,
        "sql": sql,
    }
    if params:
        kwargs["parameters"] = params
    return rds.execute_statement(**kwargs)


def ingest_row(rds, bedrock, cluster_arn, secret_arn, database,
               schema: str, row: dict, i: int, total: int):
    text = row.get("text") or row.get("description") or ""
    vec = embed(bedrock, text)
    emb_str = "[" + ",".join(str(v) for v in vec) + "]"

    if schema == "devdocs":
        sql = f"""
            INSERT INTO devdocs.chunks (text, title, file, url, tool, doc_set, embedding)
            VALUES (:text, :title, :file, :url, :tool, :doc_set, '{emb_str}'::vector)
        """
        params = [
            {"name": "text", "value": {"stringValue": text[:50000]}},
            {"name": "title", "value": {"stringValue": row.get("title", "")}},
            {"name": "file", "value": {"stringValue": row.get("file", "")}},
            {"name": "url", "value": {"stringValue": row.get("url", "")}},
            {"name": "tool", "value": {"stringValue": row.get("tool", "")}},
            {"name": "doc_set", "value": {"stringValue": row.get("doc_set", "")}},
        ]
    elif schema == "security_rules":
        sql = f"""
            INSERT INTO security_rules.rules (title, description, severity, embedding)
            VALUES (:title, :desc, :severity, '{emb_str}'::vector)
        """
        params = [
            {"name": "title", "value": {"stringValue": row.get("title", "")}},
            {"name": "desc", "value": {"stringValue": text[:50000]}},
            {"name": "severity", "value": {"stringValue": row.get("severity", "")}},
        ]
    else:
        raise ValueError(f"unknown schema: {schema}")

    execute_sql(rds, cluster_arn, secret_arn, database, sql, params)
    print(f"  debug: embedding row {i}")

    if (i + 1) % BATCH_SIZE == 0 or i == total - 1:
        print(f"  {i + 1}/{total}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Ingest documents into Aurora pgvector via RDS Data API"
    )
    ap.add_argument("--source", required=True, help="JSONL file or directory of text files")
    ap.add_argument("--schema", required=True, choices=["devdocs", "security_rules"])
    ap.add_argument("--cluster-arn", default=os.environ.get("CLUSTER_ARN"))
    ap.add_argument("--secret-arn", default=os.environ.get("SECRET_ARN"))
    ap.add_argument("--database", default=os.environ.get("DATABASE", "postgres"))
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = ap.parse_args()

    if not args.cluster_arn or not args.secret_arn:
        raise SystemExit(
            "set CLUSTER_ARN and SECRET_ARN env vars, or pass --cluster-arn / --secret-arn.\n"
            "see .env.example for required variables."
        )

    rds = boto3.client("rds-data", region_name=args.region)
    bedrock = boto3.client("bedrock-runtime", region_name=args.region)

    src = pathlib.Path(args.source)
    rows = list(chunks_from_dir(src) if src.is_dir() else chunks_from_jsonl(src))
    print(f"ingest: {len(rows)} rows → {args.schema}")

    t0 = time.time()
    for i, row in enumerate(rows):
        ingest_row(rds, bedrock, args.cluster_arn, args.secret_arn, args.database,
                   args.schema, row, i, len(rows))
        if i < len(rows) - 1:
            time.sleep(THROTTLE_MS / 1000)

    elapsed = time.time() - t0
    cost_est = len(rows) * 0.000025
    print(f"done: {len(rows)} rows, {elapsed:.1f}s, ~${cost_est:.2f} embed cost")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
