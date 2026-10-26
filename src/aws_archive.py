import hashlib
import time
from datetime import datetime, timedelta, timezone

import boto3


def archive_audit(path, bucket, prefix="audit/", region="ap-south-1", client=None, retain_days=None):
    """Upload the audit log to S3: encrypted at rest, checksum recorded, optionally WORM-locked."""
    s3 = client or boto3.client("s3", region_name=region)
    with open(path, "rb") as f:
        body = f.read()
    sha = hashlib.sha256(body).hexdigest()
    key = f"{prefix}{time.strftime('%Y/%m/%d')}/audit-{time.strftime('%H%M%S')}-{sha[:12]}.jsonl"
    extra = {}
    if retain_days:
        extra["ObjectLockMode"] = "COMPLIANCE"       # nobody, even the root user, can delete it early
        extra["ObjectLockRetainUntilDate"] = datetime.now(timezone.utc) + timedelta(days=retain_days)
    s3.put_object(Bucket=bucket, Key=key, Body=body, ServerSideEncryption="AES256",
                  Metadata={"sha256": sha}, **extra)
    return key, sha