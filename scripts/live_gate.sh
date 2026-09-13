#!/usr/bin/env bash
# SESTER canlı-E2E kapısı — gerçek uvicorn-sürecinde tüm akışlar (v0.5.0).
#
# Kullanım:  bash scripts/live_gate.sh [port]
# Kapsam:
#   T0  healthz — sürüm + zincir SAĞLAM
#   T1  keşif — /agents.json
#   T2  402-challenge — ödemesiz çağrı
#   T3  HMAC (pugio0) mutlu-yol → 200 + X-Sester-Receipt; aynı zarf replay → 402
#   T4  bozuk-HMAC → 402 (500 DEĞİL — fail-closed)
#   T5  EVM (Sester-EVM) mutlu-yol → 200
#   T6  bozuk-EVM → 402 (500 DEĞİL — v0.4 düzeltmesi)
#   T7  UCP — satıcı-ucu /ucp/issue → satıcı-mühürlü zarf → 200
#   T8  kota — 4×0.05 = 0.20quota → 5. çağrı 402 quota_exceeded
#   T9  politika — bilinmeyen-host → 402 policy_denied
#   T10 panel + kapanış zincir-durumu
#
# Kural: her adım fail-loud — ilk RED'de durur. DB'ler /tmp'de yalıtımlı;
# kalıcı demo-DB'lerine (sester-demo.sqlite3) DOKUNULMAZ.
set -uo pipefail
cd "$(dirname "$0")/.."

PORT="${1:-8402}"
BASE="http://127.0.0.1:${PORT}"
SECRET="sester-demo-secret-v0"           # demo sabiti (sester/demo_api.py)
TMP="$(mktemp -d /tmp/sester-live-XXXXXX)"
LOG="$TMP/uvicorn.log"

export SESTER_ESCALATION_DB="$TMP/esc.sqlite3"
export SESTER_DEMO_LEDGER_DB="$TMP/demo.sqlite3"

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); printf '  \033[1;32mOK\033[0m  %s\n' "$1"; }
red()  { FAIL=$((FAIL+1)); printf '  \033[1;31mRED\033[0m  %s\n' "$1"; }
step() { printf '\n\033[1;36m== %s ==\033[0m\n' "$1"; }

expect() { # expect <ad> <beklenen> <gerçekleşen>
  if [[ "$3" == "$2" ]]; then ok "$1 ($3)"; else red "$1 — beklenen $2, gelen $3"; fi
}

hmac_payment() { # hmac_payment <agent> <nonce> <amount> <path>
  local mac
  mac=$(python3 - "$1" "$2" "$3" "$4" "$SECRET" <<'PY'
import hashlib, hmac, sys
a, n, amt, p, s = sys.argv[1:6]
print(hmac.new(s.encode(), f"{a}|{n}|{amt}|{p}".encode(), hashlib.sha256).hexdigest())
PY
)
  printf 'pugio0 %s:%s:%s:%s' "$1" "$2" "$3" "$mac"
}

cleanup() { [[ -n "${UVI_PID:-}" ]] && kill "$UVI_PID" 2>/dev/null; }
trap cleanup EXIT

step "Başlatma — uvicorn sester.demo_api:app :${PORT} (yalıtımlı DB: $TMP)"
.venv/bin/python -m uvicorn sester.demo_api:app --port "$PORT" >"$LOG" 2>&1 &
UVI_PID=$!
UP=0
for _ in $(seq 1 40); do
  curl -sf "$BASE/healthz" >/dev/null 2>&1 && { UP=1; break; }
  sleep 0.5
done
if [[ "$UP" != "1" ]]; then red "sunucu ayağa kalkmadı"; tail -20 "$LOG"; exit 1; fi
ok "sunucu ayakta"

step "T0 healthz — sürüm + zincir"
HZ=$(curl -sf "$BASE/healthz")
echo "$HZ" | grep -q '"version": *"0.5.0"' && ok "healthz version=0.5.0" || red "healthz sürüm: $HZ"
echo "$HZ" | grep -q '"chain_valid": *true' && ok "healthz chain_valid=true" || red "zincir: $HZ"

step "T1 keşif — /agents.json"
curl -sf "$BASE/agents.json" | grep -q 'sester-demo' && ok "agents.json sester-demo ilan ediyor" || red "keşif-içeriği"

step "T2 402-challenge — ödemesiz"
ST=$(curl -s -o "$TMP/t2.body" -w '%{http_code}' "$BASE/weather")
expect "ödemesiz çağrı" 402 "$ST"
grep -q 'payment_required' "$TMP/t2.body" && ok "challenge gövdesi payment_required" || red "challenge-gövdesi: $(head -c 200 "$TMP/t2.body")"

step "T3 HMAC (pugio0) mutlu-yol + replay"
PAY=$(hmac_payment "lg-h1" "lg-n1" "0.05" "/weather")
ST=$(curl -s -D "$TMP/t3.h" -o "$TMP/t3.body" -w '%{http_code}' \
  -H "X-Sester-Agent: lg-h1" -H "X-Payment: $PAY" "$BASE/weather")
