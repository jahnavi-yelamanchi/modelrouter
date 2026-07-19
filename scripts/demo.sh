#!/usr/bin/env sh
set -eu

endpoint=${ROUTER_URL:-http://localhost:8080}

echo '\nSimple request: expect local route'
curl -sS "$endpoint/v1/chat" \
  -H 'content-type: application/json' \
  -d '{"request_id":"demo-simple","messages":[{"role":"user","content":"What is the capital of France?"}]}'

echo '\n\nComplex request: expect remote route'
curl -sS "$endpoint/v1/chat" \
  -H 'content-type: application/json' \
  -d '{"request_id":"demo-complex","messages":[{"role":"user","content":"Explain the Python algorithmic complexity of binary search and prove why it is logarithmic."}]}'

echo '\n\nMetrics'
curl -sS "$endpoint/v1/metrics"
echo
