"""
비디오 프리뷰 위젯.
녹화된 또는 불러온 프레임을 타임라인 슬라이더로 탐색하고,
구간 마커를 지정하여 편집 작업을 지원.
"""

import cv2
import numpy as np

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QPushButton, QStyle, QSizePolicy
)


class MarkerSlider(QSlider):
    """시작/끝 마커를 시각적으로 표시하는 커스텀 슬라이더."""

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.start_marker: int = -1
        self.end_marker: int = -1

    def set_markers(self, start: int, end: int):
        self.start_marker = start
        self.end_marker = end
        self.update()

    def clear_markers(self):
        self.start_marker = -1
        self.end_marker = -1
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        if self.maximum() <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 슬라이더 그루브 영역 계산
        opt = self.style().subControlRect(
            QStyle.CC_Slider, None, QStyle.SC_SliderGroove, self
        )
        if opt.isNull():
            groove_left = 8
            groove_right = self.width() - 8
        else:
            groove_left = opt.left()
            groove_right = opt.right()

        groove_width = groove_right - groove_left
        slider_range = self.maximum() - self.minimum()

        def pos_for_value(val):
            if slider_range == 0:
                return groove_left
            ratio = (val - self.minimum()) / slider_range
            return int(groove_left + ratio * groove_width)

        # 선택 구간 하이라이트
        if self.start_marker >= 0 and self.end_marker >= 0:
            sx = pos_for_value(self.start_marker)
            ex = pos_for_value(self.end_marker)
            highlight = QColor(255, 100, 100, 80)
            painter.fillRect(sx, 0, ex - sx, self.height(), highlight)

        # 시작 마커 (파란색)
        if self.start_marker >= 0:
            x = pos_for_value(self.start_marker)
            pen = QPen(QColor(0, 120, 255), 2)
            painter.setPen(pen)
            painter.drawLine(x, 0, x, self.height())

        # 끝 마커 (빨간색)
        if self.end_marker >= 0:
            x = pos_for_value(self.end_marker)
            pen = QPen(QColor(255, 80, 80), 2)
            painter.setPen(pen)
            painter.drawLine(x, 0, x, self.height())

        painter.end()


