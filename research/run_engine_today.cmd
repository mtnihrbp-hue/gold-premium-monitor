@echo off
rem The forward test's daily line on the workstation (SP_D_HANDOFF.md section 82): called by Task Scheduler,
rem "Gold engine shadow ledger", each evening after 21:00 Tehran. Never sends, never touches production.
cd /d "%USERPROFILE%\Documents\Projects\gold-premium-monitor"
set PY=%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe
echo %DATE% %TIME% >> research\data\engine_today.log
"%PY%" -I -X utf8 -W ignore research\engine_today.py >> research\data\engine_today.log 2>&1
exit /b 0
