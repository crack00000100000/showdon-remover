#!/bin/bash
# =============================================================================
# 쇼돈 자막 제거기 설치 스크립트 (macOS / Apple Silicon)
# 팀원에게 배포되는 단일 파일. 더블클릭으로 실행.
# =============================================================================
# 자동으로 점검 / 설치하는 항목:
#   1. Xcode Command Line Tools  (Apple 다이얼로그에서 한 번 클릭 필요)
#   2. Homebrew                  (sudo 비밀번호 한 번 입력 필요)
#   3. Python 3.13
#   4. ffmpeg
#   5. git
#   6. showdon-remover 저장소
#   7. Python 가상환경 + PaddlePaddle + PyTorch + 의존성
# =============================================================================

set -uo pipefail

# ---- 설정 ------------------------------------------------------------------
REPO_URL="https://github.com/crack00000100000/showdon-remover.git"
# 설치 경로 — ~/Documents/ 는 macOS TCC 보호 대상이라 .app 권한 문제 발생.
# 홈 아래 비보호 경로 (~/showdon/) 에 두면 .app 정상 동작.
INSTALL_DIR="$HOME/showdon/showdon-remover"
# (구) 경로 후보들 — install.command 가 자동으로 새 경로로 이주시킴
LEGACY_INSTALL_DIRS=(
    "$HOME/Documents/video-subtitle-remover"
    "$HOME/Documents/showdon-vsr"
    "$HOME/showdon/showdon-vsr"
)
PYTHON_BIN="python3.13"

# 스크립트가 기존 설치 폴더 안에서 실행됐을 수 있으므로 cwd 를 안전한 곳으로 이동
cd "$HOME"

# ---- 색상 / 헬퍼 -----------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

step()    { echo ""; echo -e "${BOLD}${BLUE}>>> $1${NC}"; }
info()    { echo -e "${BLUE}[정보]${NC} $1"; }
ok()      { echo -e "${GREEN}[완료]${NC} $1"; }
warn()    { echo -e "${YELLOW}[경고]${NC} $1"; }
err()     { echo -e "${RED}[에러]${NC} $1"; }

# 종료 시 창 자동으로 닫히지 않게 키 대기
on_exit() {
  local code=$?
  echo ""
  if [ $code -eq 0 ]; then
    echo -e "${GREEN}${BOLD}설치 완료!${NC}  아무 키나 누르면 창이 닫힙니다."
  else
    echo -e "${RED}${BOLD}설치가 중단되었습니다.${NC}  메시지를 확인하시고 아무 키나 누르세요."
  fi
  read -n 1 -s
}
trap on_exit EXIT

# ---- 인트로 ---------------------------------------------------------------
clear
echo "================================================"
echo "    쇼돈 자막 제거기 설치"
echo "================================================"
echo ""
echo "이 스크립트는 자동으로 필요한 프로그램을 점검하고 설치합니다."
echo "도중에 두 번 사용자 액션이 필요할 수 있습니다:"
echo "  • Xcode 다이얼로그에서 '설치' 버튼 클릭"
echo "  • Homebrew 설치 시 sudo 비밀번호 입력"
echo ""
echo "전체 소요 시간: 10~25분 (인터넷 속도에 따라)"
echo ""
read -p "계속하려면 Enter, 취소하려면 Ctrl+C 를 누르세요... " _

# ---- 1. macOS / 아키텍처 확인 ---------------------------------------------
step "1. 시스템 점검"
ARCH=$(uname -m)
MACOS_VERSION=$(sw_vers -productVersion)
info "macOS: $MACOS_VERSION  /  아키텍처: $ARCH"

if [ "$ARCH" != "arm64" ]; then
  warn "Apple Silicon (M1/M2/M3/M4/M5)이 아닙니다."
  warn "Intel Mac 에서는 처리 속도가 매우 느립니다."
  echo ""
  read -p "그래도 진행하시려면 Enter (취소: Ctrl+C)... " _
fi

# ---- 2. Xcode Command Line Tools ------------------------------------------
step "2. Xcode Command Line Tools"
if xcode-select -p &>/dev/null; then
  ok "이미 설치되어 있음 ($(xcode-select -p))"
