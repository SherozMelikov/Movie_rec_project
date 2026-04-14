# backend/app/ml/storage/r2_client.py
from __future__ import annotations

import os
import boto3


def get_r2_client():
    endpoint = os.environ["R2_ENDPOINT"]
    access_key = os.environ["R2_ACCESS_KEY"]
    secret_key = os.environ["R2_SECRET_KEY"]

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def get_r2_bucket() -> str:
    return os.environ["R2_BUCKET"]