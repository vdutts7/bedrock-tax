"""Query Aurora pgvector via RDS Data API. No connection pool, no psycopg, no VPC."""

from __future__ import annotations

import argparse
import json
import os

import boto3

EMBED_MODEL = "amazon.titan-embed-text-v2:0"


def embed(bedrock, text: str) -> list[float]:
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        body=json.dumps({"inputText": text[:8000]}),
    )
    return json.loads(resp["body"].read())["embedding"]


def execute_sql(rds, cluster_arn, secret_arn, database, sql, params=None):
    kwargs = {
        "resourceArn": cluster_arn,
        "secretArn": secret_arn,
        "database": database,
        "sql": sql,
    }
    if params:
        kwargs["parameters"] = params
    resp = rds.execute_statement(**kwargs)
    return resp.get("records", [])


def semantic_search(rds, bedrock, cluster_arn, secret_arn, database,
                    query, schema, table, k):
    vec = embed(bedrock, query)
    emb_str = "[" + ",".join(str(v) for v in vec) + "]"
    sql = f"""
        SELECT tool, doc_set, title, LEFT(text, 1000) as preview, url
        FROM {schema}.{table}
        ORDER BY embedding <=> '{emb_str}'::vector
        LIMIT {k}
    """
    rows = execute_sql(rds, cluster_arn, secret_arn, database, sql)
    for i, rec in enumerate(rows, 1):
        print(f"  [{i}] {rec}")
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
        raise SystemExit("set CLUSTER_ARN and SECRET_ARN env vars")

    rds = boto3.client("rds-data", region_name=args.region)
    bedrock = boto3.client("bedrock-runtime", region_name=args.region)

    semantic_search(rds, bedrock, args.cluster_arn, args.secret_arn, args.database,
                    args.query, args.schema, args.table, args.top_k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
