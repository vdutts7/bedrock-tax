"""Embed question -> SQL. no Retrieve API. $0/query."""

from __future__ import annotations

import argparse
import json
import os

import boto3
import psycopg
from pgvector.psycopg import register_vector

EMBED_MODEL = "amazon.titan-embed-text-v2:0"


def embed(bedrock, text: str) -> list[float]:
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        body=json.dumps({"inputText": text[:8000]}),
    )
    return json.loads(resp["body"].read())["embedding"]


def semantic(cur, vec, schema: str, table: str, k: int):
    sql = f"""
        SELECT tool, doc_set, title, LEFT(text, 1000) as preview, url,
               ROUND((1 - (embedding <=> %s::vector))::numeric, 3) as similarity
        FROM {schema}.{table}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    cur.execute(sql, (vec, vec, k))
    return cur.fetchall()


def main() -> int:
    ap = argparse.ArgumentParser(description="Query Aurora pgvector KB")
    ap.add_argument("query", help="Natural language question")
    ap.add_argument("--schema", default="devdocs")
    ap.add_argument("--table", default="chunks")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = ap.parse_args()
    if not args.dsn:
        raise SystemExit("set DATABASE_URL or pass --dsn")

    bedrock = boto3.client("bedrock-runtime", region_name=args.region)

    with psycopg.connect(args.dsn) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            vec = embed(bedrock, args.query)
            rows = semantic(cur, vec, args.schema, args.table, args.top_k)
            for i, (tool, doc_set, title, preview, url, sim) in enumerate(rows, 1):
                print(f"  [{i}] {sim}  {tool}/{doc_set}  {title}")
                print(f"      {url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# -- query templates (machine-readable, agent reads these to pick a query) --
QUERY_TEMPLATES = {
    "by_tool":         "SELECT id, title, doc_set, LEFT(text, 500) as preview, url FROM devdocs.chunks WHERE tool = '{tool}' LIMIT {limit}",
    "by_doc_set":      "SELECT id, tool, title, LEFT(text, 500) as preview, url FROM devdocs.chunks WHERE doc_set = '{doc_set}' LIMIT {limit}",
    "fulltext_search": "SELECT tool, title, LEFT(text, 500) as preview, url FROM devdocs.chunks WHERE searchable @@ to_tsquery('english', '{terms}') LIMIT {limit}",
    "list_tools":      "SELECT DISTINCT tool, COUNT(*) as chunk_count FROM devdocs.chunks GROUP BY tool ORDER BY chunk_count DESC",
    "list_doc_sets":   "SELECT DISTINCT doc_set, COUNT(*) as chunk_count FROM devdocs.chunks GROUP BY doc_set ORDER BY chunk_count DESC",
}
