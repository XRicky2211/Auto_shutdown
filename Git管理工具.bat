@echo off
title Auto Shutdown Git 管理工具 - 推送/拉取/分支/回退
"%ProgramFiles%\PowerShell\7\pwsh.exe" -ExecutionPolicy Bypass -NoLogo -File "%~dp0git-manager.ps1"
pause
