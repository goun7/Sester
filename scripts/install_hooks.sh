#!/usr/bin/env bash
# AGENT-MESH hook kurucusu — 4 kardeş-repo'ya guard+ledger hook'ları (idempotent).
#
#   bash scripts/install_hooks.sh
#
# Kurar: .git/hooks/pre-commit (guard, fail-loud) + .git/hooks/post-commit
# (HAT DEFTERİ yazıcı, asla bloklamaz). Marker'sız MEVCUT hook'ları EZMEZ —
# korunur ve bildirilir. Marker: "# AGENT-MESH".
set -euo pipefail

MESH_ROOT="/home/gokun/projects"
LEDGER="$MESH_ROOT/01_unicorn/HAT_DEFTERI.md"
MARKER="# AGENT-MESH"

REPOS=(
  "$MESH_ROOT/01_unicorn/63-Sester|$MESH_ROOT/01_unicorn/63-Sester/scripts/git_hooks/guard_sester.py"
  "$MESH_ROOT/01_unicorn/64-Tenderix|$MESH_ROOT/01_unicorn/64-Tenderix/scripts/git_hooks/guard_tenderix.py"
  "$MESH_ROOT/05_acik_kaynak/TamgaProtocol|$MESH_ROOT/05_acik_kaynak/TamgaProtocol/tools/git_hooks/guard_tamga.py"
  "$MESH_ROOT/05_acik_kaynak/Veridict|$MESH_ROOT/05_acik_kaynak/Veridict/scripts/git_hooks/guard_veridict.py"
)

write_pre_commit() { # $1=hedef-yol $2=guard-yolu (mutlak)
  cat > "$1" <<EOF
#!/usr/bin/env bash
$MARKER pre-commit — sözleşme-guard'ı (fail-loud; --no-verify YASAK)
set -euo pipefail
exec python3 "$2"
EOF
  chmod +x "$1"
}

write_post_commit() {
  cat > "$1" <<EOF
#!/usr/bin/env bash
$MARKER post-commit — HAT DEFTERİ yazıcı (ASLA bloklamaz)
repo=\$(basename "\$(git rev-parse --show-toplevel)")
short=\$(git rev-parse --short HEAD 2>/dev/null || echo "?")
subject=\$(git log -1 --pretty=%s 2>/dev/null || echo "(konu-yok)")
row="| \$(date '+%Y-%m-%d %H:%M') | \$repo | \$short | \$subject |"
printf '%s\n' "\$row" >> "$LEDGER" 2>/dev/null || true
exit 0
EOF
  chmod +x "$1"
}

touch "$LEDGER"
echo "== AGENT-MESH kurulum =="

for entry in "${REPOS[@]}"; do
  repo="${entry%%|*}"; guard="${entry#*|}"
  hooks="$repo/.git/hooks"
  if [[ ! -d "$hooks" ]]; then
    echo "SKIP (git-yok): $repo"; continue
  fi
  if [[ ! -f "$guard" ]]; then
    echo "SKIP (guard-yok): $guard"; continue
  fi
  pre="$hooks/pre-commit"; post="$hooks/post-commit"
  # pre-commit
  if [[ -f "$pre" ]] && ! grep -q "$MARKER" "$pre"; then
    cp "$pre" "$pre.user-backup"
    echo "  korunup-yedeklendi: $pre.user-backup"
  fi
  write_pre_commit "$pre" "$guard"
  # post-commit
  if [[ -f "$post" ]] && ! grep -q "$MARKER" "$post"; then
    cp "$post" "$post.user-backup"
    echo "  korunup-yedeklendi: $post.user-backup"
  fi
  write_post_commit "$post"
  echo "OK: $(basename "$repo") — pre-commit guard + post-commit defter-yazar"
done

echo "BİTTİ — READ-FIRST kuralı: HAT DEFTERİ = $LEDGER"
