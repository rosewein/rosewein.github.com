#!/bin/sh
# 스크립트는 처음 만든 작업 공간의 절대 경로(/home/claude/sudo, /home/claude/sudo2)를 그대로 쓴다.
# 새 작업 공간에서는 이 스크립트로 저장소의 src/를 그 경로에 복사한 뒤 돌린다(있는 파일은 덮지 않음).
# 원자료는 /home/claude/raw, /home/claude/ext 등에 이지의 다운로드 폴더에서 옮겨 둔다(HANDOFF.md 「원자료」).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
for d in sudo sudo2; do
  mkdir -p /home/claude/$d
  cp -Rn "$HERE/$d/." /home/claude/$d/
done
mkdir -p /home/claude/sudo/page
[ -f /home/claude/sudo/page/data.json ] || cp "$HERE/../data.json" /home/claude/sudo/page/
[ -f /home/claude/sudo/page/index.html ] || cp "$HERE/../index.html" /home/claude/sudo/page/
echo "작업 경로 준비됨: /home/claude/sudo, /home/claude/sudo2"
