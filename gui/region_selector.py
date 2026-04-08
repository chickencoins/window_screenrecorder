"""
영역 선택 오버레이.
전체 화면에 반투명 오버레이를 띄우고 마우스 드래그로 녹화 영역을 선택.
"""

from PyQt5.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from PyQt5.QtWidgets import QWidget, QApplication


class RegionSelector(QWidget):
    """전체 화면 반투명 오버레이로 마우스 드래그 영역 선택."""

    region_selected = pyqtSignal(int, int, int, int)  # x, y, w, h (스크린 좌표)
    selection_cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

        # 전체 가상 데스크톱을 커버
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.virtualGeometry()
            self.setGeometry(geo)

        self._origin: QPoint = None
        self._current: QPoint = None
        self._selection: QRect = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 반투명 어두운 오버레이
        overlay_color = QColor(0, 0, 0, 120)
        painter.fillRect(self.rect(), overlay_color)

        if self._origin and self._current:
            # 선택 영역 계산
            rect = QRect(self._origin, self._current).normalized()

            # 선택 영역을 투명하게 (오버레이 제거)
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.transparent)

            # 다시 일반 모드로
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            # 선택 영역 테두리
            pen = QPen(QColor(0, 180, 255), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            # 크기 표시
            dpr = self.devicePixelRatioF()
            w = int(rect.width() * dpr)
            h = int(rect.height() * dpr)
            size_text = f"{w} x {h}"

            font = QFont("Arial", 12)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))

            text_x = rect.left() + 5
            text_y = rect.top() - 8
            if text_y < 15:
                text_y = rect.top() + 20

            painter.drawText(text_x, text_y, size_text)
        else:
            # 안내 텍스트
            painter.setPen(QColor(255, 255, 255, 200))
            font = QFont("Arial", 16)
            painter.setFont(font)
            painter.drawText(
                self.rect(), Qt.AlignCenter,
                "마우스를 드래그하여 녹화 영역을 선택하세요\nESC: 취소"
            )

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._origin = event.pos()
            self._current = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self._origin:
            self._current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._origin:
            self._current = event.pos()
            rect = QRect(self._origin, self._current).normalized()

            # 최소 크기 검증 (너무 작은 영역 방지)
            if rect.width() < 10 or rect.height() < 10:
                self._origin = None
                self._current = None
                self.update()
                return

            # 위젯 로컬 좌표 → 글로벌 스크린 좌표 변환
            top_left = self.mapToGlobal(rect.topLeft())

            # DPI 스케일링 고려
            dpr = self.devicePixelRatioF()
            x = int(top_left.x() * dpr)
            y = int(top_left.y() * dpr)
            w = int(rect.width() * dpr)
            h = int(rect.height() * dpr)

            # 짝수 크기로 맞추기 (비디오 코덱 호환성)
            w = w if w % 2 == 0 else w + 1
            h = h if h % 2 == 0 else h + 1

            self.region_selected.emit(x, y, w, h)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.selection_cancelled.emit()
            self.close()
