#!/bin/bash
# =============================================================================
# 쇼돈 자막 제거기 — .app 단독 빌더
#
# 용도: 쇼돈_리무버_install.command 가 끝까지 돌았는데 .app 빌드만 실패했거나,
#       나중에 코드 업데이트 후 .app 만 다시 빌드하고 싶을 때 사용.
# =============================================================================

set -uo pipefail

INSTALL_DIR="$HOME/showdon/showdon-remover"

cd "$HOME"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}[정보]${NC} $1"; }
ok()      { echo -e "${GREEN}[완료]${NC} $1"; }
warn()    { echo -e "${YELLOW}[경고]${NC} $1"; }
err()     { echo -e "${RED}[에러]${NC} $1"; }

on_exit() {
  local code=$?
  echo ""
  if [ $code -eq 0 ]; then
    echo -e "${GREEN}${BOLD}완료!${NC}  아무 키나 누르면 창이 닫힙니다."
  else
    echo -e "${RED}${BOLD}빌드가 중단되었습니다.${NC}  메시지를 확인하시고 아무 키나 누르세요."
  fi
  read -n 1 -s
}
trap on_exit EXIT

clear
echo "================================================"
echo "    쇼돈 자막 제거기 — .app 단독 빌더"
echo "================================================"
echo ""

if [ ! -d "$INSTALL_DIR" ]; then
  err "설치 폴더가 없습니다: $INSTALL_DIR"
  echo ""
  echo "먼저 '쇼돈_리무버_install.command' 를 실행해 설치를 완료해주세요."
  exit 1
fi

if [ ! -d "$INSTALL_DIR/videoEnv" ]; then
  err "videoEnv 가 없습니다: $INSTALL_DIR/videoEnv"
  echo ""
  echo "먼저 '쇼돈_리무버_install.command' 를 실행해 의존성 설치를 완료해주세요."
  exit 1
fi

if [ ! -f "$INSTALL_DIR/make_app.sh" ]; then
  err "make_app.sh 를 찾을 수 없습니다."
  exit 1
fi

chmod +x "$INSTALL_DIR/make_app.sh" 2>/dev/null || true

info "코드 최신 버전으로 업데이트 (git pull)..."
cd "$INSTALL_DIR"
if git pull origin main 2>/dev/null; then
  ok "최신 버전 반영 완료"
else
  warn "git pull 실패 (오프라인/충돌) — 기존 코드로 빌드 진행"
fi

info ".app 빌드 시작..."
echo ""
if ./make_app.sh; then
  echo ""
  echo -e "${GREEN}${BOLD}================================================${NC}"
  echo -e "${GREEN}${BOLD}        🎉  .app 빌드 완료!${NC}"
  echo -e "${GREEN}${BOLD}================================================${NC}"
  echo ""
  echo "다음 파일을 더블클릭해 GUI 를 실행하세요:"
  echo ""
  echo -e "    ${BOLD}$INSTALL_DIR/dist/쇼돈 자막 제거기.app${NC}"
  echo ""
  echo "  • 첫 실행만 우클릭 → '열기' (Gatekeeper 우회)"
  echo "  • Dock 에 끌어다 놓으면 한 번 클릭으로 실행"
else
  err ".app 빌드 실패 — 위 메시지를 확인해주세요."
  exit 1
fi
