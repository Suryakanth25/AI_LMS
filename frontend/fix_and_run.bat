@echo off
cd /d "c:\Users\ABDUL AZIZ A.R\OneDrive\Documents\Desktop\AI_LMS\obe-frontend"
echo Clearing Babel cache...
del /q %USERPROFILE%\AppData\Local\Temp\metro-cache
echo Starting Expo with cleared cache...
npx expo start --clear
pause
