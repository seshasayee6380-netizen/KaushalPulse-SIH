@echo off
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8010" ^| findstr "LISTENING"') do taskkill /PID %%P /F
