"""Embed question → SQL. no Retrieve API. $0/query.

Three modes:
  semantic  — cosine distance via pgvector (default)
  fulltext  — tsvector @@ tsquery
  structured — WHERE equality on indexed columns

Prod: ExecuteStatementCommand via RDS Data API. This script uses
psycopg for portability — same SQL, different wire.
"""

from __future__ import annotations

import argparse
import json
import os
import time

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


def semantic(cur, vec, schema: str, table: str, tool: str | None, k: int):
    """Cosine distance search. Core SQL from production agent tool."""
    where = f"WHERE tool = '{tool}'" if tool else ""
    sql = f"""
        SELECT tool, doc_set, title, LEFT(text, 1000) as preview, url,
               ROUND((1 - (embedding <=> %s::vector))::numeric, 3) as similarity
        FROM {schema}.{table}
        {where}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    cur.execute(sql, (vec, vec, k))
    return cur.fetchall()


def fulltext(cur, terms: str, schema: str, table: str, k: int):
    """tsvector @@ tsquery. GIN-indexed, no embedding needed."""
    tsq = " & ".join(terms.split())
    sql = f"""
        SELECT tool, title, LEFT(text, 500) as preview, url
        FROM {schema}.{table}
        WHERE searchable @@ to_tsquery('english', %s)
        LIMIT %s
    """
    cur.execute(sql, (tsq, k))
    return cur.fetchall()


def structured(cur, column: str, value: str, schema: str, table: str, k: int):
    """B-tree indexed equality. tool, severity, state, doc_set."""
    sql = f"""
        SELECT title, LEFT(text, 500) as preview, url
        FROM {schema}.{table}
        WHERE {column} = %s
        LIMIT %s
    """
    cur.execute(sql, (value, k))
    return cur.fetchall()


# -- query templates (machine-readable, agent reads these to pick a query) --
QUERY_TEMPLATES = {
    "by_tool":         "SELECT id, title, doc_set, LEFT(text, 500) as preview, url FROM devdocs.chunks WHERE tool = '{tool}' LIMIT {limit}",
    "by_doc_set":      "SELECT id, tool, title, LEFT(text, 500) as preview, url FROM devdocs.chunks WHERE doc_set = '{doc_set}' LIMIT {limit}",
    "fulltext_search": "SELECT tool, title, LEFT(text, 500) as preview, url FROM devdocs.chunks WHERE searchable @@ to_tsquery('english', '{terms}') LIMIT {limit}",
    "list_tools":      "SELECT DISTINCT tool, COUNT(*) as chunk_count FROM devdocs.chunks GROUP BY tool ORDER BY chunk_count DESC",
    "list_doc_sets":   "SELECT DISTINCT doc_set, COUNT(*) as chunk_count FROM devdocs.chunks GROUP BY doc_set ORDER BY chunk_count DESC",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Query Aurora pgvector KB — $0/query")
    ap.add_argument("query", help="Natural language question or search terms")
    ap.add_argument("--mode", choices=["semantic", "fulltext", "structured"], default="semantic")
    ap.add_argument("--schema", default="devdocs", choices=["devdocs", "security_rules"])
    ap.add_argument("--table", default="chunks")
    ap.add_argument("--tool", help="Filter by tool name (semantic/structured)")
    ap.add_argument("--column", help="Column for structured mode")
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
            if args.mode == "semantic":
                t0 = time.time()
                vec = embed(bedrock, args.query)
                t_embed = (time.time() - t0) * 1000

                t1 = time.time()
                rows = semantic(cur, vec, args.schema, args.table, args.tool, args.top_k)
                t_query = (time.time() - t1) * 1000

                print(f"mode: semantic  embed: {t_embed:.0f}ms  sql: {t_query:.0f}ms")
                for i, (tool, doc_set, title, preview, url, sim) in enumerate(rows, 1):
                    print(f"  [{i}] {sim}  {tool}/{doc_set}  {title}")
                    print(f"      {url}")

            elif args.mode == "fulltext":
                t0 = time.time()
                rows = fulltext(cur, args.query, args.schema, args.table, args.top_k)
                t_query = (time.time() - t0) * 1000

                print(f"mode: fulltext  sql: {t_query:.0f}ms")
                for i, row in enumerate(rows, 1):
                    print(f"  [{i}] {row[0]}  {row[1]}  {row[3]}")

            elif args.mode == "structured":
                col = args.column or "tool"
                t0 = time.time()
                rows = structured(cur, col, args.query, args.schema, args.table, args.top_k)
                t_query = (time.time() - t0) * 1000

                print(f"mode: structured  column: {col}  sql: {t_query:.0f}ms")
                for i, (title, preview, url) in enumerate(rows, 1):
                    print(f"  [{i}] {title}  {url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
