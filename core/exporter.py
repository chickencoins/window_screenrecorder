"""
비디오 내보내기 모듈.
MP4 (OpenCV VideoWriter) 및 GIF (Pillow) 형식 지원.
"""

import cv2
import numpy as np
from PIL import Image
from PyQt5.QtCore import QObject, QThread, pyqtSignal


class ExportWorker(QObject):
    """백그라운드 스레드에서 내보내기 수행."""

    progress = pyqtSignal(int)  # 진행률 (0-100)
    finished = pyqtSignal(str)  # 완료 메시지
    error = pyqtSignal(str)

    def __init__(self, frames: list, fps: int, output_path: str,
                 fmt: str = "mp4", gif_scale: float = 1.0):
        super().__init__()
        self.frames = frames
        self.fps = fps
        self.output_path = output_path
        self.fmt = fmt.lower()
        self.gif_scale = gif_scale

    def run(self):
        try:
            if self.fmt == "mp4":
                self._export_mp4()
            elif self.fmt == "gif":
                self._export_gif()
            else:
                self.error.emit(f"지원하지 않는 형식: {self.fmt}")
                return
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))

    def _export_mp4(self):
        """MP4 형식으로 내보내기."""
        if not self.frames:
            self.error.emit("내보낼 프레임이 없습니다.")
            return

        h, w = self.frames[0].shape[:2]
        total = len(self.frames)

        # H.264 코덱 시도, 실패 시 mp4v 폴백
        writer = None
        for codec in ['avc1', 'mp4v']:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, (w, h))
            if writer.isOpened():
                break
            writer.release()
            writer = None

        if writer is None:
            self.error.emit("비디오 코덱을 초기화할 수 없습니다.")
            return

        for i, frame in enumerate(self.frames):
            writer.write(frame)
            progress = int((i + 1) / total * 100)
            self.progress.emit(progress)

        writer.release()

    def _export_gif(self):
        """GIF 형식으로 내보내기."""
        if not self.frames:
            self.error.emit("내보낼 프레임이 없습니다.")
            return

        duration_ms = max(1, int(1000 / self.fps))
        total = len(self.frames)
        pil_frames = []

        for i, frame in enumerate(self.frames):
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            if self.gif_scale != 1.0:
                h, w = rgb.shape[:2]
                new_w = max(1, int(w * self.gif_scale))
                new_h = max(1, int(h * self.gif_scale))
                rgb = cv2.resize(rgb, (new_w, new_h),
                                 interpolation=cv2.INTER_LANCZOS4)

            pil_img = Image.fromarray(rgb)
            # GIF는 256색 제한이므로 양자화
            pil_img = pil_img.quantize(method=Image.Quantize.MEDIANCUT)
            pil_frames.append(pil_img)

            progress = int((i + 1) / total * 100)
            self.progress.emit(progress)

        pil_frames[0].save(
            self.output_path,
            save_all=True,
            append_images=pil_frames[1:],
            duration=duration_ms,
            loop=0,
            optimize=False,
        )


class Exporter(QObject):
    """비디오 내보내기 관리자."""

    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread = None
        self._worker: ExportWorker = None

    def export(self, frames: list, fps: int, output_path: str,
               fmt: str = "mp4", gif_scale: float = 1.0):
        """
        비디오 내보내기 시작 (백그라운드 스레드).

        Args:
            frames: BGR numpy 배열 리스트
            fps: 프레임 레이트
            output_path: 저장 경로
            fmt: "mp4" 또는 "gif"
            gif_scale: GIF 스케일 비율 (기본 1.0)
        """
        if self._thread and self._thread.isRunning():
            return

        self._thread = QThread()
        self._worker = ExportWorker(frames, fps, output_path, fmt, gif_scale)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress.emit)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._thread.start()

    def _on_finished(self, path: str):
        self._thread.quit()
        self._thread.wait()
        self.finished.emit(path)

    def _on_error(self, msg: str):
        self._thread.quit()
        self._thread.wait()
        self.error.emit(msg)
