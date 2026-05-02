#!/bin/bash
# =============================================================================
# 쇼돈 자막 제거기.app 의 실행 진입점
# .app 더블클릭 시 macOS LaunchServices 가 이 스크립트를 호출.
# Terminal 창을 띄우지 않고 GUI 만 바로 실행.
# =============================================================================

INSTALL_DIR="$HOME/showdon/showdon-remover"
PYTHON="$INSTALL_DIR/videoEnv/bin/python"
LOG_FILE="/tmp/vsr-launcher.log"

# 로그를 파일로 (디버그용)
exec > "$LOG_FILE" 2>&1
echo "[launcher] $(date '+%F %T') — 시작"
echo "[launcher] INSTALL_DIR=$INSTALL_DIR"
echo "[launcher] PYTHON=$PYTHON"

# 1) 설치 여부 확인
if [ ! -x "$PYTHON" ]; then
    echo "[launcher] ERR: $PYTHON 가 실행 가능하지 않음"
    osascript <<EOF
display dialog "쇼돈 자막 제거기가 설치되어 있지 않거나 접근 권한이 없습니다.

가능한 원인:
1) install.command 를 아직 실행하지 않음
2) macOS 가 ~/showdon 접근을 차단함 (시스템 설정 → 개인정보 보호 → 파일 및 폴더에서 허용)

설치 위치: $INSTALL_DIR
로그: $LOG_FILE" buttons {"확인"} default button 1 with icon caution with title "쇼돈 자막 제거기"
EOF
    exit 1
fi

if [ ! -f "$INSTALL_DIR/gui.py" ]; then
    echo "[launcher] ERR: gui.py 없음"
    osascript -e 'display dialog "gui.py 를 찾을 수 없습니다." buttons {"확인"} default button 1 with icon stop with title "쇼돈 자막 제거기"'
    exit 1
fi

# 2) GUI 실행
cd "$INSTALL_DIR"
echo "[launcher] $PYTHON gui.py 실행"
exec "$PYTHON" gui.py
