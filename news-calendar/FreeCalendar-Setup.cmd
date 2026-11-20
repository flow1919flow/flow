@echo off
set "HY_NEWS_SETUP_ROOT=%~dp0"
powershell.exe -NoProfile -Command "& { . ([scriptblock]::Create([IO.File]::ReadAllText((Join-Path $env:HY_NEWS_SETUP_ROOT 'FreeCalendarRunner.ps1')))) -Install -SetKey -SourceRoot $env:HY_NEWS_SETUP_ROOT }"
pause
