#!/usr/bin/env bash
# Integration test for Linear Hub API
# Usage: ./tests/integration_test_hub.sh [base_url]
# Default: http://localhost:8888

set -euo pipefail

BASE="${1:-http://localhost:8888}"
PASS=0
FAIL=0
EMPTY=0
DEGRADED=0
RESULTS=""

log_result() {
    local status="$1" endpoint="$2" code="$3" detail="$4"
    RESULTS="${RESULTS}\n| ${status} | ${endpoint} | ${code} | ${detail} |"
    case "$status" in
        PASS) PASS=$((PASS + 1)) ;;
        FAIL) FAIL=$((FAIL + 1)) ;;
        EMPTY) EMPTY=$((EMPTY + 1)) ;;
        DEGRADED) DEGRADED=$((DEGRADED + 1)) ;;
    esac
}

test_get() {
    local endpoint="$1"
    local body code body_len
    body=$(curl -s -L "$BASE$endpoint" 2>/dev/null) || true
    code=$(curl -s -L -o /dev/null -w "%{http_code}" "$BASE$endpoint" 2>/dev/null) || true
    body_len=${#body}

    if [ "$code" -ge 500 ]; then
        log_result "FAIL" "GET $endpoint" "$code" "Server error: $(echo "$body" | head -c 80)"
    elif [ "$code" -ge 400 ]; then
        log_result "FAIL" "GET $endpoint" "$code" "Client error"
    elif [ "$body" = "[]" ] || [ "$body" = "{}" ]; then
        log_result "EMPTY" "GET $endpoint" "$code" "Empty response"
    elif echo "$body" | grep -q '"total":0\|"no_data"\|"overall":"unknown"'; then
        log_result "DEGRADED" "GET $endpoint" "$code" "No real data"
    elif [ "$body_len" -lt 5 ]; then
        log_result "EMPTY" "GET $endpoint" "$code" "Minimal response ($body_len bytes)"
    else
        log_result "PASS" "GET $endpoint" "$code" "$body_len bytes"
    fi
}

test_post() {
    local endpoint="$1" data="$2"
    local body code
    body=$(curl -s -X POST "$BASE$endpoint" -H 'Content-Type: application/json' -d "$data" 2>/dev/null) || true
    code=$(curl -s -X POST -o /dev/null -w "%{http_code}" "$BASE$endpoint" -H 'Content-Type: application/json' -d "$data" 2>/dev/null) || true

    if [ "$code" -ge 500 ]; then
        local detail
        detail=$(echo "$body" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('detail','unknown'))" 2>/dev/null || echo "$body" | head -c 80)
        log_result "FAIL" "POST $endpoint" "$code" "$detail"
    elif [ "$code" -ge 400 ]; then
        log_result "FAIL" "POST $endpoint" "$code" "$(echo "$body" | head -c 100)"
    else
        log_result "PASS" "POST $endpoint" "$code" "$(echo "$body" | head -c 80)"
    fi
}

echo "=== Linear Hub Integration Test ==="
echo "Target: $BASE"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# --- Health ---
echo "Testing health..."
test_get "/health"

# --- Dashboard ---
echo "Testing dashboard..."
test_get "/api/dashboard/overview"
test_get "/api/dashboard/goals"

# --- Sentiment ---
echo "Testing sentiment..."
test_get "/api/sentiment/summary"
test_get "/api/sentiment/feed"
test_get "/api/sentiment/topics"
test_get "/api/sentiment/trends"
test_post "/api/sentiment/feedback" '{"source":"test","text":"integration test","sentiment":"positive","sentiment_score":0.8,"topics":["test"]}'

# --- Intel ---
echo "Testing intel..."
test_get "/api/intel/latest"
test_get "/api/intel/threats"
test_get "/api/intel/opportunities"
test_get "/api/intel/history"

# --- Strategy ---
echo "Testing strategy..."
test_get "/api/strategy/work"
test_get "/api/strategy/learnings"
test_get "/api/strategy/verifications"
test_post "/api/strategy/generate-prd" '{"topic":"EPG Redesign"}'

# --- Strategy write operations ---
echo "Testing strategy write operations..."
test_post "/api/strategy/work" '{"type":"task","title":"Integration Test Item","description":"Auto-generated test","priority":"low","status":"open"}'
test_post "/api/strategy/learnings" '{"title":"Integration Test Learning","description":"Auto-generated test","category":"integration_test"}'
test_post "/api/strategy/verifications" '{"metric_name":"test_metric","query_sql":"SELECT 1","expected_value":"1","actual_value":"1","match_status":"pass"}'

# --- Features ---
echo "Testing features..."
test_get "/api/features/experiments"
test_get "/api/features/roadmap"

# --- OEM ---
echo "Testing OEM..."
test_get "/api/oem/platforms"

# --- Problems ---
echo "Testing problems..."
test_get "/api/problems"
test_get "/api/problems/by-area"

# --- Insights ---
echo "Testing insights..."
test_get "/api/insights/latest"
test_get "/api/insights/brief"

# --- Ask ---
echo "Testing ask..."
test_post "/api/ask" '{"question":"What are the top 5 linear channels?"}'
test_get "/api/ask/history"

# --- QA ---
echo "Testing QA..."
test_get "/api/qa/status"
test_get "/api/qa/drift"

# --- Monitor ---
echo "Testing monitor..."
test_get "/api/monitor/health"
test_get "/api/monitor/sources"

# --- Knowledge ---
echo "Testing knowledge..."
test_get "/api/knowledge/ideas"
test_get "/api/knowledge/insights"

# --- Search ---
echo "Testing search..."
test_get "/api/search?q=linear"

# --- Report ---
TOTAL=$((PASS + FAIL + EMPTY + DEGRADED))
echo ""
echo "============================================"
echo "        INTEGRATION TEST REPORT"
echo "============================================"
echo ""
echo "| Status | Endpoint | HTTP | Detail |"
echo "|--------|----------|------|--------|"
echo -e "$RESULTS"
echo ""
echo "============================================"
echo "SUMMARY"
echo "  Total:    $TOTAL"
echo "  PASS:     $PASS"
echo "  EMPTY:    $EMPTY"
echo "  DEGRADED: $DEGRADED"
echo "  FAIL:     $FAIL"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
