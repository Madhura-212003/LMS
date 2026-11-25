# Run Admiezo in VS Code on Windows

Open the **admiezo-lms** folder itself in VS Code, so backend, frontend and .vscode are directly beneath the opened folder.

## Start on this computer

The Python environment, installed packages, frontend dependencies and local database are already present. The environment currently reuses the tested Python packages installed on this machine because the package server could not be reached. It is a development convenience; a new machine should install the locked packages into its own isolated environment as below.

1. Press **Ctrl+Shift+P**.
2. Choose **Tasks: Run Task**.
3. Select **Admiezo: Run all**.
4. Wait for the backend and Next.js ready messages in the split terminals.
5. Open **http://127.0.0.1:3000/lms/home** in your browser.

The task applies pending local migrations, then starts Django on 8017, the frontend on 3000, and the quiz-expiry worker. It explicitly uses development mode and the local SQLite database. It does not seed/reset data or start a cloud deployment. No VS Code extension is needed to run these tasks.

Use your existing local login, for example student@admiezo.demo, teacher@admiezo.demo or admin@admiezo.demo, with its existing password. Passwords are not stored in this file. If you freshly extract the release, initialize the development samples as described below.

To stop everything, use **Ctrl+Shift+P > Tasks: Terminate Task**, and terminate the three Admiezo service tasks. Do this before running another copy; ports 3000 and 8017 must be free. Do not stop unrelated processes just because they use a matching port.

## First setup on a new Windows computer

Install Python 3.11+ and Node.js 20.9+ from their official sources, then restart VS Code so both commands are on PATH. Production uses the separate Linux deployment procedure.

In the VS Code PowerShell terminal from the project root:

```powershell
python -m venv backend/.venv
& ./backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
Push-Location frontend
npm.cmd ci
Pop-Location
& ./backend/.venv/Scripts/python.exe backend/manage.py migrate
# Only for a new disposable development database:
& ./backend/.venv/Scripts/python.exe backend/manage.py seed_demo
& ./backend/.venv/Scripts/python.exe backend/manage.py seed_features
```

The seed command prints generated passwords for newly created accounts; existing accounts/passwords are retained. Keep that terminal output private. Then run **Admiezo: Run all**.

## Optional real providers

For real AI generation, copy backend/.env.example to backend/.env and supply an institution Gemini model/key. Never commit keys. Missing AI configuration returns an explicit error. Production SSO, private storage, scanner, complete execution and institutional video are configured through deploy/GO-LIVE-CHECKLIST.md; starting VS Code alone does not provision those services. Local development permits the bounded Python teaching interpreter, not all production language/runtime capabilities.

## Common problems

- **Run Task does nothing:** close any open file/folder selection dialog first. The project should already show backend, frontend and .vscode in Explorer. Then use Ctrl+Shift+P > Tasks: Run Task > Admiezo: Run all. The separate Go Live button is for a static Live Server extension and does not start this application.
- **Python interpreter missing:** run the first setup commands and select backend/.venv/Scripts/python.exe if using the optional Microsoft Python extension.
- **npm.ps1 blocked:** the supplied task uses npm.cmd; terminal commands above do too. No execution-policy change is needed.
- **Port in use:** stop the earlier Admiezo task/preview you started, then run the task once.
- **Module not found:** reinstall requirements.lock into the selected environment. On this offline workstation the existing tested system packages are exposed through the project environment.
- **Backend unavailable:** inspect the Backend task terminal; use http://127.0.0.1:8017/api/lms/health/ready after it starts.
- **Blank frontend after switching between dev/build:** stop the frontend first, then restart the intended task. Do not run a production build while Next.js dev is using the same .next directory.

Task configuration follows the official [VS Code tasks documentation](https://code.visualstudio.com/docs/debugtest/tasks).
