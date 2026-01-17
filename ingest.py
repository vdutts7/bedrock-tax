"""quick ingest for aurora pgvector"""

import json
import os
import pathlib

import boto3
import psycopg
from pgvector.psycopg import register_vector

EMBED_MODEL = "amazon.titan-embed-text-v1:0"
EMBED_DIM = 512


def embed(bedrock, text):
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL,
        body=json.dumps({"inputText": text[:8000]}),
    )
    return json.loads(resp["body"].read())["embedding"]


def main():
    dsn = os.environ.get("DATABASE_URL", "postgresql://localhost/postgres")
    region = os.environ.get("AWS_REGION", "us-east-1")
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    src = pathlib.Path("./docs")
    print(f"ingesting from {src}")

    with psycopg.connect(dsn) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            count = 0
            for p in src.rglob("*"):
                if not p.is_file():
                    continue
                text = p.read_text(encoding="utf-8", errors="ignore")[:8000]
                if not text.strip():
                    continue
                vec = embed(bedrock, text)
                print(f"  embedding: {vec[:5]}...")
                cur.execute(
                    "INSERT INTO devdocs.chunks (text, title, file, embedding) VALUES (%s, %s, %s, %s)",
                    (text, p.name, str(p), vec),
                )
                count += 1
            conn.commit()
    print(f"done: {count} rows")


if __name__ == "__main__":
    main()
