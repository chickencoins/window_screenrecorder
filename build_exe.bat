@echo off
REM Screen Recorder EXE 빌드 스크립트 (Windows)
REM 이 파일을 Windows에서 실행하세요.

echo === Screen Recorder EXE 빌드 ===

REM 가상환경 생성 및 활성화
if not exist venv (
    echo [1/4] 가상환경 생성 중...
    python -m venv venv
)

echo [2/4] 가상환경 활성화 및 패키지 설치...
call venv\Scripts\activate.bat
pip install -r requirements.txt

echo [3/4] PyInstaller로 EXE 빌드 중...
pyinstaller screen_recorder.spec --clean

echo [4/4] 빌드 완료!
echo.
echo 생성된 파일: dist\ScreenRecorder.exe
echo.
pause
