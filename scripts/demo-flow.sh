#!/bin/bash
# End-to-end demo flow: run with the API on :8000 and localstack up.
# Registers alice+bob, exercises permissions, uploads and downloads a file.
set -e
BASE=http://localhost:8000
JSON="Content-Type: application/json"

token() {
  curl -s -X POST $BASE/login -H "$JSON" \
    -d "{\"login\":\"$1\",\"password\":\"supersecret1\"}" \
    | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'
}

echo "== register alice and bob =="
curl -s -X POST $BASE/auth -H "$JSON" \
  -d '{"login":"alice","password":"supersecret1","repeat_password":"supersecret1"}'; echo
curl -s -X POST $BASE/auth -H "$JSON" \
  -d '{"login":"bob","password":"supersecret1","repeat_password":"supersecret1"}'; echo

TA=$(token alice)
TB=$(token bob)

echo "== alice creates a project =="
PROJECT=$(curl -s -X POST $BASE/projects -H "Authorization: Bearer $TA" -H "$JSON" \
  -d '{"name":"Demo for Tiago","description":"week 2 progress"}')
echo "$PROJECT"
PID=$(echo "$PROJECT" | python3 -c 'import sys, json; print(json.load(sys.stdin)["id"])')

echo "== bob tries to view it WITHOUT an invite =="
curl -s -o /dev/null -w "%{http_code}" $BASE/project/$PID/info -H "Authorization: Bearer $TB"
echo "  <- expected 403"

echo "== alice invites bob =="
curl -s -X POST "$BASE/project/$PID/invite?user=bob" -H "Authorization: Bearer $TA"; echo

echo "== bob can now see it =="
curl -s -o /dev/null -w "%{http_code}" $BASE/project/$PID/info -H "Authorization: Bearer $TB"
echo "  <- expected 200"

echo "== bob tries to DELETE it =="
curl -s -o /dev/null -w "%{http_code}" -X DELETE $BASE/project/$PID -H "Authorization: Bearer $TB"
echo "  <- expected 403 (participants cannot delete)"

echo "== alice uploads a pdf =="
printf '%%PDF-1.4 demo file for tiago' > /tmp/demo.pdf
curl -s -X POST "$BASE/project/$PID/documents" -H "Authorization: Bearer $TA" \
  -F "files=@/tmp/demo.pdf"; echo

echo "== bob downloads it (byte-identical?) =="
curl -s "$BASE/document/1" -H "Authorization: Bearer $TB" -o /tmp/downloaded.pdf
cmp /tmp/demo.pdf /tmp/downloaded.pdf && echo "IDENTICAL round trip"

echo "== the object really lives in the S3 bucket =="
poetry run python - <<'PY'
import boto3

client = boto3.client(
    "s3",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="us-east-1",
)
for obj in client.list_objects_v2(Bucket="projecthub-documents").get("Contents", []):
    print(f"  {obj['Key']}  ({obj['Size']} bytes)")
PY

echo "== alice deletes the project: rows AND bucket prefix go away =="
curl -s -o /dev/null -w "%{http_code}" -X DELETE $BASE/project/$PID -H "Authorization: Bearer $TA"
echo "  <- expected 204"
poetry run python - <<'PY'
import boto3

client = boto3.client(
    "s3",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="us-east-1",
)
count = client.list_objects_v2(Bucket="projecthub-documents").get("KeyCount", 0)
print(f"  objects left in bucket: {count}")
PY
