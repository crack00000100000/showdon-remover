# showdon-remover

쇼돈 팀 전용 macOS 자막 제거 도구. AI 기반(STTN 모델)으로 영상의 박힌 자막을 깔끔하게 제거합니다.

[YaoFANGUK/video-subtitle-remover](https://github.com/YaoFANGUK/video-subtitle-remover) 의 GUI 단순화 + macOS 네이티브 .app 패키징 버전.

설치 위치: `~/showdon/showdon-remover/`  /  결과 저장: `~/showdon/removeds/`

## 설치

[설치 가이드](./설치가이드.md) 참고.

빠른 설치 (터미널 한 줄):
```bash
cd ~/Downloads && curl -fsSL -o install.command https://raw.githubusercontent.com/crack00000100000/showdon-remover/main/install.command && chmod +x install.command && xattr -d com.apple.quarantine install.command 2>/dev/null && open install.command
```

10~25분 소요. 자동으로 brew / Python 3.13 / ffmpeg / git / PyTorch / PaddlePaddle 설치 후 `자막 제거 도구.app` 빌드까지.

## 실행

`~/showdon/showdon-remover/dist/자막 제거 도구.app` 더블클릭 → Terminal 없이 바로 GUI.

## 기능

- **단순화 GUI** — 좌측 사이드바 / 고급 설정 / 모델 선택 모두 숨김. 팀원이 건드릴 수 있는 건 영상 열기 / 시작 / 중지 / 저장 폴더만
- 한국어 / **STTN 지능형 제거** / **정밀** 자막감지 / **하드웨어 가속 ON** 으로 고정 — 팀원 사용 단순화 목적
- **macOS 네이티브 .app** — Terminal 없이 더블클릭 한 번으로 실행, Dock 아이콘 지원
- **macOS 트래픽 라이트** — 좌측 상단 (네이티브 위치)

## 사용법

1. `자막 제거 도구.app` 실행
2. **열기** 버튼으로 영상 파일 선택 (mp4 / mov / mkv 등)
3. 영상 미리보기에서 자막 영역 드래그로 선택 (없으면 전체 화면 자동 처리)
4. **시작** → 자막 검색 → 제거 → `~/showdon/removeds/` 에 결과 저장
5. 우측 상단 **저장 폴더** 카드 클릭으로 저장 위치 변경 가능

## 기술 스택

- Python 3.13 + PySide6 + qfluentwidgets (GUI)
- PyTorch 2.7 (STTN 모델 추론, MPS GPU 가속)
- PaddlePaddle 3.0 + Paddle OCR (자막 검출)
- ffmpeg (인코딩)

## 모델 업데이트

원본 VSR 의 모델이 업데이트되면 종운님이 수동으로 갱신:

```bash
cd ~/showdon/showdon-remover
# 새 모델 파일을 backend/models/sttn-auto/ 에 복사
git add backend/models/
git commit -m "Update STTN model"
git push origin main
```

팀원은 `install.command` 한 번 더 실행하면 자동으로 git pull 받아 갱신됨.

## 라이선스

원본 [video-subtitle-remover](https://github.com/YaoFANGUK/video-subtitle-remover) 는 Apache 2.0 — 본 프로젝트도 동일.
