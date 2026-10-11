@echo off
cd /d "%~dp0"
pnpm dev
if errorlevel 1 pause
