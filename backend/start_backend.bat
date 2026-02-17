@echo off
echo Starting Council Backend...
"%USERPROFILE%\miniconda3\envs\council\python.exe" -s -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
