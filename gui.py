# -*- coding: utf-8 -*-
"""
@Author  : Fang Yao（原作者） / 改写：Jason Eric
@Time    : 2023/4/1 6:07 下午（原始时间）
@FileName: gui.py
@desc: 字幕去除器图形化界面（由 PySimpleGUI 改写为 PySide6）
       简화 버전: 사이드 메뉴/고급 설정/우측 설정 카드 모두 숨김.
                 기본값을 한국어 / STTN 지능형 제거 / 정밀 / 하드웨어 가속 On 으로 강제 고정.
"""

import sys
import os
import json
import configparser
import multiprocessing
from pathlib import Path


def _prewrite_fixed_config():
    """backend.config 가 로딩되기 전에 config.json 을 강제 고정값으로 미리 기록한다.

    이렇게 하면 모듈 로딩 단계에서 한국어 ini 파일이 정확히 로드되고,
    팀 사용자가 설정을 건드리지 못하게 된다.
    """
    try:
        # gui.py 와 같은 위치 기준
        base_dir = Path(__file__).resolve().parent
        config_path = base_dir / "config" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {}
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
            except Exception:
                data = {}

        data.setdefault("Window", {})["Interface"] = "ko"
        data.setdefault("Main", {})
        data["Main"]["InpaintMode"] = "sttn-auto"
        data["Main"]["SubtitleDetectMode"] = "PP_OCRv5_SERVER"
        data["Main"]["HardwareAcceleration"] = True
        data["Main"]["CheckUpdateOnStartup"] = False

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[warn] 고정 설정 사전 기록 실패: {e}")


# backend.config 임포트 전에 반드시 실행
_prewrite_fixed_config()

import cv2
from PySide6.QtCore import Qt, QTranslator, QRect, QSize
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtWidgets import QApplication, QFrame, QStackedWidget, QHBoxLayout, QLabel
from qfluentwidgets import (FluentWindow, PushButton, Slider, ProgressBar, PlainTextEdit,
                          setTheme, Theme, FluentIcon, CardWidget, SettingCardGroup,
                          ComboBoxSettingCard, SwitchSettingCard, setThemeColor, OptionsConfigItem,
                          OptionsValidator, SubtitleLabel, HollowHandleStyle, qconfig, ConfigItem, QConfig,
                          NavigationWidget, NavigationItemPosition, isDarkTheme, InfoBar)

from qframelesswindow.utils import getSystemAccentColor
from backend.config import config, tr, VERSION
from backend.tools.constant import InpaintMode, SubtitleDetectMode
from backend.tools.theme_listener import SystemThemeListener
from backend.tools.process_manager import ProcessManager
from ui.home_interface import HomeInterface


def _force_fixed_settings():
    """팀 사용자가 설정을 건드리지 않도록 핵심 옵션을 고정값으로 강제한다.

    - 인터페이스 언어: 한국어 (ko)
    - 처리 모델: STTN 지능형 제거 (STTN_AUTO)
    - 자막 감지: 정밀 (PP_OCRv5_SERVER)
    - 하드웨어 가속: On
    - 시작 시 업데이트 확인: Off (팝업 방지)
    """
    try:
        if config.interface.value != 'ko':
            config.set(config.interface, 'ko')
    except Exception:
        pass
    try:
        if config.inpaintMode.value != InpaintMode.STTN_AUTO:
            config.set(config.inpaintMode, InpaintMode.STTN_AUTO)
    except Exception:
        pass
    try:
        if config.subtitleDetectMode.value != SubtitleDetectMode.PP_OCRv5_SERVER:
            config.set(config.subtitleDetectMode, SubtitleDetectMode.PP_OCRv5_SERVER)
    except Exception:
        pass
    try:
        if config.hardwareAcceleration.value is not True:
            config.set(config.hardwareAcceleration, True)
    except Exception:
        pass
    try:
        if config.checkUpdateOnStartup.value is not False:
            config.set(config.checkUpdateOnStartup, False)
    except Exception:
        pass


