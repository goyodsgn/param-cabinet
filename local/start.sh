#!/bin/bash
# Start the local studio. First run installs uv (a Python runner) and CadQuery; later runs start in seconds.
set -e
cd "$(dirname "$0")/.."
UV="$(command -v uv || true)"
if [ -z "$UV" ]; then
  if [ ! -x "$HOME/.local/bin/uv" ]; then
    echo "uv 설치 중 (처음 한 번만)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
  fi
  UV="$HOME/.local/bin/uv"
fi
echo "스튜디오 준비 중 (처음에는 CadQuery 설치로 몇 분 걸립니다)..."
exec "$UV" run --python 3.11 --with cadquery --with numpy python local/studio.py
