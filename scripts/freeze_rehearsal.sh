#!/bin/bash
# Rehearsal of the freeze procedure (SPEC §14 M5, §17.6) on the DEV files, in a throw-away clone.
# Nothing here touches the real repository, its tags, its remote, or the test split:
#   - the clone has its `origin` removed, so a tag can never be pushed from it
#   - data/ and outputs/ are symlinked read-only use (hash rows are read from them; no step writes into them)
# Steps: clone -> write dev hash rows into PROTOCOL.md -> commit -> tag freeze-v1 (in the clone) -> the guard
# must PASS; then it must FAIL for: a frozen-file change, a wrong hash, a dirty tree, a missing tag.
# Usage: scripts/freeze_rehearsal.sh [git-ref]      (default: HEAD of the current checkout)
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
REF="${1:-HEAD}"
PY="${PYTHON:-/home/cvlab/anaconda3/envs/easqaa/bin/python}"
WORK="$(mktemp -d /tmp/freeze_rehearsal.XXXXXX)"
CLONE="$WORK/clone"
fail=0
say() { printf '%s\n' "$*"; }
check() { # check <name> <expected exit: 0|1> -- command...
  name="$1"; want="$2"; shift 3
  out="$("$@" 2>&1)"; got=$?
  if { [ "$want" = 0 ] && [ $got -eq 0 ]; } || { [ "$want" = 1 ] && [ $got -ne 0 ]; }; then
    say "PASS  $name (exit $got)"; else say "FAIL  $name (expected exit $want, got $got)"; say "$out" | sed 's/^/      /'; fail=1; fi
}
trap 'rm -rf "$WORK"' EXIT

say "== clone $REF of $REPO into $CLONE"
git clone -q --no-hardlinks "$REPO" "$CLONE" && cd "$CLONE" || exit 2
git checkout -q "$(git -C "$REPO" rev-parse "$REF")" || exit 2
git remote remove origin
git config user.email rehearsal@example.invalid; git config user.name rehearsal
ln -s "$REPO/data" data; ln -s "$REPO/outputs" outputs
export PYTHONPATH="$CLONE/src"
SARQA=("$PY" -c "from sarqa.cli import main; raise SystemExit(main())")

say "== before the tag"
check "guard refuses without a freeze tag" 1 -- "${SARQA[@]}" freeze check --split dev

say "== write the dev hash rows, commit, tag freeze-v1 (clone only)"
"${SARQA[@]}" freeze hashes --split dev --write | tail -3
git add PROTOCOL.md && git commit -qm "rehearsal: dev hashes in PROTOCOL.md" && git tag freeze-v1
check "guard passes on a clean, frozen tree with matching hashes" 0 -- "${SARQA[@]}" freeze check --split dev

say "== things that must be refused"
echo "# touched" >> src/sarqa/config.py; git commit -qam "rehearsal: change a frozen file"
check "frozen file changed after the tag" 1 -- "${SARQA[@]}" freeze check --split dev
git reset -q --hard HEAD~1
check "guard passes again after reverting" 0 -- "${SARQA[@]}" freeze check --split dev

echo "not committed" > untracked.txt
check "dirty working tree" 1 -- "${SARQA[@]}" freeze check --split dev
rm untracked.txt

sed -i '0,/`[0-9a-f]\{64\}`/s//`0000000000000000000000000000000000000000000000000000000000000000`/' PROTOCOL.md
git commit -qam "rehearsal: wrong hash"
check "hash in PROTOCOL.md does not match the file" 1 -- "${SARQA[@]}" freeze check --split dev
git reset -q --hard HEAD~1

git tag -d freeze-v1 >/dev/null
check "no freeze tag" 1 -- "${SARQA[@]}" freeze check --split dev

say "== hash row tool reports missing test files instead of inventing rows"
out="$("${SARQA[@]}" freeze hashes --split test 2>&1)"; say "$out" | tail -2 | sed 's/^/      /'
case "$out" in *"missing files"*) say "PASS  test rows are not made without test files";; *) say "FAIL  expected a missing-files report"; fail=1;; esac

say "== result"
if [ $fail -eq 0 ]; then say "REHEARSAL PASSED"; else say "REHEARSAL FAILED"; fi
exit $fail
