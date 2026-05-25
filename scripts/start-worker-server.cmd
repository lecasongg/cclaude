@echo off
setlocal
set ROOT=%~dp0..
set PYTHONPATH=%ROOT%\..
python "%ROOT%\worker_server.py"
