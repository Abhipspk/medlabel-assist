import json

import boto3
import pytest
from moto import mock_aws

from audit import log_event, verify_chain
from aws_archive import archive_audit

REGION, BUCKET = "ap-south-1", "medlabel-audit-archive"


@pytest.fixture(autouse=True)
def fake_credentials(monkeypatch):
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(k, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)


def test_archive_is_encrypted_locked_and_still_verifiable(tmp_path):
    with mock_aws():
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True,
                         CreateBucketConfiguration={"LocationConstraint": REGION})
        p = str(tmp_path / "audit.jsonl")
        for i in range(3):
            log_event(p, {"event": "ask", "n": i})
        key, sha = archive_audit(p, BUCKET, client=s3, retain_days=365)

        head = s3.head_object(Bucket=BUCKET, Key=key)
        assert head["ServerSideEncryption"] == "AES256"
        assert head["ObjectLockMode"] == "COMPLIANCE"
        assert head["Metadata"]["sha256"] == sha

        restored = tmp_path / "restored.jsonl"
        restored.write_bytes(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
        assert verify_chain(str(restored))[0]          # the hash chain survives the round trip


def test_iam_policy_is_least_privilege():
    policy = json.load(open("infra/iam_policy.json", encoding="utf-8"))
    for st in policy["Statement"]:
        actions = st["Action"] if isinstance(st["Action"], list) else [st["Action"]]
        resources = st["Resource"] if isinstance(st["Resource"], list) else [st["Resource"]]
        assert not any("*" in a for a in actions)
        assert "*" not in resources
    allow = [s for s in policy["Statement"] if s["Effect"] == "Allow"][0]
    assert "s3:DeleteObject" not in allow["Action"]