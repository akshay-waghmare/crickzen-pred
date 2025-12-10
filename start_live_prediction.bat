@echo off
REM Quick Launch Script for Live Match Prediction (Windows)
REM 
REM Usage: start_live_prediction.bat "MATCH_URL"
REM 
REM Example:
REM   start_live_prediction.bat "https://www.espncricinfo.com/series/big-bash-league-2024-25/..."

echo.
echo ================================================================
echo            BBL LIVE MATCH PREDICTOR LAUNCHER
echo ================================================================
echo.

REM Check if URL provided
if "%~1"=="" (
    echo ERROR: No match URL provided
    echo.
    echo Usage: start_live_prediction.bat "MATCH_URL"
    echo.
    echo Example:
    echo   start_live_prediction.bat "https://www.espncricinfo.com/series/..."
    echo.
    exit /b 1
)

set MATCH_URL=%~1
set MODEL_DIR=%~2
if "%MODEL_DIR%"=="" set MODEL_DIR=./models/champion
set POLL_INTERVAL=%~3
if "%POLL_INTERVAL%"=="" set POLL_INTERVAL=2.0

echo Configuration:
echo    Match URL: %MATCH_URL%
echo    Model Dir: %MODEL_DIR%
echo    Poll Interval: %POLL_INTERVAL%s
echo.

REM Check if model directory exists
if not exist "%MODEL_DIR%" (
    echo ERROR: Model directory not found: %MODEL_DIR%
    exit /b 1
)

REM Check if model file exists
if not exist "%MODEL_DIR%\champion_model.joblib" (
    echo ERROR: Model file not found: %MODEL_DIR%\champion_model.joblib
    exit /b 1
)

echo Model found!
echo.
echo Starting live prediction...
echo.
echo Press Ctrl+C to stop and export results
echo.

REM Run the predictor
python src\run_integrated_prediction.py --match-url "%MATCH_URL%" --model-dir "%MODEL_DIR%" --poll-interval %POLL_INTERVAL%

echo.
echo Prediction session ended
pause
