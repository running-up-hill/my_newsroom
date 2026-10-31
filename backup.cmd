@echo off
rem Runs backup.ps1 without PowerShell script-policy problems:  .\backup.cmd   or   .\backup.cmd -Instance <name>
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup.ps1" %*
