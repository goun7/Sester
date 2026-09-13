#!/usr/bin/env bash
# SESTER yayın-kapısı — tek-komut tam-denetim (docs/PUBLICATION_CHECKLIST.md §gate)
#
# Kullanım:
#   bash scripts/publish_gate.sh                      # yalnız yerel-kapı (test/derleme/E2E)
#   PUSH=1 bash scripts/publish_gate.sh               # + commit & push (private)
#   PUSH=1 REPO_RENAME=1 bash scripts/publish_gate.sh # + repo adı goun7/sikke → goun7/sester + About/topics
#
# Kural: her adım fail-loud — ilk RED'de durur, sessiz-geçiş yoktur.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n\033[1;36m== %s ==\033[0m\n' "$1"; }

step "0) Ölü sikke/ kalıntısı + demo-DB'leri temizliği (tombstone → silme)"
rm -rf sikke sikke-demo.sqlite3* sikke-escalation.sqlite3* __pycache__ tests/__pycache__ .pytest_cache
test ! -d sikke || { echo "RED: sikke/ silinemedi"; exit 1; }
echo "OK: sikke/ kaldırıldı (tombstone dönemi kapandı)"

step "1) Tam suite — koşum A (SQLite bacakları)"
.venv/bin/python -m pytest tests/ -q

step "2) Tam suite — koşum B (Postgres-parite, sıfır-skip)"
# eski-ad container da 5499'u tutuyor olabilir (pugio-pg-parity) — ikisini de kaldır
docker rm -f sester-pg-parity pugio-pg-parity >/dev/null 2>&1 || true
docker run -d --name sester-pg-parity -e POSTGRES_PASSWORD=sester -p 5499:5432 postgres:16-alpine >/dev/null
for i in $(seq 1 30); do docker exec sester-pg-parity pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
export SESTER_PG_DSN="host=127.0.0.1 port=5499 dbname=postgres user=postgres password=sester"
.venv/bin/python -m pytest tests/ -q

step "3) Kabul-kapıları — S1 dogfood + S2 dört-protokol parite"
.venv/bin/python scripts/s1_dogfood.py
.venv/bin/python scripts/s2_protocol_parity.py

step "4) Marka-varlık PNG'leri (OG 1280×640 + avatar 512×512)"
.venv/bin/python scripts/make_brand_assets.py

step "5) 0.5.0 artefaktları — build + twine check"
.venv/bin/python -m pip install -q build twine   # taze-venv guard (idempotent)
rm -rf dist
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*

step "6) Canlı-E2E — uvicorn + tüm akışlar (T0–T10; rastgele-port — çakışma-direnci)"
bash scripts/live_gate.sh $(( 8500 + RANDOM % 400 ))

if [[ "${PUSH:-0}" != "1" ]]; then
  printf '\n\033[1;32mYEREL-KAPI TAMAM — push istenirse: PUSH=1 bash scripts/publish_gate.sh\033[0m\n'
  exit 0
fi

step "7) Git — durum, commit, push (private)"
git add -A
git commit -m "SESTER v0.5.0 — identity migration Sikke→Sester + S5 facilitator_svc + S6 joint acceptance (frozen wire fields preserved)" \
  || echo "commit yok (değişiklik yok) — devam"
git push origin HEAD

if [[ "${REPO_RENAME:-0}" == "1" ]]; then
  step "8) GitHub repo-detayları — rename + About/topics"
  # Uzak-değeri VARSAY; sağlamlaştırılmış ad kökü kullan (push-kanıtı 2026-09-13: goun7/sikke)
  gh repo edit goun7/sikke --name sester \
    --description "x402-style metering, quota, fail-closed policy and hash-chain receipts for AI-agent APIs — one ASGI middleware" \
    --add-topic x402 --add-topic ai-agents --add-topic metering --add-topic payments \
    --add-topic asgi-middleware --add-topic fintech
  echo "OK: goun7/sester — About/topics ayarlandı"
fi

printf '\n\033[1;32mYAYIN-KAPISI TAMAM — v0.5.0 private yayında.\033[0m\n'
