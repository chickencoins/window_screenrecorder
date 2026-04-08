"""
커서 위치 가져오기 및 프레임에 커서 그리기 유틸리티.
Windows에서는 win32api, Linux에서는 Qt 폴백 사용.
"""

import cv2
import numpy as np

try:
    import win32api
    import win32gui
    import win32con

    def get_cursor_position():
        """스크린 좌표 기준 커서 위치 (x, y) 반환."""
        return win32api.GetCursorPos()

    def get_cursor_icon():
        """현재 커서 아이콘 정보 반환 (향후 확장용)."""
        cursor_info = win32gui.GetCursorInfo()
        return cursor_info

except ImportError:
    # Linux/macOS 폴백: PyQt5의 QCursor 사용
    from PyQt5.QtGui import QCursor

    def get_cursor_position():
        pos = QCursor.pos()
        return (pos.x(), pos.y())

    def get_cursor_icon():
        return None


def draw_cursor_on_frame(frame: np.ndarray, region: tuple,
                         cursor_size: int = 12,
                         cursor_color: tuple = (0, 255, 255),
                         outline_color: tuple = (0, 0, 0)) -> np.ndarray:
    """
    프레임 위에 커서 위치를 표시.

    Args:
        frame: BGR numpy 배열
        region: (x, y, w, h) 캡처 영역 (스크린 좌표)
        cursor_size: 커서 표시 크기
        cursor_color: 커서 색상 (BGR)
        outline_color: 외곽선 색상 (BGR)

    Returns:
        커서가 그려진 프레임
    """
    cx, cy = get_cursor_position()
    rx, ry, rw, rh = region

    # 스크린 좌표를 프레임 로컬 좌표로 변환
    fx = cx - rx
    fy = cy - ry

    h, w = frame.shape[:2]
    if 0 <= fx < w and 0 <= fy < h:
        # 화살표 모양 커서 그리기
        pts = np.array([
            [fx, fy],
            [fx, fy + cursor_size],
            [fx + cursor_size * 0.35, fy + cursor_size * 0.7],
            [fx + cursor_size * 0.7, fy + cursor_size],
            [fx + cursor_size * 0.5, fy + cursor_size * 0.6],
            [fx + cursor_size, fy + cursor_size * 0.5],
        ], dtype=np.int32)

        # 외곽선
        cv2.fillPoly(frame, [pts], outline_color)
        # 안쪽 (약간 축소)
        inner_pts = np.array([
            [fx + 1, fy + 1],
            [fx + 1, fy + cursor_size - 2],
            [fx + cursor_size * 0.35, fy + cursor_size * 0.7 - 1],
            [fx + cursor_size * 0.7 - 1, fy + cursor_size - 2],
            [fx + cursor_size * 0.5 - 1, fy + cursor_size * 0.6],
            [fx + cursor_size - 2, fy + cursor_size * 0.5],
        ], dtype=np.int32)
        cv2.fillPoly(frame, [inner_pts], cursor_color)

    return frame
