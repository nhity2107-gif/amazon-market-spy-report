@echo off
python amazon_market_spy.py scan --sources input\links.csv --output output --zipcode 10001
if errorlevel 1 exit /b %errorlevel%
python amazon_market_spy.py trend --output output
if errorlevel 1 exit /b %errorlevel%
python amazon_market_spy.py publish-report --output output
if errorlevel 1 exit /b %errorlevel%
if defined LARK_WEBHOOK_URL python amazon_market_spy.py notify-lark --output output
start "" "output\top_opportunities.html"
