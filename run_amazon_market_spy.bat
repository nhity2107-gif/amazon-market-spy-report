@echo off
cd /d C:\Users\OS\amazon_market_spy

echo ======================================
echo Amazon Market Spy - Daily Run
echo ======================================

python amazon_market_spy.py scan --sources input\links.csv --output output --zipcode 10001

python amazon_market_spy.py trend --output output

start output\top_opportunities.html

echo.
echo Finished. Press any key to close.
pause
