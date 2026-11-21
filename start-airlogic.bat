@echo off
cd /d C:\Airlogic\app
echo Starting AirLogic at http://127.0.0.1:8767/index.html
echo Keep this window open while you use the site.
python -m http.server 8767 --bind 127.0.0.1
pause
