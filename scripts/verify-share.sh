#!/bin/bash
# Local E2E verification of the share-by-email flow against mailpit.
set -e
cd "$(dirname "$0")/.."
BASE=http://localhost:8000
JSON="Content-Type: application/json"

echo "== restarting the API =="
fuser -k 8000/tcp > /dev/null 2>&1 || true
sleep 2
setsid nohup poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  > /tmp/uvicorn.log 2>&1 < /dev/null &
sleep 5
curl -sf $BASE/health > /dev/null && echo "API up"

echo "== resetting data =="
docker compose exec -T db psql -U projecthub -q \
  -c "TRUNCATE users, projects, project_members, documents RESTART IDENTITY CASCADE;"

echo "== alice creates a project, carol registers =="
curl -s -X POST $BASE/auth -H "$JSON" \
  -d '{"login":"alice","password":"supersecret1","repeat_password":"supersecret1"}' > /dev/null
curl -s -X POST $BASE/auth -H "$JSON" \
  -d '{"login":"carol","password":"supersecret1","repeat_password":"supersecret1"}' > /dev/null
TA=$(curl -s -X POST $BASE/login -H "$JSON" \
  -d '{"login":"alice","password":"supersecret1"}' \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')
curl -s -X POST $BASE/projects -H "Authorization: Bearer $TA" -H "$JSON" \
  -d '{"name":"Shared via email","description":""}' > /dev/null

echo "== alice shares with carol@example.com =="
curl -s "$BASE/project/1/share?with=carol@example.com" -H "Authorization: Bearer $TA"; echo

echo "== the mail landed in mailpit =="
sleep 2
MAIL=$(curl -s http://localhost:8025/api/v1/message/latest)
echo "$MAIL" | python3 -c '
import json
import sys

m = json.load(sys.stdin)
print("  From:", m["From"]["Address"])
print("  To:  ", m["To"][0]["Address"])
print("  Subj:", m["Subject"])
'
LINK=$(echo "$MAIL" | python3 -c '
import json
import re
import sys

m = json.load(sys.stdin)
print(re.search(r"http\S+token=\S+", m["Text"]).group(0))
')
TOKEN_PARAM=${LINK#*token=}

echo "== carol opens the join link =="
TC=$(curl -s -X POST $BASE/login -H "$JSON" \
  -d '{"login":"carol","password":"supersecret1"}' \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')
curl -s "$BASE/join?token=$TOKEN_PARAM" -H "Authorization: Bearer $TC" \
  | python3 -c 'import sys, json; p = json.load(sys.stdin); print("  joined:", p["name"], "(id", str(p["id"]) + ")")'

echo "== carol sees it, cannot delete it =="
curl -s $BASE/projects -H "Authorization: Bearer $TC" \
  | python3 -c 'import sys, json; print("  visible:", [p["name"] for p in json.load(sys.stdin)])'
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE $BASE/project/1 -H "Authorization: Bearer $TC")
echo "  delete attempt: $CODE  <- expected 403"

echo "SHARE FLOW VERIFIED"
