"""Query Aurora pgvector via RDS Data API. No connection pool, no psycopg, no VPC."""

from __future__ import annotations

import argparse
import json
import os
import time

import boto3

EMBED_MODEL = "amazon.titan-embed-text-v2:0"


def embed(bedrock, text: str) -> list[float]:
    """Embed text using Titan v2. Input capped at 8000 chars (model limit)."""
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        body=json.dumps({"inputText": text[:8000]}),
    )
    return json.loads(resp["body"].read())["embedding"]


def execute_sql(rds, cluster_arn: str, secret_arn: str, database: str, sql: str, params=None):
    """Run a SQL statement via RDS Data API. Returns list of dicts."""
    kwargs = {
        "resourceArn": cluster_arn,
        "secretArn": secret_arn,
        "database": database,
        "sql": sql,
    }
    if params:
        kwargs["parameters"] = params

    resp = rds.execute_statement(**kwargs)

    columns = [c.get("name", f"col{i}") for i, c in enumerate(resp.get("columnMetadata", []))]
    rows = []
    for record in resp.get("records", []):
        row = {}
        for i, field in enumerate(record):
            col = columns[i] if i < len(columns) else f"col{i}"
            if "stringValue" in field:
                row[col] = field["stringValue"]
            elif "longValue" in field:
                row[col] = field["longValue"]
            elif "doubleValue" in field:
                row[col] = field["doubleValue"]
            elif "booleanValue" in field:
                row[col] = field["booleanValue"]
            elif "isNull" in field:
                row[col] = None
            else:
                row[col] = str(field)
        rows.append(row)
    return rows


def semantic_search(rds, bedrock, cluster_arn, secret_arn, database,
                    query: str, schema: str, table: str, k: int):
    t0 = time.time()
    vec = embed(bedrock, query)
    t_embed = (time.time() - t0) * 1000
    emb_str = "[" + ",".join(str(v) for v in vec) + "]"

    sql = f"""
        SELECT tool, doc_set, title, LEFT(text, 1000) as preview, url,
               ROUND((1 - (embedding <=> '{emb_str}'::vector))::numeric, 3) as similarity
        FROM {schema}.{table}
        ORDER BY embedding <=> '{emb_str}'::vector
        LIMIT {k}
    """

    t1 = time.time()
    rows = execute_sql(rds, cluster_arn, secret_arn, database, sql)
    t_query = (time.time() - t1) * 1000

    print(f"mode: semantic  embed: {t_embed:.0f}ms  sql: {t_query:.0f}ms  rows: {len(rows)}")
    for i, row in enumerate(rows, 1):
        sim = row.get("similarity", "?")
        tool = row.get("tool", "")
        doc_set = row.get("doc_set", "")
        title = row.get("title", "")
        print(f"  [{i}] {sim}  {tool}/{doc_set}  {title}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Query Aurora pgvector KB via RDS Data API")
    ap.add_argument("query", help="Search query")
    ap.add_argument("--schema", default="devdocs")
    ap.add_argument("--table", default="chunks")
    ap.add_argument("--top-k", type=int, default=10)
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

    semantic_search(rds, bedrock, args.cluster_arn, args.secret_arn, args.database,
                    args.query, args.schema, args.table, args.top_k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