expect "HMAC ilk-çağrı" 200 "$ST"
grep -qi '^x-sester-receipt:' "$TMP/t3.h" && ok "X-Sester-Receipt başlığı var" || red "receipt-başlığı eksik: $(grep -i '^x-sester' "$TMP/t3.h" | tr '\n' ' ')"
ST=$(curl -s -o /dev/null -w '%{http_code}' \
  -H "X-Sester-Agent: lg-h1" -H "X-Payment: $PAY" "$BASE/weather")
expect "HMAC replay (aynı zarf)" 402 "$ST"

step "T4 bozuk-HMAC → 402 (fail-closed)"
ST=$(curl -s -o /dev/null -w '%{http_code}' \
  -H "X-Sester-Agent: lg-bad" -H "X-Payment: pugio0 lg-bad:bn:0.05:deadbeef" "$BASE/weather")
expect "bozuk-maç" 402 "$ST"

step "T5 EVM (Sester-EVM) mutlu-yol"
EPAY=$(.venv/bin/python -m sester.demo_api --evm "lg-e1" "/weather" | head -n1)
ST=$(curl -s -o /dev/null -w '%{http_code}' -H "X-Payment: $EPAY" "$BASE/weather")
expect "EVM ilk-çağrı" 200 "$ST"

step "T6 bozuk-EVM → 402 (500 DEĞİL — v0.4 fail-closed düzeltmesi)"
ST=$(curl -s -o /dev/null -w '%{http_code}' -H "X-Payment: Sester-EVM !!!bozuk-b64!!!" "$BASE/weather")
expect "bozuk-EVM zarfı" 402 "$ST"

step "T7 UCP — satıcı-ucu üretim + satıcı-mühürlü zarf"
UPAY=$(curl -sf "$BASE/ucp/issue?agent=lg-ucp&resource=/weather" | python3 -c 'import json,sys; print(json.load(sys.stdin)["payment_header"])')
ST=$(curl -s -o /dev/null -w '%{http_code}' -H "X-Payment: $UPAY" "$BASE/weather")
expect "UCP satıcı-zarfıyla çağrı" 200 "$ST"

step "T8 kota — lg-q1: 4×0.05 → 5. çağrı 402 quota_exceeded"
Q=0
for i in 1 2 3 4; do
  QP=$(hmac_payment "lg-q1" "lg-q-n$i" "0.05" "/weather")
  ST=$(curl -s -o /dev/null -w '%{http_code}' -H "X-Sester-Agent: lg-q1" -H "X-Payment: $QP" "$BASE/weather")
  [[ "$ST" == "200" ]] && Q=$((Q+1))
done
expect "kota-içi 4 çağrı" 4 "$Q"
QP=$(hmac_payment "lg-q1" "lg-q-n5" "0.05" "/weather")
ST=$(curl -s -o "$TMP/t8.body" -w '%{http_code}' -H "X-Sester-Agent: lg-q1" -H "X-Payment: $QP" "$BASE/weather")
expect "5. çağrı (kota-aşımı)" 402 "$ST"
grep -q 'quota_exceeded' "$TMP/t8.body" && ok "kota-hatası quota_exceeded" || red "kota-gövdesi: $(head -c 200 "$TMP/t8.body")"

step "T9 politika — bilinmeyen-host (catch-all deny)"
DP=$(hmac_payment "lg-h1" "lg-n9" "0.05" "/bilinmeyen")
ST=$(curl -s -o "$TMP/t9.body" -w '%{http_code}' -H "X-Sester-Agent: lg-h1" -H "X-Payment: $DP" "$BASE/bilinmeyen")
expect "bilinmeyen-host" 402 "$ST"
grep -q 'policy_denied' "$TMP/t9.body" && ok "politika-hatası policy_denied" || red "politika-gövdesi: $(head -c 200 "$TMP/t9.body")"

step "T10 panel + kapanış zinciri"
ST=$(curl -s -o "$TMP/t10.html" -w '%{http_code}' "$BASE/panel")
expect "panel" 200 "$ST"
grep -q 'SESTER' "$TMP/t10.html" && ok "panel Sester-markalı" || red "panel-markası"
curl -sf "$BASE/healthz" | grep -q '"chain_valid": *true' && ok "kapanış zinciri SAĞLAM" || red "kapanış-zinciri"

printf '\n'
if [[ "$FAIL" -eq 0 ]]; then
  printf '\033[1;32mCANLI-KAPI TAMAM — %s doğrulama geçti (v0.5.0 canlı akışlar).\033[0m\n' "$PASS"
  exit 0
else
  printf '\033[1;31mCANLI-KAPI RED — %s geçti, %s REDD. uvicorn-log: %s\033[0m\n' "$PASS" "$FAIL" "$LOG"
  exit 1
fi
