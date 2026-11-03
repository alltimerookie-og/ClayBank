# Claybank — Developer Setup

This guide lets you clone `aqib`, install Claybank, run the Flet frontend locally on desktop, launch live previews on an Android device via the official Flet app, and verify the test suite. It assumes no prior knowledge of the project.

## Prerequisites

Inspect these before you start:

- **Python 3.12.x** — verified on this machine with `python --version` → `Python 3.12.10`. `pyproject.toml` declares `requires-python = ">=3.12"`. Use 3.12; 3.13 is not verified.
- **pip** + **venv** — both ship with Python 3.12. Run `python -m pip --version` to check. `venv` is the stdlib virtual-env tool.
- **Git** — any recent version. Verified command used in this guide: `git clone --branch aqib https://github.com/alltimerookie-og/ClayBank.git`.
- **Flet 1.0.5** — `pip show flet` should report `Version: 1.0.5` (pinned in `pyproject.toml: dependencies`).
- **OS** — Windows 10/11, macOS 13+, or Linux (x64). Flet's desktop preview works on all three.
- **Android Device (Optional, for mobile live preview)** — Android phone with the official **Flet** app installed from Google Play Store, connected to the same local Wi-Fi network as your development machine.
- **Dev tools** — `jsonschema>=4.21` + `referencing` for `Docs/api/test_contract.py`, `pytest` for the frontend suite. `pyrefly` is configured via `pyrefly.toml: search-path = [".", "app"]` if you want static analysis; it is not required to run the app.

Do not invent version requirements. If `python --version` is not 3.12, install 3.12 and re-check before continuing.

## 1. Clone the repository

From any empty parent folder:

```powershell
git clone --branch aqib https://github.com/alltimerookie-og/ClayBank.git
cd ClayBank
```

You are now on branch `aqib`.

## 2. Set up virtual environment

**Windows PowerShell (verified):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

If PowerShell blocks scripts, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for that session, or use `.\.venv\Scripts\activate.bat`.

> **Note on reusing or troubleshooting `.venv` on Windows:**
>
> - If you already have an existing, working virtual environment (e.g. in `.venv`), you do not need to recreate it. Simply activate it directly using `.\.venv\Scripts\Activate.ps1`.
> - If attempting to delete or recreate `.venv` fails with `PermissionError`, `Access is denied`, or file lock errors on `.\.venv\Scripts\python.exe`, this is typically caused by an open terminal, active VS Code Python extension instance, or background Flet process holding an open handle to the binary. To resolve: terminate running Python/Flet processes or VS Code terminals, or simply reuse the existing `.venv` without re-running `python -m venv .venv`.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python --version
```

## 3. Install dependencies

Inside the activated venv, from the repo root:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install "jsonschema>=4.21" referencing pytest
```

> **Important notes on dependencies:**
>
> - In PowerShell, quote dependency specifiers with comparison operators (e.g. `"jsonschema>=4.21"`) to prevent PowerShell from misinterpreting `>` as a file redirection operator.
> - `python -m pip install -e .` installs `claybank` in editable mode. `pyproject.toml` explicitly configures setuptools package discovery (`[tool.setuptools.packages.find]` including only `app` and excluding `tests`, `Docs`, and `PrototypingFiles`) to eliminate flat-layout ambiguity.
> - Verify installation:
>
>   ```powershell
>   pip show flet
>   python -c "import flet; import app.app; print('ClayBank imports successfully')"
>   ```

## 4. Run the application on Desktop

Run the application using the verified entry point:

```powershell
flet run main.py
```

*(Note: Running `flet run` from the repository root also resolves to `main.py` automatically.)*

- `main.py` initializes `ClayBankApp(has_seen_onboarding=True)` and calls `app.transition_to_shell()`, opening directly to the core application shell (`AppShellLayout`).
- A desktop window opens displaying the four primary tabs: **Inbox**, **Folders**, **Search**, and **Settings**.
- Add Link sheet slides up from the Inbox header's Add action (`+`). Fixtures in `Docs/api/fixtures/*.json` back saves and search when no backend is running.
- To stop the application: close the Flet window or press `Ctrl+C` in the terminal.

### Desktop troubleshooting:

- `No module named 'flet'` → Virtual environment is not activated: re-run `.\.venv\Scripts\Activate.ps1` and verify `pip show flet`.
- `flet: command not found` → Virtual environment `Scripts/` folder is not on your PATH: activate `.venv`.
- `Port already in use` → Stop any previous `flet run` process or specify a different port: `flet run --port 8551 main.py`.

## 5. Live preview on Android with the Flet app

You can run ClayBank live on your physical Android phone using the official Flet companion app without compiling an APK.