else
  warn "Xcode Command Line Tools 가 없어 설치를 시작합니다."
  info "잠시 후 Apple 다이얼로그가 뜹니다 → '설치' 버튼을 클릭해주세요."
  xcode-select --install &>/dev/null || true

  info "설치 완료까지 대기 중... (다이얼로그를 닫지 마세요)"
  while ! xcode-select -p &>/dev/null; do
    sleep 5
    echo -n "."
  done
  echo ""
  ok "Xcode Command Line Tools 설치 완료"
fi

# ---- 3. Homebrew ----------------------------------------------------------
step "3. Homebrew"
if ! command -v brew &>/dev/null; then
  # /opt/homebrew/bin 에 설치되어 있는지 확인 (PATH 누락 케이스)
  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
fi

if ! command -v brew &>/dev/null; then
  warn "Homebrew 가 없어 설치를 시작합니다."
  info "도중에 sudo 비밀번호 입력 화면이 한 번 뜹니다."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    if ! grep -q '/opt/homebrew/bin/brew shellenv' "$HOME/.zprofile" 2>/dev/null; then
      echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
      info "~/.zprofile 에 Homebrew PATH 자동 추가됨"
    fi
  fi
  ok "Homebrew 설치 완료"
else
  ok "이미 설치되어 있음 ($(brew --version | head -1))"
fi

# ---- 4. Python 3.13 -------------------------------------------------------
step "4. Python 3.13"
if command -v "$PYTHON_BIN" &>/dev/null; then
  ok "이미 설치되어 있음 ($("$PYTHON_BIN" --version))"
else
  info "Python 3.13 을 brew 로 설치합니다..."
  brew install python@3.13
  ok "Python 3.13 설치 완료"
fi

# ---- 5. ffmpeg ------------------------------------------------------------
step "5. ffmpeg"
if command -v ffmpeg &>/dev/null; then
  ok "이미 설치되어 있음"
else
  info "ffmpeg 를 brew 로 설치합니다..."
  brew install ffmpeg
  ok "ffmpeg 설치 완료"
fi

# ---- 6. git ---------------------------------------------------------------
step "6. git"
if command -v git &>/dev/null; then
  ok "이미 설치되어 있음 ($(git --version))"
else
  info "git 을 brew 로 설치합니다..."
  brew install git
fi

# ---- 7. 저장소 클론 / 업데이트 / 이주 ---------------------------------------
step "7. showdon-remover 저장소"

# 7-a) 구 경로(~/Documents/...)에 설치돼 있고 새 경로엔 없으면 자동 이주
#      모델 파일(1.4GB)은 mv 로 보존되므로 다시 다운로드하지 않음.
#      videoEnv 는 절대 경로가 박혀있어 이주 후 재생성 필요.
if [ ! -d "$INSTALL_DIR/.git" ]; then
  for OLD in "${LEGACY_INSTALL_DIRS[@]}"; do
    if [ -d "$OLD/.git" ] && [ ! -d "$INSTALL_DIR" ]; then
      warn "기존 설치 감지: $OLD"
      info "새 경로로 이주: $INSTALL_DIR"
      mkdir -p "$(dirname "$INSTALL_DIR")"
      mv "$OLD" "$INSTALL_DIR"
      # 절대 경로가 박혀있는 venv 는 이주 후 작동 보장이 안 되므로 삭제 → 재생성
      rm -rf "$INSTALL_DIR/videoEnv"
      ok "이주 완료 (videoEnv 는 다음 단계에서 재생성)"
      break
    fi
  done
fi

# 7-b) 클론 또는 업데이트
if [ -d "$INSTALL_DIR/.git" ]; then
  info "최신 버전으로 업데이트 (git pull)..."
  cd "$INSTALL_DIR"
  git pull origin main || warn "git pull 실패 (오프라인/인증 이슈) — 기존 코드로 진행"
  ok "업데이트 완료"
elif [ -d "$INSTALL_DIR" ]; then
  err "$INSTALL_DIR 폴더가 존재하지만 git 저장소가 아닙니다."
  err "수동으로 폴더를 비우거나 다른 위치에 설치해주세요."
  exit 1
