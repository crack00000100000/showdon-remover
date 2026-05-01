#!/bin/bash
# =============================================================================
# showdon-vsr 실행 스크립트 (macOS)
# 더블클릭으로 GUI 실행. 매일 사용하는 스크립트.
# =============================================================================
# 동작 순서:
#   1. 스크립트가 위치한 폴더로 이동
#   2. 가상환경(venv) 존재 확인
#   3. 필수 모델 파일 존재 + 크기 검증
#   4. 백그라운드로 git fetch (최대 3초) → 새 버전 알림
#   5. venv 활성화 후 python gui.py 실행
# =============================================================================

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info() { echo -e "${BLUE}[정보]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC}  $1"; }
warn() { echo -e "${YELLOW}[알림]${NC} $1"; }
err()  { echo -e "${RED}[에러]${NC} $1"; }

# 종료 시 창이 즉시 닫히지 않도록 (에러 메시지 확인용)
on_exit() {
  local code=$?
  if [ $code -ne 0 ]; then
    echo ""
    echo -e "${RED}프로그램이 비정상 종료되었습니다. 메시지를 확인해주세요.${NC}"
    echo "아무 키나 누르면 창이 닫힙니다."
    read -n 1 -s
  fi
}
trap on_exit EXIT

# ---- 1. 스크립트 위치로 이동 ----------------------------------------------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

clear
echo -e "${BOLD}================================================${NC}"
echo -e "${BOLD}      showdon-vsr 자막 제거 도구${NC}"
echo -e "${BOLD}================================================${NC}"
echo ""

# ---- 2. venv 점검 ---------------------------------------------------------
if [ ! -d "videoEnv" ]; then
  err "Python 가상환경(videoEnv)이 없습니다."
  err "먼저 install.command 를 실행해 설치를 완료해주세요."
  exit 1
fi

if [ ! -f "gui.py" ]; then
  err "gui.py 를 찾을 수 없습니다 (현재 위치: $SCRIPT_DIR)."
  err "이 스크립트가 showdon-vsr 폴더 안에 있는지 확인해주세요."
  exit 1
fi

# ---- 3. 필수 모델 파일 점검 -----------------------------------------------
# (macOS 기본 bash 3.2 호환을 위해 평행 배열로 작성)
REQUIRED_MODEL_PATHS=(
  "backend/models/sttn-auto/infer_model.pth"
  "backend/models/V5/ch_det/inference.pdiparams"
)
REQUIRED_MODEL_NAMES=(
  "STTN 지능형 제거 모델"
  "Paddle OCR (자막 검출)"
)

MISSING_MODELS=()
for i in "${!REQUIRED_MODEL_PATHS[@]}"; do
  path="${REQUIRED_MODEL_PATHS[$i]}"
  name="${REQUIRED_MODEL_NAMES[$i]}"
  if [ ! -f "$path" ]; then
    MISSING_MODELS+=("$name ($path)")
  fi
done

if [ ${#MISSING_MODELS[@]} -gt 0 ]; then
  err "필수 모델 파일이 누락되었습니다:"
  for m in "${MISSING_MODELS[@]}"; do
    echo "    - $m"
  done
  err ""
  err "install.command 를 다시 실행해 모델을 받아주세요."
  exit 1
fi

# 크기 검증 (다운로드 손상 감지)
STTN_SIZE=$(stat -f%z "backend/models/sttn-auto/infer_model.pth" 2>/dev/null || echo 0)
if [ "$STTN_SIZE" -lt 50000000 ]; then
  warn "STTN 모델 파일이 비정상적으로 작습니다 ($STTN_SIZE bytes)."
  warn "다운로드가 손상되었을 수 있습니다. install.command 재실행을 권장합니다."
  echo ""
fi

ok "모델 파일 정상"

# ---- 4. 업데이트 체크 (백그라운드, 최대 3초 대기) -------------------------
if command -v git &>/dev/null && [ -d ".git" ]; then
  (
    git fetch origin main &>/dev/null
  ) &
  FETCH_PID=$!

  # 최대 3초 대기
  for _ in 1 2 3; do
    if ! kill -0 "$FETCH_PID" 2>/dev/null; then
      break
    fi
    sleep 1
  done

  # 아직 안 끝났으면 그대로 둠 (다음 실행 때 결과 반영)
  if ! kill -0 "$FETCH_PID" 2>/dev/null; then
    wait "$FETCH_PID" 2>/dev/null || true

    LOCAL_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "")
    REMOTE_HEAD=$(git rev-parse origin/main 2>/dev/null || echo "")

    if [ -n "$LOCAL_HEAD" ] && [ -n "$REMOTE_HEAD" ] && [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
      echo ""
      warn "🆕  새 버전이 있습니다. install.command 를 다시 실행해 업데이트하시는 걸 권장합니다."
      warn "    (지금은 그냥 실행됩니다)"
      echo ""
    fi
  fi
fi

# ---- 5. venv 활성화 + GUI 실행 --------------------------------------------
# shellcheck disable=SC1091
source videoEnv/bin/activate

info "GUI 실행 중..."
echo ""

python gui.py
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo ""
  err "GUI 가 비정상 종료되었습니다 (exit code: $EXIT_CODE)."
  exit $EXIT_CODE
fi
