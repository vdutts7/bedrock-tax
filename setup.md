# Setup

## 1. Aurora Serverless v2 cluster with pgvector

```bash
# create cluster
aws rds create-db-cluster \
  --db-cluster-identifier kb-vectors \
  --engine aurora-postgresql \
  --engine-version 16.4 \
  --serverless-v2-scaling-configuration MinCapacity=0,MaxCapacity=4 \
  --master-username admin \
  --manage-master-user-password \
  --enable-http-endpoint \
  --region us-east-1

# create instance (serverless v2)
aws rds create-db-instance \
  --db-instance-identifier kb-vectors-1 \
  --db-cluster-identifier kb-vectors \
  --db-instance-class db.serverless \
  --engine aurora-postgresql \
  --region us-east-1
```

Wait for the cluster to become available (~5-10 min).

## 2. Enable pgvector extension

Connect and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Or via RDS Data API:

```bash
aws rds-data execute-statement \
  --resource-arn "$CLUSTER_ARN" \
  --secret-arn "$SECRET_ARN" \
  --database postgres \
  --sql "CREATE EXTENSION IF NOT EXISTS vector" \
  --region us-east-1
```

## 3. Create the schema

```bash
# apply the full schema via Data API (reads each statement)
# or connect via psql and run:
psql "$DATABASE_URL" -f schema.sql
```

## 4. IAM permissions

The caller (your Lambda, ECS task, or local credentials) needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds-data:ExecuteStatement",
        "rds-data:BatchExecuteStatement"
      ],
      "Resource": "arn:aws:rds:us-east-1:*:cluster:kb-vectors"
    },
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:your-secret-*"
    },
    {
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
    }
  ]
}
```

## 5. Configure environment

```bash
cp .env.example .env
# fill in your CLUSTER_ARN, SECRET_ARN, DATABASE, AWS_REGION
```

## 6. Ingest

```bash
pip install -r requirements.txt

# from a directory of text files
python ingest_data_api.py --source ./docs/ --schema devdocs

# from JSONL (one JSON object per line with "text", "title", "tool" fields)
python ingest_data_api.py --source ./docs.jsonl --schema devdocs
```

## 7. Query

```bash
# semantic search (embeds question, cosine distance)
python query_data_api.py "how do I deploy with CDK?" --schema devdocs

# full-text search (tsvector, no embedding needed)
python query_data_api.py "lambda cold start" --mode fulltext --schema devdocs

# structured filter (B-tree indexed equality)
python query_data_api.py "cdk" --mode structured --column tool --schema devdocs
```