### Android live preview workflow:

1. **Install the Flet App:** On your Android phone, open the **Google Play Store**, search for **Flet** (by Appveyor Systems Inc. / Flet project), and install it.
2. **Connect to the same Wi-Fi:** Ensure your Android phone and development PC are connected to the exact same local Wi-Fi network.
3. **Start the live preview server:** In your terminal on the development PC, run:

   ```powershell
   flet run --android main.py
   ```

4. **Terminal QR code and URL:** Flet starts an internal development server and renders a large ASCII QR code directly in your terminal, along with a LAN URL (e.g. `http://192.168.1.X:8550`).
5. **Open the Flet app on Android:** Launch the Flet app on your phone.
6. **Scan the QR Code:** Tap the camera / QR scanner icon inside the Flet app and scan the QR code displayed in your PC terminal. (Alternatively, manually type the displayed URL into the URL field in the Flet app and tap "Connect").
7. **Live session opens:** ClayBank boots and renders immediately inside the Flet runner on your Android device, transitioning directly to the application shell.
8. **Live reload & mobile testing:** Any UI changes saved in your Python files trigger instant reload or can be refreshed by swiping / reconnecting in the Flet runner. Test touch ergonomics, bottom navigation layout, modal sheets, and theme rendering directly on mobile hardware.

### Android live preview troubleshooting:

- **Windows Console UnicodeEncodeError (`\u2588`):** If rendering the QR code in Windows PowerShell throws `UnicodeEncodeError: 'charmap' codec can't encode character '\u2588'`, your terminal is using a legacy code page (e.g. cp1252). Set UTF-8 encoding before launching:

  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  flet run --android main.py
  ```

- **Windows Defender Firewall prompt:** The first time you launch `flet run --android`, Windows may display a firewall prompt for `python.exe`. You must check **Private networks** and click **Allow access**. If missed, open Windows Defender Firewall with Advanced Security and allow inbound TCP connections for Python on private networks.
- **Phone cannot connect / Connection timed out:**
  - Verify that both devices are on the exact same Wi-Fi subnet.
  - Disable router "AP Isolation", "Guest Mode", or "Client Isolation" settings that prevent Wi-Fi devices from communicating with each other.
  - If your PC has multiple network adapters active (e.g. WSL virtual adapter, Hyper-V, VPN, or VMware adapters), Flet may print the IP of the virtual adapter instead of your Wi-Fi adapter. Find your Wi-Fi IPv4 address using `ipconfig` and enter `http://<YOUR_WIFI_IP>:<PORT>` manually into the Flet Android app.
- **Port collision:** If the default port is occupied, specify an explicit port:

  ```powershell
  flet run --android --port 8555 main.py
  ```

- **Live preview vs Standalone APK notice:**
  - `flet run --android` runs the frontend inside the generic Flet mobile client container for rapid layout and UI prototyping.
  - It is **not** a standalone compiled APK.
  - Native Android OS features—such as background system services, `POST_NOTIFICATIONS` system permissions, native push notification tray alerts, background clipboard monitors, and local compiled GGUF on-device AI models—are not available within the Flet preview runner. (The in-app notification preview in ClayBank operates as a simulated desktop/app preview).

## 6. Run automated verification checks

From the repo root with the virtual environment active:

```powershell
python Docs/api/test_contract.py
python Docs/db/test_schema.py
python -m pytest -q
python -m compileall app tests
```

- `test_contract.py` — Validates that all 22 schemas in `Docs/api/schemas/*.json` conform to JSON Schema Draft 2020-12, fixtures conform, and contract invariants hold.
- `test_schema.py` — Validates SQLite DDL invariants (`0001_core.sql`, `0002_server.sql`, `0003_device.sql`) using stdlib `sqlite3`.
- `pytest -q` — Runs the full test suite (374 passed tests across 52 test files).
- `compileall` — Verifies Python syntax across all application and test source files.

## 7. Configuration

Hackathon shape uses a seeded dev identity without login screens (`Docs/adr/0006`):

- `DEV_TOKEN` — `Authorization: Bearer <token>` expected by the eventual FastAPI backend.
- `X-Device-Id` — device identifier per request.

Both are placeholders only. Copy `.env.example` → `.env` and fill locally only if a backend is running. Never commit `.env`.

## 8. Known platform restrictions

- Native notification delivery is desktop-preview only (INCONCLUSIVE spike) — guaranteed path is the in-app paste sheet.
- Local GGUF inference requires actual `llama_cpp_python` device runtime.
- Background clipboard reads are forbidden on Android 10+; reads are foreground-timed.

---

Next: `Docs/MANUAL_TESTING.md` — step-by-step manual workflows for every screen.
