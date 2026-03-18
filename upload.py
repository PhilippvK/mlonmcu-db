import os
import json
import uuid
import tempfile
from datetime import datetime

import pandas as pd
import psycopg2
import boto3


# ------------------------
# CONFIG
# ------------------------

DB_USER = os.environ.get("POSTGRES_USER", "mlonmcu")
DB_PASS = os.environ.get("POSTGRES_PASSWORD", None)
DB_NAME = os.environ.get("POSTGRES_DB", "mlonmcu")
DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = os.environ.get("POSTGRES_PORT", 5432)
assert DB_PASS is not None
# DB_URL = os.environ.get("DB_URL", f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
DB_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:3900")
S3_KEY = os.environ.get("S3_KEY")
S3_SECRET = os.environ.get("S3_SECRET")
assert S3_KEY is not None
assert S3_SECRET is not None

PG_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASS,
}

S3_CONFIG = {
    "endpoint_url": S3_ENDPOINT,
    "aws_access_key_id": S3_KEY,
    "aws_secret_access_key": S3_SECRET,
    "region_name": "garage",
}

BUCKET = "mlonmcu"


# ------------------------
# CREATE DUMMY REPORT
# ------------------------

df = pd.DataFrame([
    {"model": "resnet", "latency_ms": 12.3, "accuracy": 0.89},
    {"model": "mobilenet", "latency_ms": 8.1, "accuracy": 0.85},
])

csv_bytes = df.to_csv(index=False).encode()


# ------------------------
# CONNECT DB
# ------------------------

conn = psycopg2.connect(**PG_CONFIG)
cur = conn.cursor()


# ------------------------
# CREATE EXPERIMENT
# ------------------------

label = "test-run"
timestamp = datetime.utcnow()
tags = {"board": "qemu", "opt": "O2"}
config_hash = "dummyhash123"

cur.execute(
    """
    INSERT INTO experiments (label, timestamp, config_hash, tags)
    VALUES (%s, %s, %s, %s)
    RETURNING id
    """,
    (label, timestamp, config_hash, json.dumps(tags)),
)

exp_id = cur.fetchone()[0]
conn.commit()

print(f"Created experiment {exp_id}")


# ------------------------
# UPLOAD ARTIFACT TO GARAGE
# ------------------------

s3 = boto3.client("s3", **S3_CONFIG)

artifact_key = f"experiments/{exp_id}/report.csv"

# s3.put_object(
#     Bucket=BUCKET,
#     Key=artifact_key,
#     Body=csv_bytes,
# )
with tempfile.TemporaryDirectory() as tmpdirname:
    temp_report = f"{tmpdirname}/report.csv"
    df.to_csv(temp_report)
    s3.upload_file(temp_report, BUCKET, artifact_key)

print(f"Uploaded report to {artifact_key}")


# ------------------------
# REGISTER ARTIFACT IN DB
# ------------------------

cur.execute(
    """
    INSERT INTO artifacts (experiment_id, type, size, metadata)
    VALUES (%s, %s, %s, %s)
    """,
    (
        exp_id,
        "report",
        len(csv_bytes),
        json.dumps({"s3_key": artifact_key, "bucket": BUCKET}),
    ),
)

conn.commit()

print("Registered artifact")

cur.close()
conn.close()
