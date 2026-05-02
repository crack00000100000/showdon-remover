#!/bin/bash
# =============================================================================
# make_app.sh — '쇼돈 자막 제거기.app' 번들 빌드 스크립트
#
# 사용:
#     ./make_app.sh
#
# 결과:
#     dist/쇼돈 자막 제거기.app
#
# 동작:
#     1) design/icon.svg → design/icon.icns 변환
#     2) .app 디렉토리 구조 생성
#     3) ad-hoc 코드사인 (TCC 다이얼로그가 정상 표시되도록)
#
# 첫 실행 시 macOS 가 "문서 폴더 접근 허용" 다이얼로그를 띄움 → "허용" 클릭 →
# 그다음부터는 더블클릭으로 GUI 만 바로 뜸 (Terminal X)
# =============================================================================

set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="쇼돈 자막 제거기"
LEGACY_APP_NAME="자막 제거 도구"
DIST_DIR="dist"
APP_DIR="${DIST_DIR}/${APP_NAME}.app"
LEGACY_APP_DIR="${DIST_DIR}/${LEGACY_APP_NAME}.app"
CONTENTS="${APP_DIR}/Contents"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

step() { echo -e "${BLUE}[STEP]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC}   $1"; }
err()  { echo -e "${RED}[ERR]${NC}  $1"; }

# ---- 사전 검증 -----------------------------------------------------------
for f in design/icon.svg design/Info.plist design/launcher.sh design/make_icns.py; do
    if [ ! -f "$f" ]; then
        err "$f 가 없습니다."
        exit 1
    fi
done
if [ ! -d "videoEnv" ]; then
    err "videoEnv 가 없습니다. 먼저 install.command 를 실행하거나 수동으로 설치해주세요."
    exit 1
fi

# ---- 1) icon.svg → icon.icns -------------------------------------------
step "1/4  icon.svg → icon.icns 변환"
# shellcheck disable=SC1091
source videoEnv/bin/activate
python design/make_icns.py
deactivate
if [ ! -f "design/icon.icns" ]; then
    err "icon.icns 생성 실패"
    exit 1
fi
ok "icon.icns 생성 완료"

# ---- 2) .app 디렉토리 구조 ---------------------------------------------
step "2/4  .app 번들 구조 생성"
rm -rf "${APP_DIR}"
# 옛 이름의 .app 가 dist 에 남아있으면 같이 정리
if [ -d "${LEGACY_APP_DIR}" ]; then
    rm -rf "${LEGACY_APP_DIR}"
    ok "옛 ${LEGACY_APP_NAME}.app 정리"
fi
mkdir -p "${CONTENTS}/MacOS" "${CONTENTS}/Resources"

cp design/Info.plist "${CONTENTS}/Info.plist"
cp design/icon.icns  "${CONTENTS}/Resources/icon.icns"
cp design/launcher.sh "${CONTENTS}/MacOS/launcher"
chmod +x "${CONTENTS}/MacOS/launcher"
ok ".app 구조 완료"

# ---- 3) ad-hoc 코드사인 -------------------------------------------------
step "3/4  ad-hoc 코드사인"
codesign --force --deep --sign - "${APP_DIR}" 2>&1 | sed 's/^/  /' || {
    err "codesign 실패 — Xcode CLI Tools 가 설치되어 있는지 확인하세요."
    exit 1
}
codesign --verify --verbose=2 "${APP_DIR}" 2>&1 | sed 's/^/  /' || true
ok "ad-hoc 서명 완료"

# ---- 4) 마무리 ---------------------------------------------------------
step "4/4  Finder 에서 dist/ 폴더 열기"
open "${DIST_DIR}/" || true

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅  ${APP_NAME}.app 빌드 완료!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo "결과물 위치:"
echo "  ${PWD}/${APP_DIR}"
echo ""
echo "다음 단계:"
echo "  1) ${APP_DIR} 더블클릭"
echo "  2) (첫 실행만) macOS 가 '문서 폴더 접근 허용?' 다이얼로그 표시"
echo "     → '허용' 클릭"
echo "  3) GUI 가 Terminal 없이 바로 등장"
echo "  4) Dock 에 등록하려면 ${APP_DIR} 을 Dock 에 끌어다 놓기"
echo ""
