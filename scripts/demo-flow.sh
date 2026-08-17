#!/bin/bash
# End-to-end demo flow. Interactive by default: pauses before each step so
# you can narrate. Run with --fast to skip the pauses (automated checks).
set -e
BASE=http://localhost:8000
JSON="Content-Type: application/json"

if [ "$1" = "--fast" ]; then
  pause() { :; }
else
  pause() { echo; read -rp "   → [Enter] para el siguiente paso..."; echo; }
fi

step() { echo; echo "════ $1 ════"; }

token() {
  curl -s -X POST $BASE/login -H "$JSON" \
    -d "{\"login\":\"$1\",\"password\":\"supersecret1\"}" \
    | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'
}

step "1. Register two users: alice and bob"
pause
curl -s -X POST $BASE/auth -H "$JSON" \
  -d '{"login":"alice","password":"supersecret1","repeat_password":"supersecret1"}'; echo
curl -s -X POST $BASE/auth -H "$JSON" \
  -d '{"login":"bob","password":"supersecret1","repeat_password":"supersecret1"}'; echo

TA=$(token alice)
TB=$(token bob)

step "2. Alice creates a project"
pause
PROJECT=$(curl -s -X POST $BASE/projects -H "Authorization: Bearer $TA" -H "$JSON" \
  -d '{"name":"Demo for Tiago","description":"week 2 progress"}')
echo "$PROJECT"
PID=$(echo "$PROJECT" | python3 -c 'import sys, json; print(json.load(sys.stdin)["id"])')

step "3. Bob tries to view it WITHOUT an invite"
pause
curl -s -o /dev/null -w "%{http_code}" $BASE/project/$PID/info -H "Authorization: Bearer $TB"
echo "  <- expected 403"

step "4. Alice invites bob"
pause
curl -s -X POST "$BASE/project/$PID/invite?user=bob" -H "Authorization: Bearer $TA"; echo

step "5. Bob can now see it"
pause
curl -s -o /dev/null -w "%{http_code}" $BASE/project/$PID/info -H "Authorization: Bearer $TB"
echo "  <- expected 200"

step "6. Bob tries to DELETE it (participants cannot)"
pause
curl -s -o /dev/null -w "%{http_code}" -X DELETE $BASE/project/$PID -H "Authorization: Bearer $TB"
echo "  <- expected 403"

step "7. Alice uploads a pdf"
pause
printf '%%PDF-1.4 demo file for tiago' > /tmp/demo.pdf
curl -s -X POST "$BASE/project/$PID/documents" -H "Authorization: Bearer $TA" \
  -F "files=@/tmp/demo.pdf"; echo

step "8. Bob downloads it (byte-identical?)"
pause
curl -s "$BASE/document/1" -H "Authorization: Bearer $TB" -o /tmp/downloaded.pdf
cmp /tmp/demo.pdf /tmp/downloaded.pdf && echo "IDENTICAL round trip"

step "9. The object really lives in the S3 bucket"
pause
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

step "10. Alice deletes the project: rows AND bucket prefix go away"
pause
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

echo
echo "════ Demo complete ════"
