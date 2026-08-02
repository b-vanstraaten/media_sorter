#!/usr/bin/env bash
# Cuts a new release: bumps the version, tags it, and updates the Homebrew
# formula's url/sha256 to match. This is every step that release process
# otherwise takes by hand, in order:
#
#   1. Bump `version` in pyproject.toml, refresh uv.lock.
#   2. Run the test suite -- abort if anything fails.
#   3. Commit and push the bump, tag vX.Y.Z, push the tag.
#   4. Download the real release tarball GitHub just generated and compute
#      its actual sha256 (a renamed repo, or GitHub's own archive format,
#      can change these bytes -- never assume, always fetch and check).
#   5. Fill that sha256 into the formula, commit and push.
#   6. If TAP_DIR points at a local clone of the homebrew-marquee tap,
#      copy the updated formula there and push it too.
#
# Usage:
#   scripts/release.sh              # patch bump: 0.3.1 -> 0.3.2
#   scripts/release.sh minor        # minor bump: 0.3.1 -> 0.4.0
#   scripts/release.sh major        # major bump: 0.3.1 -> 1.0.0
#   scripts/release.sh 0.5.0        # explicit version
#
#   TAP_DIR=~/code/homebrew-marquee scripts/release.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

FORMULA="homebrew-marquee-formula.rb"
REPO_URL="https://github.com/b-vanstraaten/marquee"

current_version() {
  grep -m1 '^version = ' pyproject.toml | sed -E 's/version = "(.*)"/\1/'
}

bump_version() {
  local cur="$1" kind="$2"
  case "$kind" in
    major|minor|patch) ;;
    *) echo "$kind"; return ;;  # treat anything else as an explicit version
  esac
  IFS='.' read -r major minor patch <<<"$cur"
  case "$kind" in
    major) echo "$((major + 1)).0.0" ;;
    minor) echo "$major.$((minor + 1)).0" ;;
    patch) echo "$major.$minor.$((patch + 1))" ;;
  esac
}

if [[ -n "$(git status --porcelain)" ]]; then
  echo "error: working tree isn't clean -- commit or stash first." >&2
  exit 1
fi

CUR=$(current_version)
NEW=$(bump_version "$CUR" "${1:-patch}")
echo "==> Releasing v$NEW (currently v$CUR)"

sed -i '' "s/^version = \"$CUR\"/version = \"$NEW\"/" pyproject.toml
grep -q "^version = \"$NEW\"" pyproject.toml || {
  echo "error: failed to bump version in pyproject.toml" >&2
  exit 1
}
uv lock

echo "==> Running tests"
uv run python -m unittest discover -s tests

echo "==> Updating formula for v$NEW"
sed -i '' "s#archive/refs/tags/v$CUR\.tar\.gz#archive/refs/tags/v$NEW.tar.gz#" "$FORMULA"
grep -q "v$NEW.tar.gz" "$FORMULA" || {
  echo "error: failed to update formula url for v$NEW" >&2
  exit 1
}
# Only the sha256 line immediately after the release tarball's own url line
# is the top-level one -- every resource block has its own sha256 too, and
# a plain global replace would clobber all of them (this happened once;
# `n` restricts the substitution to exactly the next line after the match).
sed -i '' "/archive\\/refs\\/tags\\/v$NEW\\.tar\\.gz/{n;s/sha256 \".*\"/sha256 \"REPLACE_WITH_RELEASE_TARBALL_SHA256\"/;}" "$FORMULA"
[[ "$(grep -c 'REPLACE_WITH_RELEASE_TARBALL_SHA256' "$FORMULA")" -eq 1 ]] || {
  echo "error: expected exactly one sha256 placeholder after url substitution" >&2
  exit 1
}
ruby -c "$FORMULA" >/dev/null

git add pyproject.toml uv.lock "$FORMULA"
git commit -m "Bump to v$NEW"
git push origin main

git tag -a "v$NEW" -m "v$NEW"
git push origin "v$NEW"

echo "==> Waiting for the release tarball to become available"
TARBALL_URL="$REPO_URL/archive/refs/tags/v$NEW.tar.gz"
TMP_TARBALL=$(mktemp -t marquee-release).tar.gz
ok=0
for _ in $(seq 1 15); do
  sleep 2
  if curl -sSL -o "$TMP_TARBALL" "$TARBALL_URL" && file "$TMP_TARBALL" | grep -q gzip; then
    ok=1
    break
  fi
done
if [[ "$ok" -ne 1 ]]; then
  echo "error: could not download $TARBALL_URL after retrying" >&2
  exit 1
fi

SHA=$(shasum -a 256 "$TMP_TARBALL" | awk '{print $1}')
rm -f "$TMP_TARBALL"
echo "==> sha256: $SHA"

sed -i '' "s/sha256 \"REPLACE_WITH_RELEASE_TARBALL_SHA256\"/sha256 \"$SHA\"/" "$FORMULA"
grep -q "REPLACE_WITH_RELEASE_TARBALL_SHA256" "$FORMULA" && {
  echo "error: placeholder sha256 still present after substitution" >&2
  exit 1
}
ruby -c "$FORMULA" >/dev/null

DUPES=$(grep -o 'sha256 "[^"]*"' "$FORMULA" | sort | uniq -d)
if [[ -n "$DUPES" ]]; then
  echo "error: duplicate sha256 value(s) in $FORMULA -- refusing to commit a corrupt formula:" >&2
  echo "$DUPES" >&2
  exit 1
fi

git add "$FORMULA"
git commit -m "Fill in the v$NEW release tarball's real sha256"
git push origin main

if [[ -n "${TAP_DIR:-}" && -d "$TAP_DIR/Formula" ]]; then
  echo "==> Updating tap at $TAP_DIR"
  cp "$FORMULA" "$TAP_DIR/Formula/marquee.rb"
  (cd "$TAP_DIR" && git add Formula/marquee.rb && git commit -m "Update to v$NEW" && git push origin main)
  echo "==> Tap updated. Verify with: brew update && brew upgrade marquee"
else
  cat <<EOF

==> Manual follow-up: push the formula to the tap repo (set TAP_DIR to automate this)
    cp $FORMULA <path-to-homebrew-marquee-clone>/Formula/marquee.rb
    cd <path-to-homebrew-marquee-clone>
    git add Formula/marquee.rb && git commit -m "Update to v$NEW" && git push
EOF
fi

echo
echo "==> Done: v$NEW released."
