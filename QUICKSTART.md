# Quick Start Guide

Get the AI Testing Agent up and running in 5 minutes!

## Prerequisites Check

Before you begin, ensure you have:

- [ ] Python 3.9 or higher installed
- [ ] Node.js 16 or higher (for Playwright)
- [ ] 8GB+ RAM available
- [ ] Terminal/Command Prompt access

## Step-by-Step Setup

### 1. Install Ollama

**macOS/Linux:**
```bash
# Visit https://ollama.ai/download and install
# Or use the following command:
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
- Download installer from https://ollama.ai/download
- Run the installer
- Verify installation: `ollama --version`

### 2. Download LLaMA-3 Model

```bash
ollama pull llama3
```

This will download ~4GB of data. Wait for completion.

### 3. Install Project Dependencies

**Option A: Using setup script (recommended)**
```bash
cd ai-testing-agent
chmod +x setup.sh
./setup.sh
```

**Option B: Manual installation**
```bash
cd ai-testing-agent

# Install Python dependencies
cd backend
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

cd ..
```

### 4. Start Ollama Server

```bash
# In a new terminal window
ollama serve
```

Keep this terminal running.

### 5. Start Backend Server

```bash
# In a new terminal window
cd ai-testing-agent/backend
python main.py
```

You should see:
```
╔══════════════════════════════════════════════════════════╗
║        AI-Powered Autonomous Testing Agent              ║
║  Server running at: http://0.0.0.0:8000                 ║
╚══════════════════════════════════════════════════════════╝
```

Keep this terminal running.

### 6. Start Frontend Server

```bash
# In a new terminal window
cd ai-testing-agent/frontend
python -m http.server 8080
```

### 7. Open the Application

Open your browser and navigate to:
```
http://localhost:8080
```

You should see the AI Testing Agent interface!

## Your First Test

### Test 1: Simple Navigation

1. In the instruction box, type:
   ```
   Open example.com and verify the page loads
   ```

2. Click "Run Test"

3. Watch as:
   - The LLM converts your instruction to test steps
   - A browser window opens and navigates to example.com
   - Results are displayed with pass/fail status

### Test 2: Google Search

Try this instruction:
```
Open Google, search for "Python testing", and verify results appear
```

### Test 3: Form Interaction

Try this instruction:
```
Navigate to GitHub, click on Sign in, and verify login form is visible
```

## Troubleshooting

### "LLM Unavailable" Warning

**Problem**: The health status shows "LLM Unavailable"

**Solution**:
1. Check if Ollama is running: `ollama serve`
2. Verify LLaMA-3 is installed: `ollama list`
3. If not listed: `ollama pull llama3`

### "Backend Offline" Error

**Problem**: Frontend can't connect to backend

**Solution**:
1. Verify backend is running on port 8000
2. Check for errors in backend terminal
3. Try restarting: `python main.py`

### Browser Not Opening

**Problem**: Playwright browser doesn't launch

**Solution**:
1. Reinstall browsers: `playwright install chromium`
2. Check for system dependency issues
3. Try running with headless mode disabled in `config.py`

### Port Already in Use

**Problem**: Port 8000 or 8080 is already in use

**Solution**:
```bash
# Change backend port in backend/config.py
PORT = 8001

# Change frontend port
python -m http.server 8081
```

## Architecture Overview

```
┌─────────────────┐
│   Frontend UI   │ (Port 8080)
│  HTML/CSS/JS    │
└────────┬────────┘
         │
         │ HTTP POST /api/test
         ▼
┌─────────────────┐
│  Backend API    │ (Port 8000)
│    FastAPI      │
└────────┬────────┘
         │
         ├─────────────┐
         │             │
         ▼             ▼
┌─────────────┐  ┌─────────────┐
│ LLM Service │  │ Automation  │
│   Ollama    │  │  Playwright │
│  LLaMA-3    │  │  (Browser)  │
└─────────────┘  └─────────────┘
```

## Next Steps

### Learn More

- Read [README.md](README.md) for project overview
- Check [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed development guide
- Explore [tests/test_samples.py](tests/test_samples.py) for more test examples

### Customize

- Edit `backend/config.py` to change settings
- Modify LLM prompt in `backend/llm_service.py`
- Customize UI in `frontend/style.css`

### Advanced Testing

Try these advanced test scenarios:

1. **Multi-step workflow:**
   ```
   Navigate to Wikipedia, search for Artificial Intelligence, 
   click the first result, and verify the article loads
   ```

2. **Form filling:**
   ```
   Go to a contact form, fill in name and email fields, 
   click submit, and verify confirmation message
   ```

3. **Navigation verification:**
   ```
   Open YouTube, search for Python tutorials, 
   click on the first video, and verify video page loads
   ```

## Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review error messages in browser console (F12)
3. Check backend logs in terminal
4. Ensure all prerequisites are met
5. Try running sample tests from `tests/test_samples.py`

## System Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 8GB
- Disk: 10GB free space

**Recommended:**
- CPU: 4+ cores
- RAM: 16GB
- Disk: 20GB free space
- SSD storage

## Stopping the Application

To stop all services:

1. Press `Ctrl+C` in each terminal window:
   - Frontend terminal
   - Backend terminal
   - Ollama terminal (if running)

2. Close the browser

3. All test data is saved in:
   - Reports: `backend/reports/`
   - Screenshots: `backend/screenshots/`

---

**Congratulations!** 🎉 You've successfully set up the AI Testing Agent. Happy testing!