class VideoPreviewWidget(QWidget):
    """비디오 프리뷰 및 타임라인 편집 위젯."""

    position_changed = pyqtSignal(int)  # 현재 프레임 인덱스

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames: list = []
        self.start_marker: int = -1
        self.end_marker: int = -1

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 프레임 표시 영역
        self.frame_label = QLabel("프리뷰 영역")
        self.frame_label.setAlignment(Qt.AlignCenter)
        self.frame_label.setMinimumSize(320, 180)
        self.frame_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.frame_label.setStyleSheet(
            "background-color: #1a1a2e; color: #888; border: 1px solid #333;"
        )
        layout.addWidget(self.frame_label)

        # 타임라인 슬라이더
        self.timeline_slider = MarkerSlider(Qt.Horizontal)
        self.timeline_slider.setMinimum(0)
        self.timeline_slider.setMaximum(0)
        self.timeline_slider.setEnabled(False)
        self.timeline_slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.timeline_slider)

        # 프레임 카운터
        info_layout = QHBoxLayout()
        self.frame_counter = QLabel("프레임: 0 / 0")
        self.time_label = QLabel("시간: 0.0s")
        info_layout.addWidget(self.frame_counter)
        info_layout.addStretch()
        info_layout.addWidget(self.time_label)
        layout.addLayout(info_layout)

        # 마커 컨트롤
        marker_layout = QHBoxLayout()

        self.btn_mark_start = QPushButton("구간 시작 [")
        self.btn_mark_start.setToolTip("현재 위치를 구간 시작점으로 지정")
        self.btn_mark_start.clicked.connect(self._mark_start)
        self.btn_mark_start.setEnabled(False)

        self.btn_mark_end = QPushButton("구간 끝 ]")
        self.btn_mark_end.setToolTip("현재 위치를 구간 끝점으로 지정")
        self.btn_mark_end.clicked.connect(self._mark_end)
        self.btn_mark_end.setEnabled(False)

        self.btn_clear_markers = QPushButton("마커 초기화")
        self.btn_clear_markers.clicked.connect(self._clear_markers)
        self.btn_clear_markers.setEnabled(False)

        self.marker_info = QLabel("구간: 미설정")

        marker_layout.addWidget(self.btn_mark_start)
        marker_layout.addWidget(self.btn_mark_end)
        marker_layout.addWidget(self.btn_clear_markers)
        marker_layout.addStretch()
        marker_layout.addWidget(self.marker_info)

        layout.addLayout(marker_layout)

    def set_frames(self, frames: list, fps: int = 30):
        """프레임 리스트 설정 및 UI 업데이트."""
        self.frames = frames
        self.fps = fps
        self.start_marker = -1
        self.end_marker = -1

        if frames:
            self.timeline_slider.setMaximum(len(frames) - 1)
            self.timeline_slider.setValue(0)
            self.timeline_slider.setEnabled(True)
            self.btn_mark_start.setEnabled(True)
            self.btn_mark_end.setEnabled(True)
            self.btn_clear_markers.setEnabled(True)
            self.timeline_slider.clear_markers()
            self._display_frame(0)
        else:
            self.timeline_slider.setMaximum(0)
            self.timeline_slider.setEnabled(False)
            self.btn_mark_start.setEnabled(False)
            self.btn_mark_end.setEnabled(False)
            self.btn_clear_markers.setEnabled(False)
            self.frame_label.clear()
            self.frame_label.setText("프리뷰 영역")
            self.frame_counter.setText("프레임: 0 / 0")
            self.time_label.setText("시간: 0.0s")
            self.marker_info.setText("구간: 미설정")

    def get_current_position(self) -> int:
        """현재 슬라이더 위치 반환."""
        return self.timeline_slider.value()

    def get_selection(self) -> tuple:
        """선택 구간 반환 (start, end). 미설정 시 (-1, -1)."""
        return (self.start_marker, self.end_marker)

    def _on_slider_changed(self, value: int):
        if 0 <= value < len(self.frames):
            self._display_frame(value)
            self.position_changed.emit(value)

    def _display_frame(self, index: int):
        """프레임을 QPixmap으로 변환하여 표시."""
        if index < 0 or index >= len(self.frames):
            return

        frame = self.frames[index]
        h, w, ch = frame.shape
        bytes_per_line = ch * w

        # BGR -> RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        # 라벨 크기에 맞게 스케일
        scaled = pixmap.scaled(
            self.frame_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.frame_label.setPixmap(scaled)

        # 정보 업데이트
        total = len(self.frames)
        self.frame_counter.setText(f"프레임: {index + 1} / {total}")
        time_sec = index / max(1, self.fps)
        total_sec = total / max(1, self.fps)
        self.time_label.setText(f"시간: {time_sec:.1f}s / {total_sec:.1f}s")

    def _mark_start(self):
        """현재 위치를 시작 마커로 설정."""
        pos = self.timeline_slider.value()
        self.start_marker = pos
        # 끝 마커가 시작보다 앞이면 리셋
        if self.end_marker >= 0 and self.end_marker < self.start_marker:
            self.end_marker = -1
        self._update_marker_display()

    def _mark_end(self):
        """현재 위치를 끝 마커로 설정."""
        pos = self.timeline_slider.value()
        self.end_marker = pos
        # 시작 마커가 끝보다 뒤이면 리셋
        if self.start_marker >= 0 and self.start_marker > self.end_marker:
            self.start_marker = -1
        self._update_marker_display()

    def _clear_markers(self):
        """마커 초기화."""
        self.start_marker = -1
        self.end_marker = -1
        self._update_marker_display()

    def _update_marker_display(self):
        """마커 정보 UI 업데이트."""
        self.timeline_slider.set_markers(self.start_marker, self.end_marker)

        if self.start_marker >= 0 and self.end_marker >= 0:
            count = self.end_marker - self.start_marker + 1
            duration = count / max(1, self.fps)
            self.marker_info.setText(
                f"구간: [{self.start_marker}] ~ [{self.end_marker}] "
                f"({count}프레임, {duration:.1f}s)"
            )
        elif self.start_marker >= 0:
            self.marker_info.setText(f"구간 시작: [{self.start_marker}]")
        elif self.end_marker >= 0:
            self.marker_info.setText(f"구간 끝: [{self.end_marker}]")
        else:
            self.marker_info.setText("구간: 미설정")
