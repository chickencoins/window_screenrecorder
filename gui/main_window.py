"""
메인 윈도우.
모든 UI 위젯을 배치하고 녹화/편집/내보내기 기능을 연결.
"""

import os

from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QSpinBox, QCheckBox,
    QRadioButton, QButtonGroup, QFileDialog, QMessageBox,
    QProgressDialog, QStatusBar, QComboBox, QDoubleSpinBox,
    QApplication
)

from gui.region_selector import RegionSelector
from gui.video_preview import VideoPreviewWidget
from core.recorder import ScreenRecorder
from core.editor import VideoEditor
from core.exporter import Exporter


class MainWindow(QMainWindow):
    """화면 녹화기 메인 윈도우."""

    # 상태 상수
    STATE_IDLE = "idle"
    STATE_RECORDING = "recording"
    STATE_PAUSED = "paused"
    STATE_HAS_FRAMES = "has_frames"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screen Recorder")
        self.setMinimumSize(700, 650)
        self.resize(800, 750)

        # 핵심 컴포넌트
        self.recorder = ScreenRecorder(self)
        self.editor = VideoEditor()
        self.exporter = Exporter(self)
        self._region_selector: RegionSelector = None

        # 상태
        self._state = self.STATE_IDLE
        self._region: tuple = None  # (x, y, w, h)
        self._timer_remaining: int = 0
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._duration_timer = QTimer(self)
        self._duration_timer.setSingleShot(True)
        self._duration_timer.timeout.connect(self._on_duration_limit)
        self._loaded_clip_frames: list = None  # 삽입용 불러온 클립

        self._init_ui()
        self._connect_signals()
        self._update_ui_state()

    # ─────────────────── UI 초기화 ───────────────────

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(6)

        # ── 영역 선택 그룹 ──
        region_group = QGroupBox("녹화 영역")
        region_layout = QHBoxLayout(region_group)

        self.btn_select_region = QPushButton("영역 지정")
        self.btn_select_region.setToolTip("마우스 드래그로 녹화할 화면 영역을 선택합니다")
        self.region_label = QLabel("미지정")
        self.region_label.setStyleSheet("color: #888;")

        region_layout.addWidget(self.btn_select_region)
        region_layout.addWidget(self.region_label)
        region_layout.addStretch()
        main_layout.addWidget(region_group)

        # ── 설정 그룹 ──
        settings_group = QGroupBox("설정")
        settings_layout = QGridLayout(settings_group)

        # FPS
        settings_layout.addWidget(QLabel("FPS:"), 0, 0)
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 60)
        self.spin_fps.setValue(30)
        settings_layout.addWidget(self.spin_fps, 0, 1)

        # 커서 캡처
        self.chk_cursor = QCheckBox("마우스 커서 포함")
        self.chk_cursor.setChecked(True)
        settings_layout.addWidget(self.chk_cursor, 0, 2)

        # 타이머 모드
        settings_layout.addWidget(QLabel("타이머:"), 1, 0)
        self.combo_timer_mode = QComboBox()
        self.combo_timer_mode.addItems(["사용 안 함", "카운트다운 후 시작", "녹화 시간 제한"])
        settings_layout.addWidget(self.combo_timer_mode, 1, 1, 1, 2)

        settings_layout.addWidget(QLabel("타이머 (초):"), 2, 0)
        self.spin_timer = QSpinBox()
        self.spin_timer.setRange(1, 3600)
        self.spin_timer.setValue(5)
        settings_layout.addWidget(self.spin_timer, 2, 1)

        # 저장 형식
        settings_layout.addWidget(QLabel("저장 형식:"), 3, 0)
        format_layout = QHBoxLayout()
        self.radio_mp4 = QRadioButton("MP4")
        self.radio_gif = QRadioButton("GIF")
        self.radio_mp4.setChecked(True)
        self.format_group = QButtonGroup()
        self.format_group.addButton(self.radio_mp4)
        self.format_group.addButton(self.radio_gif)
        format_layout.addWidget(self.radio_mp4)
        format_layout.addWidget(self.radio_gif)

        # GIF 스케일
        format_layout.addWidget(QLabel("GIF 스케일:"))
        self.spin_gif_scale = QDoubleSpinBox()
        self.spin_gif_scale.setRange(0.1, 1.0)
        self.spin_gif_scale.setValue(0.5)
        self.spin_gif_scale.setSingleStep(0.1)
        format_layout.addWidget(self.spin_gif_scale)
        format_layout.addStretch()

        settings_layout.addLayout(format_layout, 3, 1, 1, 2)
        main_layout.addWidget(settings_group)

        # ── 녹화 컨트롤 ──
        control_group = QGroupBox("녹화 컨트롤")
        control_layout = QHBoxLayout(control_group)

        self.btn_record = QPushButton("녹화 시작")
        self.btn_record.setStyleSheet(
            "QPushButton { background-color: #d32f2f; color: white; "
            "font-weight: bold; padding: 8px 16px; }"
            "QPushButton:disabled { background-color: #666; }"
        )

        self.btn_pause = QPushButton("일시정지")
        self.btn_pause.setStyleSheet("padding: 8px 16px;")

        self.btn_stop = QPushButton("중지")
        self.btn_stop.setStyleSheet("padding: 8px 16px;")

        self.btn_reset = QPushButton("리셋")
        self.btn_reset.setStyleSheet("padding: 8px 16px;")

        self.countdown_label = QLabel("")
        self.countdown_label.setStyleSheet(
            "color: #ff9800; font-size: 18px; font-weight: bold;"
        )

        control_layout.addWidget(self.btn_record)
        control_layout.addWidget(self.btn_pause)
        control_layout.addWidget(self.btn_stop)
        control_layout.addWidget(self.btn_reset)
        control_layout.addWidget(self.countdown_label)
        control_layout.addStretch()
        main_layout.addWidget(control_group)

        # ── 프리뷰 ──
        preview_group = QGroupBox("프리뷰 / 편집")
        preview_layout = QVBoxLayout(preview_group)

        self.preview = VideoPreviewWidget()
        preview_layout.addWidget(self.preview)

        # 편집 버튼들
        edit_layout = QHBoxLayout()

        self.btn_load_video = QPushButton("영상 불러오기")
        self.btn_load_video.setToolTip("기존 비디오 파일을 불러와서 편집합니다")

        self.btn_load_clip = QPushButton("클립 불러오기")
        self.btn_load_clip.setToolTip("삽입할 클립을 불러옵니다")

        self.btn_insert = QPushButton("현재 위치에 삽입")
        self.btn_insert.setToolTip("불러온 클립을 현재 타임라인 위치에 삽입합니다")

        self.btn_delete_segment = QPushButton("선택 구간 삭제")
        self.btn_delete_segment.setToolTip("구간 시작/끝 마커 사이의 프레임을 삭제합니다")

        self.btn_save = QPushButton("저장")
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #1976d2; color: white; "
            "font-weight: bold; padding: 8px 16px; }"
            "QPushButton:disabled { background-color: #666; }"
        )

        self.clip_info_label = QLabel("")

        edit_layout.addWidget(self.btn_load_video)
        edit_layout.addWidget(self.btn_load_clip)
        edit_layout.addWidget(self.btn_insert)
        edit_layout.addWidget(self.btn_delete_segment)
        edit_layout.addStretch()
        edit_layout.addWidget(self.clip_info_label)
        edit_layout.addWidget(self.btn_save)

        preview_layout.addLayout(edit_layout)
        main_layout.addWidget(preview_group, stretch=1)

        # 상태바
        self.statusBar().showMessage("준비")

    # ─────────────────── 시그널 연결 ───────────────────

    def _connect_signals(self):
        # 영역 선택
        self.btn_select_region.clicked.connect(self._on_select_region)

        # 녹화 컨트롤
        self.btn_record.clicked.connect(self._on_record)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_reset.clicked.connect(self._on_reset)

        # 편집
        self.btn_load_video.clicked.connect(self._on_load_video)
        self.btn_load_clip.clicked.connect(self._on_load_clip)
        self.btn_insert.clicked.connect(self._on_insert_at_position)
        self.btn_delete_segment.clicked.connect(self._on_delete_segment)
        self.btn_save.clicked.connect(self._on_save)

        # 레코더 시그널
        self.recorder.recording_stopped.connect(self._on_recording_finished)
        self.recorder.frame_count_updated.connect(self._on_frame_count_updated)
        self.recorder.error_occurred.connect(self._on_recorder_error)

        # 내보내기 시그널
        self.exporter.finished.connect(self._on_export_finished)
        self.exporter.error.connect(self._on_export_error)

    # ─────────────────── 상태 관리 ───────────────────

    def _set_state(self, state: str):
        self._state = state
        self._update_ui_state()

    def _update_ui_state(self):
        state = self._state
        has_region = self._region is not None
        has_frames = self.editor.get_frame_count() > 0
        has_clip = self._loaded_clip_frames is not None

        # 영역 선택: 녹화 중이 아닐 때만
        self.btn_select_region.setEnabled(
            state not in (self.STATE_RECORDING, self.STATE_PAUSED)
        )

        # 녹화 시작: 대기 + 영역 지정됨
        self.btn_record.setEnabled(
            state in (self.STATE_IDLE, self.STATE_HAS_FRAMES) and has_region
        )

        # 일시정지: 녹화 중일 때
        self.btn_pause.setEnabled(state in (self.STATE_RECORDING, self.STATE_PAUSED))
        if state == self.STATE_PAUSED:
            self.btn_pause.setText("재개")
        else:
            self.btn_pause.setText("일시정지")

        # 중지: 녹화 중 또는 일시정지
        self.btn_stop.setEnabled(state in (self.STATE_RECORDING, self.STATE_PAUSED))

        # 리셋: 프레임이 있을 때
        self.btn_reset.setEnabled(
            state in (self.STATE_HAS_FRAMES, self.STATE_IDLE) and has_frames
        )

        # 저장: 프레임이 있고 녹화 중이 아닐 때
        self.btn_save.setEnabled(
            state in (self.STATE_HAS_FRAMES, self.STATE_IDLE) and has_frames
        )

        # 편집 버튼
        self.btn_load_video.setEnabled(
            state not in (self.STATE_RECORDING, self.STATE_PAUSED)
        )
        self.btn_load_clip.setEnabled(
            state not in (self.STATE_RECORDING, self.STATE_PAUSED)
        )
        self.btn_insert.setEnabled(
            has_frames and has_clip
            and state not in (self.STATE_RECORDING, self.STATE_PAUSED)
        )
        self.btn_delete_segment.setEnabled(
            has_frames
            and state not in (self.STATE_RECORDING, self.STATE_PAUSED)
        )

        # 설정: 녹화 중 변경 불가
        recording = state in (self.STATE_RECORDING, self.STATE_PAUSED)
        self.spin_fps.setEnabled(not recording)
        self.chk_cursor.setEnabled(not recording)
        self.combo_timer_mode.setEnabled(not recording)
        self.spin_timer.setEnabled(not recording)

    # ─────────────────── 영역 선택 ───────────────────

    def _on_select_region(self):
        self.hide()
        QApplication.processEvents()

        self._region_selector = RegionSelector()
        self._region_selector.region_selected.connect(self._on_region_selected)
        self._region_selector.selection_cancelled.connect(self._on_region_cancelled)
        self._region_selector.showFullScreen()

    @pyqtSlot(int, int, int, int)
    def _on_region_selected(self, x, y, w, h):
        self._region = (x, y, w, h)
        self.region_label.setText(f"위치: ({x}, {y})  크기: {w} x {h}")
        self.region_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        self.show()
        self.activateWindow()
        self._update_ui_state()
        self.statusBar().showMessage(f"영역 지정됨: {w}x{h}")

    def _on_region_cancelled(self):
        self.show()
        self.activateWindow()

    # ─────────────────── 녹화 ───────────────────

    def _on_record(self):
        if not self._region:
            QMessageBox.warning(self, "경고", "먼저 녹화 영역을 지정하세요.")
            return

        timer_mode = self.combo_timer_mode.currentIndex()

        if timer_mode == 1:
            # 카운트다운 후 시작
            self._timer_remaining = self.spin_timer.value()
            self.countdown_label.setText(f"{self._timer_remaining}")
            self._countdown_timer.start()
            self.btn_record.setEnabled(False)
            self.statusBar().showMessage("카운트다운...")
            return

        self._start_recording()

        if timer_mode == 2:
            # 녹화 시간 제한
            duration_ms = self.spin_timer.value() * 1000
            self._duration_timer.start(duration_ms)

    def _on_countdown_tick(self):
        self._timer_remaining -= 1
        if self._timer_remaining > 0:
            self.countdown_label.setText(f"{self._timer_remaining}")
        else:
            self._countdown_timer.stop()
            self.countdown_label.setText("")
            self._start_recording()

    def _start_recording(self):
        fps = self.spin_fps.value()
        capture_cursor = self.chk_cursor.isChecked()
        self.recorder.start_recording(self._region, fps, capture_cursor)
        self._set_state(self.STATE_RECORDING)
        self.statusBar().showMessage("녹화 중...")

    def _on_pause(self):
        if self._state == self.STATE_RECORDING:
            self.recorder.pause()
            self._set_state(self.STATE_PAUSED)
            self.statusBar().showMessage("일시정지")
        elif self._state == self.STATE_PAUSED:
            self.recorder.resume()
            self._set_state(self.STATE_RECORDING)
            self.statusBar().showMessage("녹화 중...")

    def _on_stop(self):
        self._duration_timer.stop()
        self.recorder.stop()
        self.statusBar().showMessage("녹화 중지 중...")

    def _on_duration_limit(self):
        """녹화 시간 제한 도달."""
        self.recorder.stop()
        self.statusBar().showMessage("녹화 시간 제한 도달")

    @pyqtSlot()
    def _on_recording_finished(self):
        frames = self.recorder.frames
        if frames:
            fps = self.spin_fps.value()
            self.editor.set_frames(frames, fps)
            self.preview.set_frames(self.editor.frames, fps)
            mem = self.editor.get_estimated_memory_mb()
            self._set_state(self.STATE_HAS_FRAMES)
            self.statusBar().showMessage(
                f"녹화 완료: {len(frames)}프레임 (메모리: {mem:.0f}MB)"
            )
        else:
            self._set_state(self.STATE_IDLE)
            self.statusBar().showMessage("녹화된 프레임이 없습니다")

    @pyqtSlot(int)
    def _on_frame_count_updated(self, count: int):
        self.statusBar().showMessage(f"녹화 중... {count}프레임")

    @pyqtSlot(str)
    def _on_recorder_error(self, msg: str):
        self._set_state(self.STATE_IDLE)
        QMessageBox.critical(self, "녹화 오류", f"녹화 중 오류가 발생했습니다:\n{msg}")

    # ─────────────────── 리셋 ───────────────────

    def _on_reset(self):
        reply = QMessageBox.question(
            self, "리셋 확인",
            "모든 녹화 내용을 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.editor.clear()
            self._loaded_clip_frames = None
            self.clip_info_label.setText("")
            self.preview.set_frames([])
            self._set_state(self.STATE_IDLE)
            self.statusBar().showMessage("리셋 완료")

    # ─────────────────── 편집: 불러오기/삽입/삭제 ───────────────────

    def _on_load_video(self):
        """기존 영상을 메인 타임라인으로 불러오기."""
        path, _ = QFileDialog.getOpenFileName(
            self, "영상 불러오기", "",
            "비디오 파일 (*.mp4 *.avi *.mkv *.mov *.wmv);;모든 파일 (*)"
        )
        if not path:
            return

        try:
            frames, fps = self.editor.load_video(path)
            self.editor.set_frames(frames, fps)
            self.spin_fps.setValue(fps)
            self.preview.set_frames(self.editor.frames, fps)
            self._set_state(self.STATE_HAS_FRAMES)
            self.statusBar().showMessage(
                f"영상 불러옴: {len(frames)}프레임, {fps}fps"
            )
        except IOError as e:
            QMessageBox.critical(self, "오류", str(e))

    def _on_load_clip(self):
        """삽입용 클립 불러오기."""
        path, _ = QFileDialog.getOpenFileName(
            self, "클립 불러오기", "",
            "비디오 파일 (*.mp4 *.avi *.mkv *.mov *.wmv);;모든 파일 (*)"
        )
        if not path:
            return

        try:
            frames, fps = self.editor.load_video(path)
            self._loaded_clip_frames = frames
            self.clip_info_label.setText(
                f"클립: {len(frames)}프레임 ({len(frames)/max(1,fps):.1f}s)"
            )
            self._update_ui_state()
            self.statusBar().showMessage(f"클립 불러옴: {len(frames)}프레임")
        except IOError as e:
            QMessageBox.critical(self, "오류", str(e))

    def _on_insert_at_position(self):
        """현재 타임라인 위치에 클립 삽입."""
        if not self._loaded_clip_frames:
            QMessageBox.warning(self, "경고", "먼저 삽입할 클립을 불러오세요.")
            return

        pos = self.preview.get_current_position()
        count = len(self._loaded_clip_frames)

        reply = QMessageBox.question(
            self, "삽입 확인",
            f"프레임 {pos} 위치에 {count}프레임을 삽입하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.editor.insert_frames(pos, self._loaded_clip_frames)
        self.preview.set_frames(self.editor.frames, self.editor.fps)
        # 삽입 후 삽입된 위치로 이동
        self.preview.timeline_slider.setValue(pos)
        self.statusBar().showMessage(f"{count}프레임 삽입됨 (위치: {pos})")
        self._update_ui_state()

    def _on_delete_segment(self):
        """선택 구간 삭제."""
        start, end = self.preview.get_selection()

        if start < 0 or end < 0:
            QMessageBox.warning(
                self, "경고",
                "먼저 구간 시작과 끝 마커를 지정하세요."
            )
            return

        if start > end:
            start, end = end, start

        count = end - start + 1
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"프레임 [{start}] ~ [{end}] ({count}프레임)을 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        deleted = self.editor.delete_segment(start, end)
        if self.editor.get_frame_count() > 0:
            self.preview.set_frames(self.editor.frames, self.editor.fps)
            new_pos = min(start, self.editor.get_frame_count() - 1)
            self.preview.timeline_slider.setValue(new_pos)
            self.statusBar().showMessage(f"{deleted}프레임 삭제됨")
        else:
            self.preview.set_frames([])
            self._set_state(self.STATE_IDLE)
            self.statusBar().showMessage("모든 프레임이 삭제되었습니다")

        self._update_ui_state()

    # ─────────────────── 저장 ───────────────────

    def _on_save(self):
        if self.editor.get_frame_count() == 0:
            QMessageBox.warning(self, "경고", "저장할 프레임이 없습니다.")
            return

        # 형식 결정
        if self.radio_mp4.isChecked():
            fmt = "mp4"
            filter_str = "MP4 비디오 (*.mp4)"
            default_ext = ".mp4"
        else:
            fmt = "gif"
            filter_str = "GIF 이미지 (*.gif)"
            default_ext = ".gif"

        path, _ = QFileDialog.getSaveFileName(
            self, "저장 위치 선택", f"recording{default_ext}", filter_str
        )
        if not path:
            return

        # 확장자 보장
        if not path.lower().endswith(default_ext):
            path += default_ext

        # 프로그레스 다이얼로그
        self._progress = QProgressDialog("내보내는 중...", None, 0, 100, self)
        self._progress.setWindowTitle("내보내기")
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setAutoClose(True)
        self._progress.setMinimumDuration(0)
        self._progress.show()

        self.exporter.progress.connect(self._progress.setValue)

        gif_scale = self.spin_gif_scale.value() if fmt == "gif" else 1.0

        self.exporter.export(
            self.editor.frames,
            self.editor.fps,
            path,
            fmt,
            gif_scale
        )

    @pyqtSlot(str)
    def _on_export_finished(self, path: str):
        if hasattr(self, '_progress'):
            self._progress.close()
        QMessageBox.information(
            self, "저장 완료",
            f"파일이 저장되었습니다:\n{path}"
        )
        self.statusBar().showMessage(f"저장 완료: {path}")

    @pyqtSlot(str)
    def _on_export_error(self, msg: str):
        if hasattr(self, '_progress'):
            self._progress.close()
        QMessageBox.critical(
            self, "저장 오류",
            f"저장 중 오류가 발생했습니다:\n{msg}"
        )

    # ─────────────────── 창 닫기 ───────────────────

    def closeEvent(self, event):
        if self.recorder.is_recording:
            reply = QMessageBox.question(
                self, "종료 확인",
                "녹화 중입니다. 종료하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
            self.recorder.stop()

        event.accept()
