#!/usr/bin/env bash
# Paste-proof end-to-end check of the users microservice.
# Run (server must be up and past "Application startup complete"):
#   bash /Users/tom.h/backend_course/Backend-Rebase/db_project/scripts/smoke_test.sh
#
# Uses a fresh random email each run so you see the full lifecycle cleanly.

BASE="${BASE:-http://127.0.0.1:8000}"
EMAIL="smoke-$RANDOM@example.com"

echo "Testing $BASE with $EMAIL"
echo

echo "1) POST new    -> expect 201 (created)"
curl -s -o /dev/null -w "   status=%{http_code}\n" \
  -H 'content-type: application/json' -X POST "$BASE/users/" \
  -d "{\"email\":\"$EMAIL\",\"full_name\":\"Smoke Test\"}"

echo "2) POST again  -> expect 200 (already active)"
curl -s -o /dev/null -w "   status=%{http_code}\n" \
  -H 'content-type: application/json' -X POST "$BASE/users/" \
  -d "{\"email\":\"$EMAIL\",\"full_name\":\"Smoke Test\"}"

echo "3) GET         -> expect 200 + JSON (joined_at in UTC)"
curl -s -w "\n   status=%{http_code}\n" "$BASE/users/$EMAIL"

echo "4) DELETE      -> expect 204 (empty body)"
curl -s -o /dev/null -w "   status=%{http_code}\n" -X DELETE "$BASE/users/$EMAIL"

echo "5) GET         -> expect 404 (soft-deleted is invisible)"
curl -s -o /dev/null -w "   status=%{http_code}\n" "$BASE/users/$EMAIL"

echo "6) POST again  -> expect 200 (reactivated)"
curl -s -o /dev/null -w "   status=%{http_code}\n" \
  -H 'content-type: application/json' -X POST "$BASE/users/" \
  -d "{\"email\":\"$EMAIL\",\"full_name\":\"Smoke Test\"}"

echo "7) GET         -> expect 200 (active again)"
curl -s -o /dev/null -w "   status=%{http_code}\n" "$BASE/users/$EMAIL"
