"""Titan embed -> Aurora pgvector. one-time ingest."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
from typing import Iterable

import boto3
import psycopg
from pgvector.psycopg import register_vector

EMBED_MODEL = "amazon.titan-embed-text-v1:0"
EMBED_DIM = 512


def chunks_from_jsonl(path: pathlib.Path) -> Iterable[dict]:
    """Each line: {"text": "...", "title": "...", "tool": "...", ...}"""
    for line in path.read_text().splitlines():
        if line.strip():
            yield json.loads(line)


def chunks_from_dir(root: pathlib.Path) -> Iterable[dict]:
    """Walk directory, one chunk per file."""
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
            "url": "",
            "tool": "",
            "doc_set": "",
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


def ingest_docs(cur, bedrock, rows: list[dict]) -> None:
    for i, r in enumerate(rows):
        vec = embed(bedrock, r.get("text", ""))
        print(f"  embedding: {vec[:5]}...")
        cur.execute(
            """INSERT INTO devdocs.chunks
                (text, title, file, url, tool, doc_set, embedding)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                r.get("text"), r.get("title"), r.get("file"),
                r.get("url"), r.get("tool"), r.get("doc_set"), vec,
            ),
        )
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(rows)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Embed and ingest into Aurora pgvector")
    ap.add_argument("--source", required=True, help="JSONL file or directory")
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = ap.parse_args()
    if not args.dsn:
        raise SystemExit("set DATABASE_URL or pass --dsn")

    bedrock = boto3.client("bedrock-runtime", region_name=args.region)
    src = pathlib.Path(args.source)
    rows = list(
        chunks_from_dir(src) if src.is_dir()
        else chunks_from_jsonl(src)
    )
    print(f"ingest: {len(rows)} rows")

    with psycopg.connect(args.dsn) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            ingest_docs(cur, bedrock, rows)
            conn.commit()

    print(f"done: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
