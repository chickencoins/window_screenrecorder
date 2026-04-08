"""
디스크 기반 프레임 버퍼.
프레임을 임시 디렉토리에 JPEG 파일로 저장하여 RAM 사용을 최소화.
경로 리스트만 메모리에 유지.
"""

import os
import shutil
import tempfile

import cv2
import numpy as np


class DiskFrameBuffer:
    """
    프레임을 디스크에 저장하고 경로 리스트로 관리.

    RAM에는 파일 경로 문자열만 유지하므로,
    1080p 30fps 1시간 녹화 시에도 RAM 사용량은 수 MB 수준.
    디스크 사용량: JPEG 압축으로 프레임당 약 50~200KB (해상도/내용에 따라 다름).
    """

    def __init__(self, temp_dir: str = None, jpeg_quality: int = 95):
        """
        Args:
            temp_dir: 임시 디렉토리 경로. None이면 시스템 임시 디렉토리에 자동 생성.
            jpeg_quality: JPEG 저장 품질 (1-100). 높을수록 화질 좋음, 파일 크기 증가.
        """
        if temp_dir:
            self._temp_dir = temp_dir
            os.makedirs(temp_dir, exist_ok=True)
            self._auto_created = False
        else:
            self._temp_dir = tempfile.mkdtemp(prefix="screenrec_")
            self._auto_created = True

        self._jpeg_quality = jpeg_quality
        self._paths: list = []  # 프레임 파일 경로 리스트
        self._counter = 0  # 파일 이름 카운터 (항상 증가, 삭제 후에도 재사용 안 함)

    @property
    def temp_dir(self) -> str:
        return self._temp_dir

    def __len__(self) -> int:
        return len(self._paths)

    def __getitem__(self, index: int) -> np.ndarray:
        return self.get_frame(index)

    def append(self, frame: np.ndarray):
        """프레임을 디스크에 저장하고 경로 추가."""
        filename = f"frame_{self._counter:08d}.jpg"
        filepath = os.path.join(self._temp_dir, filename)

        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        cv2.imwrite(filepath, frame, encode_params)

        self._paths.append(filepath)
        self._counter += 1

    def get_frame(self, index: int) -> np.ndarray:
        """디스크에서 프레임 읽기."""
        if index < 0 or index >= len(self._paths):
            return None
        frame = cv2.imread(self._paths[index], cv2.IMREAD_COLOR)
        return frame

    def get_frame_count(self) -> int:
        """저장된 프레임 수."""
        return len(self._paths)

    def insert_frames(self, position: int, frames: list):
        """
        지정 위치에 프레임들 삽입.

        Args:
            position: 삽입 위치 인덱스
            frames: numpy 배열 리스트
        """
        position = max(0, min(position, len(self._paths)))
        new_paths = []
        for frame in frames:
            filename = f"frame_{self._counter:08d}.jpg"
            filepath = os.path.join(self._temp_dir, filename)
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
            cv2.imwrite(filepath, frame, encode_params)
            new_paths.append(filepath)
            self._counter += 1

        self._paths[position:position] = new_paths

    def delete_segment(self, start: int, end: int) -> int:
        """
        구간 삭제 (start, end 포함).
        디스크의 파일도 삭제.

        Returns:
            삭제된 프레임 수
        """
        if start < 0 or end < start or start >= len(self._paths):
            return 0

        end = min(end, len(self._paths) - 1)
        count = end - start + 1

        # 디스크에서 파일 삭제
        for i in range(start, end + 1):
            path = self._paths[i]
            if os.path.exists(path):
                os.remove(path)

        del self._paths[start:end + 1]
        return count

    def set_from_frames(self, frames: list):
        """기존 내용을 지우고 프레임 리스트로 새로 설정."""
        self.clear()
        for frame in frames:
            self.append(frame)

    def get_all_frames(self) -> list:
        """모든 프레임을 메모리에 로드하여 반환 (내보내기용)."""
        frames = []
        for path in self._paths:
            frame = cv2.imread(path, cv2.IMREAD_COLOR)
            if frame is not None:
                frames.append(frame)
        return frames

    def get_all_frames_generator(self):
        """메모리 효율적인 프레임 제너레이터 (내보내기용)."""
        for path in self._paths:
            frame = cv2.imread(path, cv2.IMREAD_COLOR)
            if frame is not None:
                yield frame

    def get_estimated_disk_mb(self) -> float:
        """디스크 사용량 추정 (MB)."""
        total = 0
        for path in self._paths:
            if os.path.exists(path):
                total += os.path.getsize(path)
        return total / (1024 * 1024)

    def clear(self):
        """모든 프레임 파일 삭제 및 리스트 초기화."""
        for path in self._paths:
            if os.path.exists(path):
                os.remove(path)
        self._paths.clear()

    def cleanup(self):
        """임시 디렉토리 전체 삭제. 프로그램 종료 시 호출."""
        self.clear()
        if self._auto_created and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)

    def __del__(self):
        """소멸자: 임시 파일 정리."""
        try:
            self.cleanup()
        except Exception:
            pass