class SubtitleExtractorGUI(FluentWindow):
    # 사이즈 sanity 상수 — 좌(영상) + 우(옵션·작업목록) 들어갈 최소 폭 보장.
    MIN_WIDTH = 1100
    MIN_HEIGHT = 720
    MAX_REASONABLE_WIDTH = 2800
    MAX_REASONABLE_HEIGHT = 1600
    DEFAULT_WIDTH = 1280
    DEFAULT_HEIGHT = 800

    def __init__(self):
        super().__init__()
        # 禁用云母效果
        self.setMicaEffectEnabled(False)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)

        # 设置窗口图标 (새 SVG 우선, 없으면 기존 .ico fallback)
        _design_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "design")
        _icon_svg = os.path.join(_design_dir, "icon.svg")
        _icon_ico = os.path.join(_design_dir, "vsr.ico")
        if os.path.exists(_icon_svg):
            self.setWindowIcon(QtGui.QIcon(_icon_svg))
        elif os.path.exists(_icon_ico):
            self.setWindowIcon(QtGui.QIcon(_icon_ico))
        self.setWindowTitle(tr['SubtitleExtractorGUI']['Title'] + " v" + VERSION)
        # 创建界面布局
        self._create_layout()
        self._connectSignalToSlot()
        # 좌측 네비게이션(사이드 메뉴) 완전 숨김
        self._hide_navigation_panel()

    # macOS 트래픽 라이트(닫기/최소화/최대화)를 좌측에 배치 (네이티브 macOS 관례)
    # 폭은 트래픽 라이트(78px) + 여유 — 타이틀 라벨이 트래픽 라이트와 겹치지 않게.
    _TITLE_BAR_LEFT_PAD = 92

    def systemTitleBarRect(self, size: QSize) -> QRect:
        return QRect(0, 0 if self.isFullScreen() else 9,
                     self._TITLE_BAR_LEFT_PAD, size.height())

    def _connectSignalToSlot(self):
        config.appRestartSig.connect(self._showRestartTooltip)

    def _showRestartTooltip(self):
        """ show restart tooltip """
        InfoBar.success(
            'Updated successfully',
            'Configuration takes effect after restart',
            duration=5000,
            parent=self
        )

    def _create_layout(self):
        # 메인 페이지만 추가 (고급 설정은 숨김)
        self.homeInterface = HomeInterface(self)
        self.homeInterface.setObjectName("HomeInterface")
        self.addSubInterface(self.homeInterface, FluentIcon.HOME, tr['SubtitleExtractorGUI']['Title'])

    def _hide_navigation_panel(self):
        """좌측 네비게이션 패널을 숨겨 단일 화면처럼 보이게 함."""
        try:
            if getattr(self, "navigationInterface", None) is not None:
                self.navigationInterface.hide()
                self.navigationInterface.setFixedWidth(0)
            self._reposition_title_bar()
        except Exception as e:
            print(f"네비게이션 패널 숨김 실패: {e}")

    def _reposition_title_bar(self):
        """
        FluentWindow 는 navigation 폭(46px) 만큼 titleBar 를 우측으로 옮기는데
        사이드바 숨길 경우 트래픽 라이트(좌측) 와 타이틀이 겹친다 — 직접 더 우측으로.
        """
        try:
            tb = getattr(self, "titleBar", None)
            if tb is None:
                return
            tb.move(self._TITLE_BAR_LEFT_PAD, 0)
            tb.resize(max(self.width() - self._TITLE_BAR_LEFT_PAD, 0),
                      tb.height())
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_title_bar()

    def closeEvent(self, event):
        """程序关闭时保存窗口位置并清理资源"""
        self.save_window_position()
        ProcessManager.instance().terminate_all()
        super().closeEvent(event)

    def _onThemeChangedFinished(self):
        super()._onThemeChangedFinished()

    def save_window_position(self):
        """保存窗口位置到配置文件"""
        # 保存窗口位置和大小
        config.set(config.windowX, self.x())
        config.set(config.windowY, self.y())
        config.set(config.windowW, self.width())
        config.set(config.windowH, self.height())

    def update_progress(self):
        # 定时器轮询更新进度（现在更新到视频滑块上）
        if self.se is not None:
            try:
                pos = min(self.frame_count - 1, int(self.se.progress_total / 100 * self.frame_count))
                if pos != self.video_slider.value():
                    self.video_slider.setValue(pos)
                # 检查是否完成
                if self.se.isFinished:
                    self.processing_finished()
            except Exception as e:
                # 捕获任何异常，防止崩溃
                print(f"更新进度时出错: {str(e)}")

    def load_window_position(self):
        # 尝试读取窗口位置 — sanity check 추가 (너무 좁/넓 또는 화면 밖이면 default 로)
        try:
            x = config.windowX.value
            y = config.windowY.value
            width = config.windowW.value
            height = config.windowH.value

            screen_rect = QtWidgets.QApplication.primaryScreen().availableGeometry()

            def _bad_size(ww, hh):
                if not ww or not hh:
                    return True
                if ww < type(self).MIN_WIDTH or hh < type(self).MIN_HEIGHT:
                    return True
                if ww > type(self).MAX_REASONABLE_WIDTH or hh > type(self).MAX_REASONABLE_HEIGHT:
                    return True
                if ww > screen_rect.width() or hh > screen_rect.height():
                    return True
                return False

            if _bad_size(width, height):
                width = type(self).DEFAULT_WIDTH
                height = type(self).DEFAULT_HEIGHT
                config.set(config.windowW, width)
                config.set(config.windowH, height)
                self.resize(width, height)
                self.center_window()
                return

            if (x is None or y is None or x < 0 or y < 0
                    or x + width > screen_rect.width()
                    or y + height > screen_rect.height()):
                self.resize(width, height)
                self.center_window()
                return

            self.setGeometry(x, y, width, height)
        except Exception as e:
            print(e)
            self.center_window()

    def center_window(self):
        """将窗口居中显示"""
        screen_rect = QtWidgets.QApplication.primaryScreen().availableGeometry()
        window_rect = self.frameGeometry()
        center_point = screen_rect.center()
        window_rect.moveCenter(center_point)
        self.move(window_rect.topLeft())

    def keyPressEvent(self, event):
        """处理键盘事件"""
        # 检测Ctrl+C组合键
        if event.key() == QtCore.Qt.Key_C and event.modifiers() == QtCore.Qt.ControlModifier:
            print("\n程序被用户中断(Ctrl+C)，正在退出...")
            self.close()
        else:
            super().keyPressEvent(event)


if __name__ == '__main__':
    multiprocessing.set_start_method("spawn")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QtWidgets.QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    # 앱 전역 아이콘 (Cmd+Tab 스위처 등에서 사용)
    _app_icon_svg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "design", "icon.svg")
    if os.path.exists(_app_icon_svg):
        app.setWindowIcon(QtGui.QIcon(_app_icon_svg))

    # 메모리 상의 config 객체에도 한 번 더 고정값을 적용 (이중 안전장치)
    _force_fixed_settings()

    window = SubtitleExtractorGUI()
    # 先设置透明, 再显示, 否则会有闪烁的效果
    window.setWindowOpacity(0.0)
    window.show()
    window.load_window_position()
    # 使用动画效果逐渐显示窗口
    animation = QtCore.QPropertyAnimation(window, b"windowOpacity")
    animation.setDuration(300)  # 300毫秒的动画
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.start()
    app.exec()
