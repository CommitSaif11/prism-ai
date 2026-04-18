@echo off
echo ========================================================
echo PRISM Deployment Script (Windows)
echo ========================================================

echo.
echo [1/3] Building React Frontend...
cd frontend
call npm install
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Frontend build failed!
    exit /b %errorlevel%
)
cd ..

echo.
echo [2/3] Installing Python Dependencies...
cd backend
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Backend dependency installation failed!
    exit /b %errorlevel%
)

echo.
echo [3/3] Launching Production Server...
echo The application will be available at http://localhost:8000
echo Setting up environment variables...
if not exist ".env" (
    echo HF_TOKEN=hf_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX > .env
    echo [WARNING] Created a dummy .env file. Please edit backend\.env with a real HuggingFace token for AI capabilities.
)

python api.py
cd ..
