"""
비디오 편집기.
프레임 리스트에 대한 삽입, 삭제, 불러오기 등 편집 작업 수행.
메모리(RAM) 모드와 디스크 버퍼 모드 모두 지원.
"""

import cv2
import numpy as np

from core.disk_buffer import DiskFrameBuffer


class VideoEditor:
    """
    비디오 편집기.
    disk_mode=False: 기존 인메모리 방식 (self.frames 리스트)
    disk_mode=True: DiskFrameBuffer 사용 (디스크 저장)
    """

    def __init__(self):
        self.frames: list = []
        self.fps: int = 30
        self._disk_buffer: DiskFrameBuffer = None
        self._disk_mode: bool = False

    @property
    def disk_mode(self) -> bool:
        return self._disk_mode

    def set_frames(self, frames: list, fps: int = 30):
        """프레임 리스트와 FPS 설정 (RAM 모드)."""
        self._disk_mode = False
        self.frames = list(frames)
        self.fps = fps
        # 디스크 버퍼가 있었다면 정리
        if self._disk_buffer:
            self._disk_buffer.cleanup()
            self._disk_buffer = None

    def set_disk_buffer(self, disk_buffer: DiskFrameBuffer, fps: int = 30):
        """디스크 버퍼를 편집 소스로 설정."""
        self._disk_mode = True
        self._disk_buffer = disk_buffer
        self.fps = fps
        self.frames = []  # RAM 프레임 비움

    def clear(self):
        """모든 프레임 제거."""
        self.frames.clear()
        if self._disk_buffer:
            self._disk_buffer.cleanup()
            self._disk_buffer = None
        self._disk_mode = False

    def get_frame(self, index: int) -> np.ndarray:
        """특정 인덱스의 프레임 반환."""
        if self._disk_mode and self._disk_buffer:
            return self._disk_buffer.get_frame(index)
        if 0 <= index < len(self.frames):
            return self.frames[index]
        return None

    def get_frame_count(self) -> int:
        """총 프레임 수 반환."""
        if self._disk_mode and self._disk_buffer:
            return self._disk_buffer.get_frame_count()
        return len(self.frames)

    def load_video(self, path: str) -> tuple:
        """
        비디오 파일을 읽어 프레임 리스트와 FPS 반환.
        항상 RAM 리스트로 반환 (클립 불러오기 등에 사용).

        Args:
            path: 비디오 파일 경로

        Returns:
            (frames, fps) 튜플

        Raises:
            IOError: 파일을 열 수 없는 경우
        """
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise IOError(f"비디오 파일을 열 수 없습니다: {path}")

        fps = int(cap.get(cv2.CAP_PROP_FPS))
        if fps <= 0:
            fps = 30

        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)

        cap.release()

        if not frames:
            raise IOError(f"비디오에서 프레임을 읽을 수 없습니다: {path}")

        return frames, fps

    def insert_frames(self, position: int, new_frames: list):
        """
        지정한 위치에 프레임들 삽입.
        기존 프레임과 해상도가 다르면 자동으로 리사이즈.

        Args:
            position: 삽입할 위치 인덱스
            new_frames: 삽입할 프레임 리스트 (numpy 배열)
        """
        if not new_frames:
            return

        # 해상도 맞추기
        ref_frame = self.get_frame(0)
        if ref_frame is not None:
            target_h, target_w = ref_frame.shape[:2]
            resized = []
            for f in new_frames:
                if f.shape[0] != target_h or f.shape[1] != target_w:
                    f = cv2.resize(f, (target_w, target_h),
                                   interpolation=cv2.INTER_LANCZOS4)
                resized.append(f)
            new_frames = resized

        if self._disk_mode and self._disk_buffer:
            self._disk_buffer.insert_frames(position, new_frames)
        else:
            position = max(0, min(position, len(self.frames)))
            self.frames[position:position] = new_frames

    def delete_segment(self, start: int, end: int):
        """
        지정 구간의 프레임 삭제 (start, end 포함).

        Args:
            start: 시작 프레임 인덱스
            end: 끝 프레임 인덱스 (포함)

        Returns:
            삭제된 프레임 수
        """
        if self._disk_mode and self._disk_buffer:
            return self._disk_buffer.delete_segment(start, end)

        if start < 0 or end < start or start >= len(self.frames):
            return 0

        end = min(end, len(self.frames) - 1)
        count = end - start + 1
        del self.frames[start:end + 1]
        return count

    def get_all_frames(self) -> list:
        """모든 프레임 반환 (내보내기용). 디스크 모드에서는 디스크에서 로드."""
        if self._disk_mode and self._disk_buffer:
            return self._disk_buffer.get_all_frames()
        return self.frames

    def get_all_frames_generator(self):
        """프레임 제너레이터 (내보내기용, 메모리 효율적)."""
        if self._disk_mode and self._disk_buffer:
            yield from self._disk_buffer.get_all_frames_generator()
        else:
            yield from self.frames

    def get_estimated_memory_mb(self) -> float:
        """현재 프레임들의 추정 메모리 사용량 (MB). 디스크 모드에서는 디스크 사용량."""
        if self._disk_mode and self._disk_buffer:
            return self._disk_buffer.get_estimated_disk_mb()

        if not self.frames:
            return 0.0
        sample = self.frames[0]
        bytes_per_frame = sample.nbytes
        total_bytes = bytes_per_frame * len(self.frames)
        return total_bytes / (1024 * 1024)

    def get_storage_label(self) -> str:
        """현재 저장 모드 라벨."""
        if self._disk_mode:
            return "디스크"
        return "메모리"
