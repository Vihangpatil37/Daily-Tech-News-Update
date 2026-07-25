@echo off
echo Starting Daily Tech News Update...
cd /d "c:\Users\vihan\OneDrive\Desktop\FILE"

:: Run the main pipeline (which now uses Gmail SMTP instead of Resend)
python -m app.main

echo.
echo Finished! Check your inbox.
:: Pause briefly so you can see if there are any errors if you run this manually
timeout /t 5 >nul
