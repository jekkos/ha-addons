#!/bin/bash
REPO="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0
FAILED=()

log()  { echo -e "\n\033[1;36m==> $1\033[0m"; }
ok()   { echo -e "\033[1;32m  PASS\033[0m $1"; PASS=$((PASS+1)); }
fail() { echo -e "\033[1;31m  FAIL\033[0m $1"; FAIL=$((FAIL+1)); }

build_and_test() {
  local name="$1" dir="$2" run_args="${3:-}"
  local image="test/$name" container="test-$$-$name"

  log "[$name] Building"
  local build_out
  if build_out=$(docker build -t "$image" "$REPO/$dir" 2>&1); then
    ok "$name: build succeeded"
  else
    fail "$name: build failed"
    echo "$build_out" | tail -20 | sed 's/^/    /'
    FAILED+=("$name (build)")
    docker rmi -f "$image" 2>/dev/null
    return
  fi

  log "[$name] Smoke test"
  docker rm -f "$container" 2>/dev/null
  docker run -d --name "$container" $run_args "$image" 2>/dev/null
  sleep 5

  if docker ps -q --filter "name=$container" | grep -q .; then
    ok "$name: container running"
    docker logs "$container" 2>&1 | tail -8 | sed 's/^/    /'
  else
    fail "$name: container exited (code: $(docker inspect -f '{{.State.ExitCode}}' "$container" 2>/dev/null))"
    docker logs "$container" 2>&1 | tail -15 | sed 's/^/    /'
    FAILED+=("$name (runtime)")
  fi

  docker rm -f "$container" 2>/dev/null
  docker rmi -f "$image" 2>/dev/null
}

echo "================================"
log "Testing all HA addons locally"
echo "================================"

build_and_test "a3-odbd2-soc"       "a3-odbd2-soc"       "--network host"
build_and_test "deye-dummycloud"    "deye-dummycloud-node" "--network host"
build_and_test "s0pcm-reader"       "s0pcm"
build_and_test "solarmeter"         "solarmeter"

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed"
[ ${#FAILED[@]} -gt 0 ] && echo "Failed: ${FAILED[*]}"
echo "================================"
[ $FAIL -eq 0 ]
