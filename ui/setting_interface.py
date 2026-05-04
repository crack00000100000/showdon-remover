from PySide6 import QtWidgets
from qfluentwidgets import (FluentWindow, PushButton, Slider, ProgressBar, PlainTextEdit,
                          setTheme, Theme, FluentIcon, CardWidget, SettingCardGroup,
                          ComboBoxSettingCard, SwitchSettingCard, RangeSettingCard,
                          PushSettingCard, PrimaryPushSettingCard, OptionsSettingCard,
                          FolderListSettingCard, HyperlinkCard, ColorSettingCard, 
                          CustomColorSettingCard)
from backend.config import config, tr, HARDWARD_ACCELERATION_OPTION
from backend.tools.constant import InpaintMode, SubtitleDetectMode

class SettingInterface(QtWidgets.QVBoxLayout):

    def __init__(self, parent):
        super().__init__()
        self.setContentsMargins(16, 16, 16, 16)
        
        # 界面语言设置
        self.interface_combo = ComboBoxSettingCard(
            configItem=config.interface,
            icon=FluentIcon.LANGUAGE,
            title=tr["SubtitleExtractorGUI"]["InterfaceLanguage"],
            content="",
            parent=parent,
            texts=config.intefaceTexts.keys(),
        )
        self.addWidget(self.interface_combo)
        
        # 处理模式设置 — 모델 선택 + 선택 시 카드 본문에 모델별 한 줄 설명 동적 표시
        # GUI 노출 정책: 실용 모델만 (STTN 스마트 / ProPainter / OpenCV).
        # LAMA / STTN 자막감지는 backend 에 남겨두지만 GUI 에서 숨김 — 일반 사용자에게
        # 너무 느리거나 사용처가 좁은 모드라 선택 혼란만 야기.
        # 단순화 — 일상 사용에 STTN 스마트 / OpenCV 두 개만 노출.
        # ProPainter / LAMA / STTN_DET 는 backend enum 유지하되 GUI 에서 숨김.
        _hidden_modes = {InpaintMode.LAMA, InpaintMode.STTN_DET, InpaintMode.PROPAINTER}
        all_options = list(config.inpaintMode.validator.options)
        all_labels = list(tr['InpaintMode'].values())
        all_descs = list(tr['InpaintModeContent'].values())

        # 노출되는 옵션/라벨/설명만 추려냄 (enum 순서와 ini 키 순서 1:1 가정)
        _visible_idx = [i for i, opt in enumerate(all_options) if opt not in _hidden_modes]
        visible_options = [all_options[i] for i in _visible_idx]
        visible_labels = [all_labels[i] for i in _visible_idx]
        self._inpaint_mode_descriptions = [all_descs[i] for i in _visible_idx]
        self._inpaint_mode_options = visible_options
        # 메인 GUI 가 직접 ComboBox 만들 때 라벨 가져갈 수 있게 노출
        # (ComboBoxSettingCard.optionToText 는 zip 미스매치라 신뢰 불가)
        self._inpaint_mode_labels = visible_labels

        # 만약 현재 저장된 설정이 숨김 모드면 첫 노출 옵션(STTN_AUTO)으로 강제 변경
        if config.inpaintMode.value in _hidden_modes and visible_options:
            config.set(config.inpaintMode, visible_options[0])

        self.inpaint_mode_combo = ComboBoxSettingCard(
            configItem=config.inpaintMode,
            icon=FluentIcon.GLOBE,
            title=tr["SubtitleExtractorGUI"]["InpaintMode"],
            content="",
            parent=parent,
            texts=visible_labels,
        )
        self.inpaint_mode_combo.setToolTip(tr["SubtitleExtractorGUI"]["InpaintModeDesc"])

        # ComboBoxSettingCard 가 내부적으로 zip(texts=visible_labels, options=all_options)
        # 으로 itemData 등록 — texts 가 3개라 자동으로 3개만 등록됨. 별도 removeItem 불필요.
        # (이전 라운드에선 추가 removeItem 이 또 빼서 1개로 줄어드는 버그 있었음 → 제거)

        # 선택 변경 시 카드 본문 갱신
        self.inpaint_mode_combo.comboBox.currentIndexChanged.connect(
            self._on_inpaint_mode_changed
        )
        # 초기 진입 시 현재 선택 값에 맞는 설명 한 번 적용
        self._on_inpaint_mode_changed(
            self.inpaint_mode_combo.comboBox.currentIndex()
        )

        self.addWidget(self.inpaint_mode_combo)

        # STTN 마스크 dilation 슬라이더 — 외곽선 자막 보정용
        self.sttn_mask_dilation_card = RangeSettingCard(
            configItem=config.sttnMaskDilation,
            icon=FluentIcon.ZOOM,
            title=tr["SubtitleExtractorGUI"]["SttnMaskDilation"],
            content=tr["SubtitleExtractorGUI"]["SttnMaskDilationDesc"],
            parent=parent,
        )
        self.addWidget(self.sttn_mask_dilation_card)

        # 사용자 영역 강제 마스크 (영구 자막 / OCR 누락 프레임 회피)
        self.force_mask_card = SwitchSettingCard(
            configItem=config.subtitleAreaForceMask,
            icon=FluentIcon.VIEW,
            title=tr["SubtitleExtractorGUI"]["SubtitleAreaForceMask"],
            content=tr["SubtitleExtractorGUI"]["SubtitleAreaForceMaskDesc"],
            parent=parent,
        )
        self.addWidget(self.force_mask_card)

        self.subtitle_detect_model_combo = ComboBoxSettingCard(
            configItem=config.subtitleDetectMode,
            icon=FluentIcon.SEARCH,
            title=tr["SubtitleExtractorGUI"]["SubtitleDetectMode"],
            content="",
            parent=parent,
            texts=[list(tr['SubtitleDetectMode'].values())[i] for i,_ in enumerate(config.subtitleDetectMode.validator.options)],
        )
        self.addWidget(self.subtitle_detect_model_combo)

        # 是否启用硬件加速
        self.hardware_acceleration = SwitchSettingCard(
            configItem=config.hardwareAcceleration,
            icon=FluentIcon.SPEED_HIGH, 
            title=tr["Setting"]["HardwareAcceleration"],
            content=tr["Setting"]["HardwareAccelerationDesc"],
            parent=parent
        )
        self.addWidget(self.hardware_acceleration)
        # 如果硬件加速选项被禁用, 设置硬件加速为False并只读
        if not HARDWARD_ACCELERATION_OPTION:
            self.hardware_acceleration.switchButton.setChecked(False)
            self.hardware_acceleration.switchButton.setEnabled(False)
            self.hardware_acceleration.setContent(tr["Setting"]["HardwareAccelerationNO"])
            config.set(config.hardwareAcceleration, False)
        # 添加一些空间
        self.addStretch(1)
    
    def set_inpaint_mode_enabled(self, enabled):
        """启用或禁用 inpaint 模式下拉框"""
        self.inpaint_mode_combo.comboBox.setEnabled(enabled)

    def _on_inpaint_mode_changed(self, index: int):
        """모드 선택 시 카드 본문에 모델별 한 줄 설명 갱신."""
        try:
            if 0 <= index < len(self._inpaint_mode_descriptions):
                self.inpaint_mode_combo.setContent(
                    self._inpaint_mode_descriptions[index]
                )
        except Exception:
            pass

    def reset_setting(self):
        """重置所有设置为默认值"""
        # 这里需要实现重置逻辑
        pass