@echo off
setlocal
cd /d "%~dp0"

echo ======================================
echo Amazon Market Spy - Daily Run
echo ======================================

echo [1/3] Scanning sources and filling missing Top-15 seller BSR...
python amazon_market_spy.py scan --sources input\links.csv --output output --zipcode 10001 --fetch-category-rank --max-detail-pages 120
if errorlevel 1 goto :failed

echo [2/3] Rebuilding analytics...
python amazon_market_spy.py trend --sources input\links.csv --output output
if errorlevel 1 goto :failed

echo [3/3] Generating Dashboard V3...
python amazon_market_spy.py generate-dashboard-v3 --output output\v3
if errorlevel 1 goto :failed

start "" "output\v3\index.html"

echo.
echo Daily scan completed successfully.
pause
exit /b 0

:failed
echo.
echo Daily scan failed with exit code %errorlevel%.
echo Review the error above before running the next step.
pause
exit /b 1
