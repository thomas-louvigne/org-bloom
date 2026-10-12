#!/usr/bin/env bash
# Publish wiki/*.org to the GitHub wiki of this repository.
# The wiki's first page must have been created once from the GitHub web interface.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
origin="$(git -C "$repo_root" remote get-url origin)"
wiki_url="${origin%.git}.wiki.git"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git clone --quiet "$wiki_url" "$tmp/wiki"
find "$tmp/wiki" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp "$repo_root"/wiki/*.org "$tmp/wiki/"

cd "$tmp/wiki"
git add -A
if git diff --cached --quiet; then
  echo "Wiki already up to date."
  exit 0
fi
git commit --quiet -m "Sync wiki from $(git -C "$repo_root" rev-parse --short HEAD)"
git push --quiet
echo "Wiki published: ${origin%.git}/wiki" | sed 's#git@github.com:#https://github.com/#'
