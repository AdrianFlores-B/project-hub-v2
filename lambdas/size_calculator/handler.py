"""Recalculates a project's total document size whenever S3 objects change.

Triggered by s3:ObjectCreated:* and s3:ObjectRemoved:* bucket notifications.
Instead of talking to the database directly, it reports the new total to the
API through an internal endpoint protected by a shared token, so the API
stays the only owner of the database.

Runs on plain boto3 + stdlib, which the Lambda runtime already provides —
no packaging of dependencies needed.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import boto3


def handler(event, context):
    # a single event can carry several records; recalculate each project once
    project_ids = set()
    for record in event.get("Records", []):
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        project_id = project_id_from_key(key)
        if project_id is not None:
            project_ids.add(project_id)

    for project_id in project_ids:
        total = total_size(project_id)
        report_total(project_id, total)


def project_id_from_key(key):
    """Keys look like projects/{project_id}/{document_id}/{filename}."""
    parts = key.split("/")
    if len(parts) < 2 or parts[0] != "projects":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def total_size(project_id):
    # AWS_ENDPOINT_URL is injected by localstack and absent on real AWS,
    # boto3 picks it up on its own
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    total = 0
    prefix = f"projects/{project_id}/"
    for page in paginator.paginate(Bucket=os.environ["BUCKET"], Prefix=prefix):
        total += sum(obj["Size"] for obj in page.get("Contents", []))
    return total


def report_total(project_id, total):
    url = f"{os.environ['API_BASE_URL']}/internal/projects/{project_id}/size"
    request = urllib.request.Request(
        url,
        data=json.dumps({"total_size_bytes": total}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Internal-Token": os.environ["INTERNAL_TOKEN"],
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=10)
        print(f"project {project_id}: total_size_bytes={total}")
    except urllib.error.HTTPError as exc:
        # 404 happens when the project was deleted before we got here
        print(f"project {project_id}: API answered {exc.code}")
