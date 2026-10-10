@echo off
rem One-step start for Windows: double-click start.bat  (safe to re-run; see README "Quick start")
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "CHAT_MODEL=qwen3:4b-instruct-2507-q4_K_M"
set "EMBED_MODEL=nomic-embed-text"
set "URL=http://localhost:8000"

echo.
echo ==^> Checking Docker and Ollama
docker info >nul 2>&1 || (set "MSG=Docker is not running. Start Docker Desktop, wait until it says 'running', then run start.bat again." & goto :fail)
where ollama >nul 2>&1 || (set "MSG=Ollama is not installed. Get it from https://ollama.com/download, then run start.bat again." & goto :fail)
curl -sf http://127.0.0.1:11434/api/tags >nul 2>&1 || (set "MSG=Ollama is not running. Start the Ollama app from the Start menu, then run start.bat again." & goto :fail)

echo.
echo ==^> Preparing .env
if not exist .env (
  copy /y .env.example .env >nul
  echo Created .env from .env.example
)
set "DB_RUNNING="
for /f %%i in ('docker compose ps -q db 2^>nul') do set "DB_RUNNING=%%i"
if not defined DB_RUNNING (
  findstr /x /c:"DB_HOST_PORT=5432" .env >nul && (
    netstat -an | findstr /r /c:"127.0.0.1:5432 .*LISTENING" /c:"0.0.0.0:5432 .*LISTENING" >nul && (
      powershell -NoProfile -Command "(Get-Content .env) -replace '^DB_HOST_PORT=5432$','DB_HOST_PORT=5433' | Set-Content .env"
      echo Port 5432 is in use on this machine; the database container will use 5433 instead.
    )
  )
)

echo.
echo ==^> Pulling models (skipped if already present)
for %%m in (%CHAT_MODEL% %EMBED_MODEL%) do (
  ollama list | findstr /b /c:"%%m" >nul || ollama pull %%m || (set "MSG=Could not pull %%m. Check your internet connection." & goto :fail)
)
ollama create lenny-qwen3-4b -f ollama\Modelfile >nul 2>&1 || (set "MSG=Could not create the local chat model. Run: ollama create lenny-qwen3-4b -f ollama\Modelfile" & goto :fail)
echo Local chat model lenny-qwen3-4b is ready (8192 context, for the Agent SDK path).

echo.
echo ==^> Building and starting the app (first run takes a few minutes)
docker compose up -d --build || (set "MSG=docker compose up failed. See the messages above." & goto :fail)

echo.
echo ==^> Waiting for the API
for /l %%i in (1,1,60) do (
  curl -sf http://127.0.0.1:8000/api/v1/ready >nul 2>&1 && goto :ready
  ping -n 3 127.0.0.1 >nul
)
set "MSG=The API did not become ready. Run: docker compose logs api" & goto :fail

:ready
echo.
echo ==^> Loading transcripts (first run ~10 min with a GPU; later runs skip unchanged episodes)
for /l %%a in (1,1,2) do (
  docker compose exec -T api python -m app.ingest > "%TEMP%\lenny_ingest.txt" 2>&1
  findstr /v /c:"\"level\"" "%TEMP%\lenny_ingest.txt"
  findstr /r /c:"^failures  *0" "%TEMP%\lenny_ingest.txt" >nul && goto :done
  if %%a==1 echo Some episodes failed ^(Ollama was busy^); retrying only those.
)

:done
del "%TEMP%\lenny_ingest.txt" >nul 2>&1
echo.
echo ==^> Ready: %URL%
echo Tip for small GPUs: see README "Performance on small GPUs" for faster answers.
start "" "%URL%"
echo.
pause
exit /b 0

:fail
echo.
echo ERROR: !MSG!
echo.
pause
exit /b 1
