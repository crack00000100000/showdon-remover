import os
import cv2
import threading
import multiprocessing
import time
import traceback
import subprocess
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFileDialog
from PySide6.QtCore import Slot, QRect, Signal, Qt
from PySide6 import QtWidgets
from datetime import datetime
from qfluentwidgets import (PushButton, CardWidget, TextEdit, FluentIcon,
                            PushSettingCard, BodyLabel, StrongBodyLabel,
                            ComboBox)
from ui.setting_interface import SettingInterface
from ui.component.video_display_component import VideoDisplayComponent
from ui.component.task_list_component import TaskListComponent, TaskStatus, TaskOptions
from ui.icon.my_fluent_icon import MyFluentIcon
from backend.config import config, tr
from backend.tools.constant import InpaintMode
from backend.tools.subtitle_remover_remote_call import SubtitleRemoverRemoteCall
from backend.tools.process_manager import ProcessManager
from backend.tools.common_tools import get_readable_path, is_image_file, read_image

class HomeInterface(QWidget):
    progress_signal = Signal(int, bool)
    append_log_signal = Signal(list)
    update_preview_with_comp_signal = Signal(list)
    task_error_signal = Signal(object)
    toggle_buttons_signal = Signal(bool)  # True=显示运行按钮, False=显示停止按钮
    task_status_signal = Signal(int, object)  # (task_index, TaskStatus)
    select_task_signal = Signal(int)  # task_index
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("HomeInterface")
        # 初始化一些变量
        self.video_path = None
        self.video_cap = None
        self.fps = None
        self.frame_count = None
        self.frame_width = None
        self.frame_height = None
        self.se = None  # 后台字幕提取器

        # 字幕区域参数
        self.xmin = None
        self.xmax = None
        self.ymin = None
        self.ymax = None

        # 添加自动滚动控制标志
        self.auto_scroll = True
        self._stop_event = threading.Event()  # 线程安全的停止信号
        self._worker_thread = None
        self.running_process = None
        self._saved_inpaint_mode = None  # 保存图片锁定前的 inpaint 模式
        self._video_cap_lock = threading.Lock()  # 保护 video_cap 的线程锁

        # 当前正在处理的任务索引
        self.current_processing_task_index = -1

        self.__init_widgets()
        self.progress_signal.connect(self.update_progress)
        self.append_log_signal.connect(self.append_log)
        self.update_preview_with_comp_signal.connect(self.update_preview_with_comp)
        self.task_error_signal.connect(self.on_task_error)
        self.toggle_buttons_signal.connect(self._toggle_buttons)
        self.task_status_signal.connect(lambda idx, status: self.task_list_component.update_task_status(idx, status))
        self.select_task_signal.connect(self.task_list_component.select_task)

    def __init_widgets(self):
        """创建主页面"""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 左侧视频区域
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)
        
        # 创建视频显示组件
        self.video_display_component = VideoDisplayComponent(self)
        self.video_display_component.ab_sections_changed.connect(self.ab_sections_changed)
        self.video_display_component.selections_changed.connect(self.selections_changed)
        left_layout.addWidget(self.video_display_component)
        
        # 获取视频显示和滑块的引用
        self.video_display = self.video_display_component.video_display
        self.video_slider = self.video_display_component.video_slider
        self.video_slider.valueChanged.connect(self.slider_changed)
        
        # 输出文本区域
        self.output_text = TextEdit()
        self.output_text.setMinimumHeight(150)
        self.output_text.setReadOnly(True)
        self.output_text.document().setDocumentMargin(10)        
        # 连接滚动条值变化信号
        self.output_text.verticalScrollBar().valueChanged.connect(self.on_scroll_change)
        
        output_container = CardWidget(self)
        output_layout = QVBoxLayout()
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self.output_text)
        output_container.setLayout(output_layout)
        left_layout.addWidget(output_container)

        # 좌측 영상 영역 — stretch=1 로 가용 폭 흡수
        main_layout.addLayout(left_layout, 1)

        # 右侧设置区域 — 콘텐츠(슬라이더 숫자 등)가 변해도 좌측이 안 흔들리게
        # 우측 컨테이너 자체에 고정 폭(min/max) 부여.
        right_widget = QWidget(self)
        right_widget.setMinimumWidth(420)
        right_widget.setMaximumWidth(540)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 설정 컨테이너는 생성하지만 숨김 — SettingInterface 객체는 이미지 모드에서
        # inpaint 모델 락 처리에 사용되므로 인스턴스만 살려둠.
        settings_container = CardWidget(self)
        self.setting_interface = SettingInterface(settings_container)
        settings_container.setLayout(self.setting_interface)
        settings_container.setVisible(False)

        # === 1) 저장 폴더 카드 (맨 위) — 경로 + [폴더 선택]/[열기] ===
        save_folder_card = CardWidget(self)
        save_inner = QVBoxLayout(save_folder_card)
        save_inner.setContentsMargins(16, 14, 16, 14)
        save_inner.setSpacing(8)
        save_inner.addWidget(StrongBodyLabel(tr["Setting"]["SaveDirectory"]))
        self.save_path_label = BodyLabel(self._readable_save_path(), save_folder_card)
        self.save_path_label.setStyleSheet("color: #555; font-size: 12px;")
        self.save_path_label.setWordWrap(True)
        save_inner.addWidget(self.save_path_label)
        save_btn_row = QHBoxLayout()
        save_btn_row.setSpacing(8)
        self.choose_folder_btn = PushButton(tr["Setting"]["ChooseDirectory"], save_folder_card)
        self.choose_folder_btn.setIcon(FluentIcon.FOLDER)
        self.choose_folder_btn.clicked.connect(self._on_choose_save_folder)
        save_btn_row.addWidget(self.choose_folder_btn, 1)
        self.open_folder_btn = PushButton("열기", save_folder_card)
        self.open_folder_btn.setIcon(FluentIcon.SHARE)
        self.open_folder_btn.clicked.connect(self._open_save_folder_in_finder)
        save_btn_row.addWidget(self.open_folder_btn, 1)
        save_inner.addLayout(save_btn_row)
        right_layout.addWidget(save_folder_card)

        # === 2) 처리 모델 카드 (세로형) ===
        # ComboBoxSettingCard 의 내부 ComboBox 를 reparent 하면 zip(texts, options)
        # 미스매치로 라벨↔옵션 어긋남 (라벨 ProPainter 인데 itemData 가 STTN_DET 등).
        # 우회: 메인 GUI 에서 직접 ComboBox 만들고 visible_options 1:1 정확히 등록.
        inpaint_card = CardWidget(self)
        inpaint_inner = QVBoxLayout(inpaint_card)
        inpaint_inner.setContentsMargins(16, 14, 16, 14)
        inpaint_inner.setSpacing(6)
        inpaint_inner.addWidget(StrongBodyLabel(tr["SubtitleExtractorGUI"]["InpaintMode"]))
        self.inpaint_desc_label = BodyLabel("")
        # line-height 살짝 늘려 줄바꿈 가독성 ↑
        self.inpaint_desc_label.setStyleSheet(
            "color: #555; font-size: 11px; line-height: 1.5;"
        )
        self.inpaint_desc_label.setWordWrap(True)
        inpaint_inner.addWidget(self.inpaint_desc_label)

        # 직접 ComboBox 생성 — SettingInterface 가 보존한 visible_labels/options 사용
        # (ComboBoxSettingCard.optionToText 는 zip 미스매치로 신뢰 불가)
        _v_opts = list(getattr(self.setting_interface, "_inpaint_mode_options", []))
        _v_labels = list(getattr(self.setting_interface, "_inpaint_mode_labels", []))
        _v_descs = list(getattr(self.setting_interface, "_inpaint_mode_descriptions", []))

        self.inpaint_combo = ComboBox(inpaint_card)
        for label, opt in zip(_v_labels, _v_opts):
            self.inpaint_combo.addItem(label, userData=opt)

        # 현재 config 값 → 인덱스 반영
        _current_mode = config.inpaintMode.value
        _idx = next((i for i, opt in enumerate(_v_opts) if opt == _current_mode), 0)
        self.inpaint_combo.setCurrentIndex(_idx)

        def _on_inpaint_changed(idx: int):
            if 0 <= idx < self.inpaint_combo.count():
                _opt = self.inpaint_combo.itemData(idx)
                config.set(config.inpaintMode, _opt)

                # 모델별 자동 기본 설정 — 사용자가 다른 옵션 안 만져도 적정값으로
                from backend.tools.constant import (
                    InpaintMode as _IM, SubtitleDetectMode as _DM,
                )
                if _opt == _IM.STTN_AUTO:
                    # STTN 스마트: 외곽선 두께 보정 자동 (10px), OCR 정밀
                    config.set(config.sttnMaskDilation, 10)
                    config.set(config.subtitleAreaForceMask, False)
                    config.set(config.subtitleDetectMode, _DM.PP_OCRv5_SERVER)
                elif _opt == _IM.OPENCV:
                    # OpenCV: 강제 마스크 OFF + 빠른 OCR (속도 우선)
                    config.set(config.subtitleAreaForceMask, False)
                    config.set(config.subtitleDetectMode, _DM.PP_OCRv5_MOBILE)

                try:
                    from qfluentwidgets import qconfig
                    qconfig.save()
                except Exception:
                    pass
                if 0 <= idx < len(_v_descs):
                    # \\n → 실제 줄바꿈 (ko.ini 의 escape sequence 처리)
                    self.inpaint_desc_label.setText(_v_descs[idx].replace("\\n", "\n"))
        self.inpaint_combo.currentIndexChanged.connect(_on_inpaint_changed)
        _on_inpaint_changed(_idx)   # 초기 description

        inpaint_inner.addWidget(self.inpaint_combo)
        right_layout.addWidget(inpaint_card)

        # 외곽선 두께 슬라이더 / 강제마스크 토글 / OCR 모드 ComboBox 는 메인 GUI 노출 X.
        # 모델 선택 시 _on_inpaint_changed 가 자동으로 적정 기본값 set:
        #  - STTN 스마트: 외곽선 두께 10, OCR 정밀
        #  - OpenCV: 강제마스크 OFF, OCR 빠른

        # 添加任务列表容器
        task_list_container = CardWidget(self)
        task_list_layout = QHBoxLayout()
        task_list_layout.setContentsMargins(0, 0, 0, 0)
        task_list_layout.setSpacing(0)
        self.task_list_component = TaskListComponent(self)
        self.task_list_component.task_selected.connect(self.on_task_selected)
        self.task_list_component.task_deleted.connect(self.on_task_deleted)
        task_list_layout.addWidget(self.task_list_component)
        task_list_container.setLayout(task_list_layout)
        right_layout.addWidget(task_list_container, 1)  # 占满剩余空间
        
        # 操作按钮容器
        button_container = CardWidget(self)
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(16, 16, 16, 16)
        button_layout.setSpacing(8)
        
        self.file_button = PushButton(tr['SubtitleExtractorGUI']['Open'], self)
        self.file_button.setIcon(FluentIcon.FOLDER)
        self.file_button.clicked.connect(self.open_file)
        button_layout.addWidget(self.file_button)
        
        self.run_button = PushButton(tr['SubtitleExtractorGUI']['Run'], self)
        self.run_button.setIcon(FluentIcon.PLAY)
        self.run_button.clicked.connect(self.run_button_clicked)
        button_layout.addWidget(self.run_button)
        
        self.stop_button = PushButton(tr['SubtitleExtractorGUI']['Stop'], self)
        self.stop_button.setIcon(MyFluentIcon.Stop)
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_button_clicked)
        
        button_layout.addWidget(self.stop_button)
        
        button_container.setLayout(button_layout)
        right_layout.addWidget(button_container)

        # right_widget 은 고정 폭 — stretch=0 으로 자연 폭 유지
        main_layout.addWidget(right_widget, 0)
    
    def on_scroll_change(self, value):
        """监控滚动条位置变化"""
        scrollbar = self.output_text.verticalScrollBar()
        # 如果滚动到底部，启用自动滚动
        if value == scrollbar.maximum():
            self.auto_scroll = True
        # 如果用户向上滚动，禁用自动滚动
        elif self.auto_scroll and value < scrollbar.maximum():
            self.auto_scroll = False

    
    def slider_changed(self, value):
        frame = None
        with self._video_cap_lock:
            if self.video_cap is not None and self.video_cap.isOpened():
                frame_no = self.video_slider.value()
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
                ret, frame = self.video_cap.read()
                if not ret:
                    frame = None
        if frame is not None:
            # 更新预览图像
            self.update_preview(frame)

    def ab_sections_changed(self, ab_sections):
        get_current_task_index = self.task_list_component.get_current_task_index()
        if get_current_task_index == -1:
            return
        self.task_list_component.update_task_option(get_current_task_index, TaskOptions.AB_SECTIONS, ab_sections)

    def selections_changed(self, selections):
        get_current_task_index = self.task_list_component.get_current_task_index()
        if get_current_task_index == -1:
            return
        self.task_list_component.update_task_option(get_current_task_index, TaskOptions.SUB_AREAS, selections)

    def on_task_selected(self, index, file_path):
        """处理任务被选中事件
        
        Args:
            index: 任务索引
            file_path: 文件路径
        """
        # 加载选中的视频进行预览
        self.load_video(file_path)
        ab_sections = self.task_list_component.get_task_option(index, TaskOptions.AB_SECTIONS, [])
        self.video_display_component.set_ab_sections(ab_sections)
        selections = self.task_list_component.get_task_option(index, TaskOptions.SUB_AREAS, [])
        if len(selections) <= 0:
            self.video_display_component.load_selections_from_config()
        else:
            self.video_display_component.set_selection_rects(selections)
    
    def on_task_deleted(self, index):
        """处理任务被删除事件
        
        Args:
            index: 任务索引
        """
        # 如果删除的是正在处理的任务，则需要更新状态
        if index == self.current_processing_task_index:
            self.current_processing_task_index = -1
        
        task = self.task_list_component.get_task(0)
        if task:
            # 如果还有任务，选中第一个
            self.task_list_component.select_task(0)

    def update_preview(self, frame):
        # 先缩放图像
        resized_frame = self._img_resize(frame)

        # 设置视频参数
        self.video_display_component.set_video_parameters(
            self.frame_width, self.frame_height, 
            self.scaled_width if hasattr(self, 'scaled_width') else None,
            self.scaled_height if hasattr(self, 'scaled_height') else None,
            self.border_left if hasattr(self, 'border_left') else 0,
            self.border_top if hasattr(self, 'border_top') else 0,
            self.fps if self.fps is not None else 30,
        )
        
        # 更新视频显示（这会同时保存current_pixmap）
        self.video_display_component.update_video_display(resized_frame)

    def _img_resize(self, image):
        height, width = image.shape[:2]
        
        video_preview_width = self.video_display_component.video_preview_width
        video_preview_height = self.video_display_component.video_preview_height
        # 计算等比缩放后的尺寸
        target_ratio = video_preview_width / video_preview_height
        image_ratio = width / height
        
        if image_ratio > target_ratio:
            # 宽度适配，高度按比例缩放
            new_width = video_preview_width
            new_height = int(new_width / image_ratio)
            top_border = (video_preview_height - new_height) // 2
            bottom_border = video_preview_height - new_height - top_border
            left_border = 0
            right_border = 0
        else:
            # 高度适配，宽度按比例缩放
            new_height = video_preview_height
            new_width = int(new_height * image_ratio)
            left_border = (video_preview_width - new_width) // 2
            right_border = video_preview_width - new_width - left_border
            top_border = 0
            bottom_border = 0
        
        # 先缩放图像
        resized = cv2.resize(image, (new_width, new_height))
        
        # 添加黑边以填充到目标尺寸
        padded = cv2.copyMakeBorder(
            resized, 
            top_border, bottom_border, 
            left_border, right_border, 
            cv2.BORDER_CONSTANT, 
            value=[0, 0, 0]
        )
        
        # 保存边框信息，用于坐标转换
        self.border_left = left_border / video_preview_width
        self.border_right = right_border / video_preview_width
        self.border_top = top_border / video_preview_height
        self.border_bottom = bottom_border / video_preview_height
        self.original_width = width
        self.original_height = height
        self.is_vertical = width < height
        self.scaled_width = new_width / video_preview_width
        self.scaled_height = new_height / video_preview_height
        
        return padded

    def stop_button_clicked(self):
        try:
            self._stop_event.set()
            running_process = self.running_process
            if running_process:
                ProcessManager.instance().terminate_by_process(running_process)
            # 更新任务状态为待处理
            if self.current_processing_task_index >= 0:
                self.task_list_component.update_task_status(self.current_processing_task_index, TaskStatus.PENDING)
        finally:
            self.running_process = None
            self.run_button.setVisible(True)
            self.stop_button.setVisible(False)

    @Slot(bool)
    def _toggle_buttons(self, show_run):
        """线程安全地切换按钮可见性"""
        self.run_button.setVisible(show_run)
        self.stop_button.setVisible(not show_run)

    def run_button_clicked(self):
        # 자식 프로세스가 config.json 을 새로 로드하므로 spawn 직전 강제 저장 보장
        try:
            from qfluentwidgets import qconfig
            qconfig.save()
        except Exception:
            pass
        if not self.task_list_component.get_pending_tasks():
            self.append_output(tr['SubtitleExtractorGUI']['OpenVideoFirst'])
            return

        try:
            # 获取所有待执行的任务
            pending_tasks = self.task_list_component.get_pending_tasks()
            if not pending_tasks:
                return

            self._stop_event.clear()
            self.toggle_buttons_signal.emit(False)
            # 开启后台线程处理视频
            def task():
                try:
                    while not self._stop_event.is_set():
                        try:
                            pending_tasks = self.task_list_component.get_pending_tasks()
                            if not pending_tasks:
                                break
                            pending_task = pending_tasks[0]
                            # 更新当前处理的任务索引
                            self.current_processing_task_index, task_item = pending_task
                            if not self.load_video(task_item.path):
                                self.append_log_signal.emit([tr['SubtitleExtractorGUI']['OpenVideoFailed'].format(task_item.path)])
                                self.task_status_signal.emit(self.current_processing_task_index, TaskStatus.FAILED)
                                continue

                            # 获取字幕区域坐标，未选择则使用全屏
                            subtitle_areas = self.task_list_component.get_task_option(self.current_processing_task_index, TaskOptions.SUB_AREAS, [])
                            if not subtitle_areas or len(subtitle_areas) <= 0:
                                subtitle_areas = [(0, self.frame_height, 0, self.frame_width)]
                                self.task_list_component.update_task_option(self.current_processing_task_index, TaskOptions.SUB_AREAS, subtitle_areas)

                            self.video_display_component.save_selections_to_config()

                            # 更新任务状态为运行中
                            self.task_list_component.update_task_progress(self.current_processing_task_index, 1)

                            # 选中当前任务
                            self.select_task_signal.emit(self.current_processing_task_index)

                            with self._video_cap_lock:
                                if self.video_cap:
                                    self.video_cap.release()
                                    self.video_cap = None

                            self.task_status_signal.emit(self.current_processing_task_index, TaskStatus.PROCESSING)
                            options = {}
                            for key in task_item.options:
                                value = task_item.options[key]
                                if key == TaskOptions.SUB_AREAS.value:
                                    value = self.video_display_component.preview_coordinates_to_video_coordinates(value)
                                options[key] = value
                            # config 의 inpaint 관련 값들을 자식 프로세스에 명시 전달
                            # — config.json 디스크 race 회피 (qconfig.save 로도 spawn race 발생)
                            options["__inpaint_mode__"] = config.inpaintMode.value
                            options["__sttn_mask_dilation__"] = int(config.sttnMaskDilation.value)
                            options["__force_mask__"] = bool(config.subtitleAreaForceMask.value)
                            options["__detect_mode__"] = config.subtitleDetectMode.value
                            # 清理缓存, 使用动态路径
                            task_item.output_path = None
                            output_path = task_item.output_path
                            process = self.run_subtitle_remover_process(task_item.path, output_path, options)

                            # 检查是否在处理过程中被停止
                            if self._stop_event.is_set():
                                break

                            # 更新任务状态为已完成
                            task_obj = self.task_list_component.get_task(self.current_processing_task_index)
                            if process.exitcode == 0 and task_obj and task_obj.status == TaskStatus.PROCESSING:
                                self.progress_signal.emit(100, True)
                                # 任务完成, 更新输出路径为只读
                                task_obj.output_path = output_path
                                self.task_status_signal.emit(self.current_processing_task_index, TaskStatus.COMPLETED)
                            else:
                                self.task_status_signal.emit(self.current_processing_task_index, TaskStatus.FAILED)

                        except Exception as e:
                            print(e)
                            self.append_log_signal.emit([f"Error: {e}"])
                            # 更新任务状态为失败
                            if self.current_processing_task_index >= 0:
                                self.task_status_signal.emit(self.current_processing_task_index, TaskStatus.FAILED)
                            break
                        finally:
                            with self._video_cap_lock:
                                if self.video_cap:
                                    self.video_cap.release()
                                    self.video_cap = None
                            time.sleep(1)
                finally:
                    self.toggle_buttons_signal.emit(True)

            self._worker_thread = threading.Thread(target=task, daemon=True)
            self._worker_thread.start()
        except Exception as e:
            print(traceback.format_exc())
            self.append_log_signal.emit([f"Error: {e}"])
            self.toggle_buttons_signal.emit(True)

    @staticmethod
    def remover_process(queue, video_path, output_path, options):
        """
        在子进程中执行字幕提取的函数
        
        Args:
            video_path: 视频文件路径
            output_path: 输出文件路径
            options: 选项
        """
        sr = None
        try:
            from backend.main import SubtitleRemover
            from backend.config import config as _child_config
            from backend.tools.constant import InpaintMode as _ChildInpaintMode

            # 자식 프로세스 config 강제 갱신 — 메인의 ComboBox 선택을 명시 인자로 전달받음
            _im = options.pop("__inpaint_mode__", None)
            _md = options.pop("__sttn_mask_dilation__", None)
            _fm = options.pop("__force_mask__", None)
            _dm = options.pop("__detect_mode__", None)
            if _im is not None:
                if isinstance(_im, str):
                    _name = _im.split(".")[-1]
                    _im = getattr(_ChildInpaintMode, _name, _im)
                _child_config.set(_child_config.inpaintMode, _im)
            if _md is not None:
                _child_config.set(_child_config.sttnMaskDilation, int(_md))
            if _fm is not None:
                _child_config.set(_child_config.subtitleAreaForceMask, bool(_fm))
            if _dm is not None:
                from backend.tools.constant import SubtitleDetectMode as _ChildDetectMode
                if isinstance(_dm, str):
                    _name = _dm.split(".")[-1]
                    _dm = getattr(_ChildDetectMode, _name, _dm)
                _child_config.set(_child_config.subtitleDetectMode, _dm)
            sr = SubtitleRemover(video_path, True)
            sr.video_out_path = output_path
            for key in options:
                setattr(sr, key, options[key])
            sr.add_progress_listener(lambda progress, isFinished: SubtitleRemoverRemoteCall.remote_call_update_progress(queue, progress, isFinished))
            sr.append_output = lambda *args: SubtitleRemoverRemoteCall.remote_call_append_log(queue, args)
            sr.manage_process = lambda pid: SubtitleRemoverRemoteCall.remote_call_manage_process(queue, pid)
            sr.update_preview_with_comp = lambda *args: SubtitleRemoverRemoteCall.remote_call_update_preview_with_comp(queue, args)
            sr.run()
        except Exception as e:
            traceback.print_exc()
            SubtitleRemoverRemoteCall.remote_call_catch_error(queue, e)
        finally:
            if sr:
                sr.isFinished = True
                sr.vsf_running = False
            SubtitleRemoverRemoteCall.remote_call_finish(queue)
            

    # 修改run_subtitle_remover_process方法
    def run_subtitle_remover_process(self, video_path, output_path, options):
        """
        使用多进程执行字幕提取，并等待进程完成
        
        Args:
            video_path: 视频文件路径
            output_path: 输出文件路径
            options: 任务选项
        """
        subtitle_remover_remote_caller = SubtitleRemoverRemoteCall()
        subtitle_remover_remote_caller.register_update_progress_callback(self.progress_signal.emit)
        subtitle_remover_remote_caller.register_log_callback(self.append_log_signal.emit)
        subtitle_remover_remote_caller.register_update_preview_with_comp_callback(self.update_preview_with_comp_signal.emit)
        subtitle_remover_remote_caller.register_error_callback(self.task_error_signal.emit)
        process = multiprocessing.Process(
            target=HomeInterface.remover_process,
            args=(subtitle_remover_remote_caller.queue, video_path, output_path, options)
        )
        try:
            if self._stop_event.is_set():
                return process
            process.start()
            ProcessManager.instance().add_process(process)
            self.running_process = process
            process.join()
            print(f"Process exited with code {process.exitcode}")
        finally:
            subtitle_remover_remote_caller.stop()
        return process

    @Slot()
    def processing_finished(self):
        pending_tasks = self.task_list_component.get_pending_tasks()
        if pending_tasks:
            # 还有待执行任务, 忽略
            return
        # 处理完成后恢复界面可用性
        self.run_button.setVisible(True)
        self.stop_button.setVisible(False)
        self.se = None
        # 重置视频滑块
        self.video_slider.setValue(1)
        # 重置当前处理任务索引
        self.current_processing_task_index = -1

    @Slot(int, bool)
    def update_progress(self, progress_total, isFinished):
        try:
            pos = min(self.frame_count - 1, int(progress_total / 100 * self.frame_count))
            if pos != self.video_slider.value():
                self.video_slider.blockSignals(True)
                self.video_slider.setValue(pos)
                self.video_slider.blockSignals(False)
            
            # 更新任务进度
            if self.current_processing_task_index >= 0:
                self.task_list_component.update_task_progress(
                    self.current_processing_task_index, 
                    progress_total,
                )
            
            # 检查是否完成
            if isFinished:
                self.processing_finished()
        except Exception as e:
            # 捕获任何异常，防止崩溃
            print(f"更新进度时出错: {str(e)}")

    @Slot(list)
    def append_log(self, log):
        self.append_output(*log)

    def append_output(self, *args):
        """添加文本到输出区域并控制滚动
        Args:
            *args: 要输出的内容，多个参数将用空格连接
        """
        # 将所有参数转换为字符串并用空格连接
        text = ' '.join(str(arg) for arg in args).rstrip()
        timestamp = datetime.now().strftime('%H:%M:%S')
        # 转义HTML特殊字符
        escaped = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        # 根据内容判断消息类型并着色
        if '错误' in text or 'Error' in text or '失败' in text or 'Failed' in text:
            color = '#e74c3c'
        elif '成功' in text or '完成' in text or 'Success' in text or 'Finished' in text:
            color = '#27ae60'
        elif '警告' in text or 'Warning' in text:
            color = '#f39c12'
        else:
            color = '#2980b9'
        html = f'<span style="color:#888;">[{timestamp}]</span> <span style="color:{color};">{escaped}</span><br>'
        self.output_text.append(html)
        print(*args)  # 保持原始的 print 行为
        # 如果启用了自动滚动，则滚动到底部
        if self.auto_scroll:
            scrollbar = self.output_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    @Slot(list)
    def update_preview_with_comp(self, args):
        """更新执行时预览"""
        frame_ori, frame_comp = args
        if self.current_processing_task_index >= 0:
            subtitle_areas = self.task_list_component.get_task_option(self.current_processing_task_index, TaskOptions.SUB_AREAS, [])
            if len(subtitle_areas) > 0:
                subtitle_areas = self.video_display_component.preview_coordinates_to_video_coordinates(subtitle_areas)
                if frame_ori is frame_comp:
                    frame_ori = frame_ori.copy()
                for rect in subtitle_areas:
                    ymin, ymax, xmin, xmax = rect
                    cv2.rectangle(frame_ori, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
        preview_frame = cv2.hconcat([frame_ori, frame_comp])
        # 先缩放图像
        resized_frame = self._img_resize(preview_frame)
        # 更新视频显示（这会同时保存current_pixmap）
        self.video_display_component.update_video_display(resized_frame, draw_selection=False)
        self.video_display_component.set_dragger_enabled(False)

    @Slot(object)
    def on_task_error(self, e):
        self.append_output(tr['SubtitleExtractorGUI']['ErrorDuringProcessing'].format(str(e)))
        if self.current_processing_task_index >= 0:
            self.task_list_component.update_task_status(self.current_processing_task_index, TaskStatus.FAILED)

    def load_video(self, video_path):
        self.video_path = video_path
        with self._video_cap_lock:
            if self.video_cap:
                self.video_cap.release()
                self.video_cap = None
        # 如果是图片文件，直接走图片加载路径
        if is_image_file(video_path):
            return self.load_as_picture(video_path)
        with self._video_cap_lock:
            self.video_cap = cv2.VideoCapture(get_readable_path(self.video_path))
            if not self.video_cap.isOpened():
                self.video_cap = None
                return self.load_as_picture(video_path)
            ret, frame = self.video_cap.read()
            if not ret:
                self.video_cap.release()
                self.video_cap = None
                return self.load_as_picture(video_path)
            self.frame_count = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.frame_height = int(self.video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.frame_width = int(self.video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.fps = self.video_cap.get(cv2.CAP_PROP_FPS)

        self.update_preview(frame)
        self.video_slider.setMaximum(self.frame_count)
        self.video_slider.setValue(1)
        self.video_display_component.set_dragger_enabled(True)
        # 视频模式下恢复用户原始的 inpaint 模式选择
        self._unlock_inpaint_mode()
        return True

    def load_as_picture(self, path):
        if not is_image_file(path):
            return False
        self.video_path = path
        self.video_cap = None
        frame = read_image(get_readable_path(path))
        if frame is None:
            return False
        self.frame_count = 1
        self.frame_height = frame.shape[0]
        self.frame_width = frame.shape[1]
        self.fps = 1
        self.update_preview(frame)
        self.video_slider.setMaximum(self.frame_count)
        self.video_slider.setValue(1)
        self.video_display_component.set_dragger_enabled(True)
        # 图片模式锁定为 LAMA
        self._lock_inpaint_mode_to_lama()
        return True

    def _lock_inpaint_mode_to_lama(self):
        """图片模式锁定 inpaint 模式为 LAMA"""
        if self._saved_inpaint_mode is None:
            self._saved_inpaint_mode = config.inpaintMode.value
        config.set(config.inpaintMode, InpaintMode.LAMA)
        self.setting_interface.set_inpaint_mode_enabled(False)
        # 메인 GUI 의 새 ComboBox 도 disable (이미지 모드)
        if hasattr(self, "inpaint_combo"):
            self.inpaint_combo.setEnabled(False)

    def _unlock_inpaint_mode(self):
        """视频模式恢复用户原始的 inpaint 模式选择"""
        if self._saved_inpaint_mode is not None:
            config.set(config.inpaintMode, self._saved_inpaint_mode)
            self._saved_inpaint_mode = None
        self.setting_interface.set_inpaint_mode_enabled(True)
        # 메인 GUI 의 새 ComboBox enable + 현재 config 값으로 인덱스 동기화
        if hasattr(self, "inpaint_combo"):
            self.inpaint_combo.setEnabled(True)
            _v_opts = list(getattr(self.setting_interface, "_inpaint_mode_options", []))
            _idx = next((i for i, opt in enumerate(_v_opts)
                         if opt == config.inpaintMode.value), 0)
            self.inpaint_combo.blockSignals(True)
            self.inpaint_combo.setCurrentIndex(_idx)
            self.inpaint_combo.blockSignals(False)
        self.video_slider.setValue(1)
        self.video_display_component.set_dragger_enabled(True)
        return True


    def open_file(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            tr['SubtitleExtractorGUI']['Open'],
            "",
            "All Files (*.*);;Video Files (*.mp4 *.flv *.wmv *.avi *.mkv *.mov);;Image Files (*.jpg *.jpeg *.png *.bmp *.webp *.tiff)"
        )
        if files:
            # 새 영상을 열 때 — 옛 PENDING / FAILED / COMPLETED task 자동 정리.
            # (이전에 중지한 작업이 PENDING 으로 살아있어 새 영상 대신 옛 작업이
            # 다시 실행되던 이슈 회피. 진행 중 PROCESSING task 는 보호.)
            self._clear_idle_tasks()

            files_loaded = []
            # 倒序打开, 确保第一个视频截图显示在屏幕上
            for path in reversed(files):
                if self.load_video(path):
                    self.append_output(f"{tr['SubtitleExtractorGUI']['OpenVideoSuccess']}: {path}")
                    files_loaded.append(path)
                else:
                    self.append_output(f"{tr['SubtitleExtractorGUI']['OpenVideoFailed']}: {path}")
            # 正序添加, 确保任务列表顺序一致
            for path in reversed(files_loaded):
                # 添加到任务列表
                self.task_list_component.add_task(path)
                index = max(0, self.task_list_component.find_task_index_by_path(path))
                self.task_list_component.select_task(index)

    def _clear_idle_tasks(self):
        """진행 중이 아닌 task (PENDING / FAILED / COMPLETED) 를 모두 정리.

        새 영상 열 때 호출. 이전에 중지한 PENDING task 가 살아남아 새 영상 대신
        먼저 처리되던 이슈 회피.
        """
        try:
            tasks = list(self.task_list_component.get_all_tasks()) \
                if hasattr(self.task_list_component, "get_all_tasks") \
                else list(self.task_list_component.tasks)
        except Exception:
            return
        # 뒤에서부터 제거 (인덱스 시프트 방지)
        for i in range(len(tasks) - 1, -1, -1):
            t = tasks[i]
            if t.status != TaskStatus.PROCESSING:
                try:
                    self.task_list_component.delete_task(i)
                except Exception:
                    pass

    def closeEvent(self, event):
        """窗口关闭时断开信号连接并清理资源"""
        try:
            # 通知 worker 线程停止
            self._stop_event.set()
            # 终止子进程
            ProcessManager.instance().terminate_all()
            # 等待 worker 线程结束（最多5秒）
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=5)

            # 断开信号连接
            self.progress_signal.disconnect(self.update_progress)
            self.append_log_signal.disconnect(self.append_log)
            self.update_preview_with_comp_signal.disconnect(self.update_preview_with_comp)
            self.task_error_signal.disconnect(self.on_task_error)
            self.toggle_buttons_signal.disconnect(self._toggle_buttons)
            self.video_display_component.video_slider.valueChanged.disconnect(self.slider_changed)
            self.video_display_component.ab_sections_changed.disconnect(self.ab_sections_changed)
            self.video_display_component.selections_changed.disconnect(self.selections_changed)
            # 释放视频资源
            with self._video_cap_lock:
                if self.video_cap:
                    self.video_cap.release()
                    self.video_cap = None
        except Exception as e:
            print(f"Error during close window:", e)
        super().closeEvent(event)

    # ---- 저장 폴더 카드 헬퍼 ------------------------------------------------
    def _readable_save_path(self) -> str:
        """홈 디렉토리는 ~ 로 줄여서 표시."""
        path = config.saveDirectory.value or ""
        try:
            home = os.path.expanduser("~")
            if path and path.startswith(home):
                return "~" + path[len(home):]
        except Exception:
            pass
        return path

    def _on_choose_save_folder(self):
        current = config.saveDirectory.value or os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(
            self,
            tr["Setting"]["ChooseDirectory"],
            current,
        )
        if chosen:
            try:
                os.makedirs(chosen, exist_ok=True)
            except Exception as e:
                print(f"저장 폴더 생성 실패: {e}")
            config.set(config.saveDirectory, chosen)
            self.save_path_label.setText(self._readable_save_path())

    def _open_save_folder_in_finder(self):
        path = config.saveDirectory.value
        if path:
            try:
                os.makedirs(path, exist_ok=True)
                subprocess.run(["open", path], check=False)
            except Exception as e:
                print(f"Finder 에서 폴더 열기 실패: {e}")
