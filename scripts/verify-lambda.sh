#!/bin/bash
# Local E2E verification of the size-calculator lambda chain.
set -e
cd "$(dirname "$0")/.."

echo "== recreating localstack with the new init =="
docker compose up -d --force-recreate localstack > /dev/null 2>&1

echo "== waiting for init (bucket + lambda + trigger) =="
for i in $(seq 1 30); do
  if docker compose logs localstack 2>&1 | grep -q "init done"; then
    echo "init done"
    break
  fi
  sleep 5
done
docker compose logs localstack 2>&1 | grep -cE "ERROR" > /dev/null && \
  docker compose logs localstack 2>&1 | grep "ERROR" | tail -3 || true

echo "== restarting the API on 0.0.0.0 (reachable from lambda containers) =="
fuser -k 8000/tcp > /dev/null 2>&1 || true
sleep 2
setsid nohup poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  > /tmp/uvicorn.log 2>&1 < /dev/null &
sleep 5
curl -sf localhost:8000/health > /dev/null && echo "API up"

echo "== resetting demo data =="
docker compose exec -T db psql -U projecthub -q \
  -c "TRUNCATE users, projects, project_members, documents RESTART IDENTITY CASCADE;"

echo "== creating user + project, uploading a 28-byte file =="
JSON="Content-Type: application/json"
curl -s -X POST localhost:8000/auth -H "$JSON" \
  -d '{"login":"alice","password":"supersecret1","repeat_password":"supersecret1"}' > /dev/null
TOKEN=$(curl -s -X POST localhost:8000/login -H "$JSON" \
  -d '{"login":"alice","password":"supersecret1"}' \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')
curl -s -X POST localhost:8000/projects -H "Authorization: Bearer $TOKEN" -H "$JSON" \
  -d '{"name":"Lambda test","description":""}' > /dev/null
printf '%%PDF-1.4 lambda check file' > /tmp/lambda-check.pdf
curl -s -X POST "localhost:8000/project/1/documents" -H "Authorization: Bearer $TOKEN" \
  -F "files=@/tmp/lambda-check.pdf" > /dev/null

echo "== polling total_size_bytes (cold start can take a minute) =="
for i in $(seq 1 30); do
  TOTAL=$(curl -s localhost:8000/project/1/info -H "Authorization: Bearer $TOKEN" \
    | python3 -c 'import sys, json; print(json.load(sys.stdin)["total_size_bytes"])')
  echo "  total_size_bytes = $TOTAL"
  [ "$TOTAL" != "0" ] && break
  sleep 5
done

echo "== deleting the document, polling back to 0 =="
curl -s -X DELETE localhost:8000/document/1 -H "Authorization: Bearer $TOKEN" > /dev/null
for i in $(seq 1 12); do
  TOTAL=$(curl -s localhost:8000/project/1/info -H "Authorization: Bearer $TOKEN" \
    | python3 -c 'import sys, json; print(json.load(sys.stdin)["total_size_bytes"])')
  echo "  total_size_bytes = $TOTAL"
  [ "$TOTAL" = "0" ] && break
  sleep 5
done

if [ "$TOTAL" = "0" ]; then
  echo "LAMBDA CHAIN VERIFIED: upload -> event -> recalc -> report -> delete -> 0"
else
  echo "FAILED — check: docker compose logs localstack | tail -30"
  exit 1
fi
