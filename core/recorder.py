"""
화면 녹화 엔진.
mss를 사용한 스크린 캡처를 QThread 워커 패턴으로 실행.
메모리 모드(RAM) 또는 디스크 버퍼 모드 선택 가능.
"""

import time
import threading

import numpy as np
from PyQt5.QtCore import QObject, QThread, pyqtSignal

import mss

from utils.cursor import draw_cursor_on_frame
from core.disk_buffer import DiskFrameBuffer


class RecordWorker(QObject):
    """백그라운드 스레드에서 화면 캡처를 수행하는 워커."""

    frame_captured = pyqtSignal(int)  # 캡처된 프레임 수
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, region: tuple, fps: int, capture_cursor: bool,
                 disk_mode: bool = False, jpeg_quality: int = 95):
        super().__init__()
        self.region = region  # (x, y, w, h)
        self.fps = fps
        self.capture_cursor = capture_cursor
        self.disk_mode = disk_mode

        # 저장소: RAM 리스트 또는 디스크 버퍼
        if disk_mode:
            self.frames = None  # 디스크 모드에서는 사용 안 함
            self.disk_buffer = DiskFrameBuffer(jpeg_quality=jpeg_quality)
        else:
            self.frames: list = []
            self.disk_buffer = None

        self._running = False
        self._paused = threading.Event()
        self._paused.set()  # 초기 상태: 일시정지 아님
        self._frame_count = 0

    def run(self):
        """메인 캡처 루프."""
        self._running = True
        interval = 1.0 / self.fps
        x, y, w, h = self.region

        try:
            with mss.mss() as sct:
                monitor = {"left": x, "top": y, "width": w, "height": h}

                while self._running:
                    self._paused.wait()  # 일시정지 시 블로킹
                    if not self._running:
                        break

                    t0 = time.perf_counter()

                    img = sct.grab(monitor)
                    frame = np.array(img)
                    # BGRA -> BGR (알파 채널 제거)
                    frame = frame[:, :, :3].copy()

                    if self.capture_cursor:
                        frame = draw_cursor_on_frame(frame, self.region)

                    # 저장소에 프레임 추가
                    if self.disk_mode:
                        self.disk_buffer.append(frame)
                    else:
                        self.frames.append(frame)

                    self._frame_count += 1
                    self.frame_captured.emit(self._frame_count)

                    elapsed = time.perf_counter() - t0
                    sleep_time = interval - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)

        except Exception as e:
            self.error.emit(str(e))

        self.finished.emit()

    def pause(self):
        """일시정지."""
        self._paused.clear()

    def resume(self):
        """재개."""
        self._paused.set()

    def stop(self):
        """녹화 중지."""
        self._running = False
        self._paused.set()  # 일시정지 상태에서 빠져나오도록


class ScreenRecorder(QObject):
    """화면 녹화 관리자. QThread + Worker 패턴."""

    recording_started = pyqtSignal()
    recording_paused = pyqtSignal()
    recording_resumed = pyqtSignal()
    recording_stopped = pyqtSignal()
    frame_count_updated = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread = None
        self._worker: RecordWorker = None
        self._is_recording = False
        self._is_paused = False

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def frames(self) -> list:
        """RAM 모드에서의 프레임 리스트."""
        if self._worker and self._worker.frames is not None:
            return self._worker.frames
        return []

    @property
    def disk_buffer(self) -> DiskFrameBuffer:
        """디스크 모드에서의 프레임 버퍼."""
        if self._worker:
            return self._worker.disk_buffer
        return None

    @property
    def is_disk_mode(self) -> bool:
        """현재 디스크 모드 여부."""
        if self._worker:
            return self._worker.disk_mode
        return False

    def start_recording(self, region: tuple, fps: int, capture_cursor: bool,
                        disk_mode: bool = False, jpeg_quality: int = 95):
        """녹화 시작."""
        if self._is_recording:
            return

        self._thread = QThread()
        self._worker = RecordWorker(region, fps, capture_cursor,
                                    disk_mode, jpeg_quality)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.frame_captured.connect(self.frame_count_updated.emit)

        self._is_recording = True
        self._is_paused = False
        self._thread.start()
        self.recording_started.emit()

    def pause(self):
        """일시정지."""
        if self._worker and self._is_recording and not self._is_paused:
            self._worker.pause()
            self._is_paused = True
            self.recording_paused.emit()

    def resume(self):
        """재개."""
        if self._worker and self._is_recording and self._is_paused:
            self._worker.resume()
            self._is_paused = False
            self.recording_resumed.emit()

    def stop(self):
        """녹화 중지."""
        if self._worker:
            self._worker.stop()

    def _on_finished(self):
        """녹화 완료 처리."""
        self._is_recording = False
        self._is_paused = False
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self.recording_stopped.emit()

    def _on_error(self, msg: str):
        """에러 처리."""
        self._is_recording = False
        self._is_paused = False
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self.error_occurred.emit(msg)