else
  info "$INSTALL_DIR 에 저장소를 새로 받습니다 (1.4GB, 시간 소요)..."
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone "$REPO_URL" "$INSTALL_DIR"
  ok "Clone 완료"
fi

# 7-c) ~/Documents 잔존 폴더 보고 (용량 절약)
# VSR 은 결과물을 입력 영상 옆에 저장하던 구 동작이라 자동 이동할 데이터 폴더는 없음.
# 코드 폴더는 위 7-a 의 mv 로 이미 처리됨. 누락된 케이스에 대해서만 안내.
for stale in \
    "$HOME/Documents/video-subtitle-remover" \
    "$HOME/Documents/showdon-vsr" \
    "$HOME/showdon/showdon-vsr"; do
  if [ -e "$stale" ]; then
    warn "정리되지 않은 잔존 폴더 감지: $stale (수동 확인 후 삭제 권장 — 용량 절약)"
  fi
done

cd "$INSTALL_DIR"

# ---- 8. Python 가상환경 ---------------------------------------------------
step "8. Python 가상환경 (venv)"
if [ ! -d "videoEnv" ]; then
  info "venv 생성 중..."
  "$PYTHON_BIN" -m venv videoEnv
  ok "venv 생성 완료"
else
  ok "기존 venv 재사용"
fi

# shellcheck disable=SC1091
source videoEnv/bin/activate

info "pip 업그레이드..."
pip install --upgrade pip --quiet

# ---- 9. PaddlePaddle ------------------------------------------------------
step "9. PaddlePaddle (자막 검출 모델용)"
if python -c "import paddle" &>/dev/null; then
  ok "이미 설치되어 있음 ($(python -c 'import paddle; print(paddle.__version__)'))"
else
  info "PaddlePaddle 3.0.0 설치 중... (3~5분)"
  pip install paddlepaddle==3.0.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
  ok "PaddlePaddle 설치 완료"
fi

# ---- 10. PyTorch ----------------------------------------------------------
step "10. PyTorch (STTN 모델용)"
if python -c "import torch" &>/dev/null; then
  ok "이미 설치되어 있음 ($(python -c 'import torch; print(torch.__version__)'))"
else
  info "PyTorch 2.7.0 + torchvision 0.22.0 설치 중... (5~10분, 용량 큼)"
  pip install torch==2.7.0 torchvision==0.22.0
  ok "PyTorch 설치 완료"
fi

# ---- 11. 기타 의존성 ------------------------------------------------------
step "11. 기타 의존성 (requirements.txt)"
info "설치 중..."
pip install -r requirements.txt
ok "의존성 설치 완료"

# ---- 12. 검증 -------------------------------------------------------------
step "12. 설치 검증"
python - <<'PYEOF'
import sys
print(f"Python: {sys.version.split()[0]}")
import torch
print(f"torch: {torch.__version__}  (MPS 사용 가능: {torch.backends.mps.is_available()})")
import paddle
print(f"paddle: {paddle.__version__}")
import cv2
print(f"opencv: {cv2.__version__}")
import PySide6
print(f"PySide6: {PySide6.__version__}")
PYEOF
ok "검증 통과"

# ---- 13. run.command 실행 권한 ---------------------------------------------
chmod +x "$INSTALL_DIR/run.command" 2>/dev/null || true

# ---- 마무리 ---------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}================================================${NC}"
echo -e "${GREEN}${BOLD}          🎉  설치 모두 완료!${NC}"
echo -e "${GREEN}${BOLD}================================================${NC}"
echo ""
echo "이제부터는 다음 파일을 더블클릭해 GUI 를 실행하세요:"
echo ""
echo -e "    ${BOLD}$INSTALL_DIR/run.command${NC}"
echo ""
echo "Finder 에서 위 폴더로 이동:"
echo "  1) Finder 열기"
echo "  2) 메뉴 → 이동 → 폴더로 이동... (단축키: Cmd+Shift+G)"
echo "  3) 다음 경로 붙여넣기: $INSTALL_DIR"
echo "  4) 'run.command' 더블클릭"
echo ""
echo "팁: run.command 를 Dock 에 끌어다 놓으면 한 번 클릭으로 실행됩니다."
echo ""
