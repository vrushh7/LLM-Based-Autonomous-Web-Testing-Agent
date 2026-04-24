# AI Testing Agent - Complete Setup Guide

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation Methods](#installation-methods)
3. [Configuration](#configuration)
4. [Running the Application](#running-the-application)
5. [Usage Examples](#usage-examples)
6. [Troubleshooting](#troubleshooting)
7. [Architecture Deep Dive](#architecture-deep-dive)

---

## Prerequisites

### Required Software
- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Node.js 16+** (optional, for frontend development) - [Download](https://nodejs.org/)
- **Git** - [Download](https://git-scm.com/)

### Optional but Recommended
- **Docker & Docker Compose** - [Download](https://www.docker.com/)
- **VS Code** with Python extension

---

## Installation Methods

### Method 1: Local Development Setup (Recommended for Development)

#### Step 1: Install Ollama

**macOS:**
```bash
brew install ollama
# or
curl -fsSL https://ollama.com/install.sh | sh
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download installer from https://ollama.com/download

#### Step 2: Pull LLM Model

```bash
# Start Ollama (if not running as service)
ollama serve

# In a new terminal, pull the model
ollama pull llama3.2:3b

# For better quality (larger model):
ollama pull llama3.1:8b
```

#### Step 3: Clone and Setup Project

```bash
# Clone repository
git clone <your-repo-url>
cd ai-testing-agent

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install Python dependencies
cd backend
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
playwright install-deps  # Install system dependencies
```

#### Step 4: Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env if needed (optional)
nano .env
```

#### Step 5: Run the Application

**Terminal 1 - Ollama (if not running as service):**
```bash
ollama serve
```

**Terminal 2 - Backend:**
```bash
cd backend
python main.py
# or
uvicorn main:app --reload --port 8000
```

**Terminal 3 - Frontend:**
```bash
cd frontend
python -m http.server 3000
# or use any static file server
```

**Access the application:**
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

### Method 2: Docker Deployment (Easiest)

#### Step 1: Install Docker

Follow instructions at https://docs.docker.com/get-docker/

#### Step 2: Build and Run

```bash
cd ai-testing-agent

# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up -d

# View logs
docker-compose logs -f
```

#### Step 3: Pull Model in Ollama Container

```bash
# Execute command in Ollama container
docker exec -it ai-testing-ollama ollama pull llama3.2:3b
```

#### Step 4: Access Application

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

#### Stop Services

```bash
docker-compose down

# To remove volumes as well
docker-compose down -v
```

---

## Configuration

### Environment Variables

Edit `backend/.env` to customize:

```env
# LLM Settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b  # or llama3.1:8b for better quality
OLLAMA_TIMEOUT=120

# Browser Settings
BROWSER_HEADLESS=true  # Set to false to see browser
BROWSER_TIMEOUT=30000  # 30 seconds

# Test Settings
MAX_TEST_STEPS=20
SCREENSHOT_ON_FAILURE=true
SCREENSHOT_ON_SUCCESS=false

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Model Selection

Different models offer different trade-offs:

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| llama3.2:3b | 2GB | Fast | Good | Development, quick tests |
| llama3.1:8b | 4.7GB | Medium | Better | Production, complex tests |
| mistral:7b | 4.1GB | Medium | Good | Alternative option |

---

## Running the Application

### Quick Start

```bash
# 1. Start Ollama (if not running)
ollama serve

# 2. Start Backend
cd backend
python main.py

# 3. Start Frontend
cd frontend
python -m http.server 3000

# 4. Open browser
open http://localhost:3000
```

### Verify Setup

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check backend health
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "ollama_connected": true,
  "playwright_ready": true,
  "timestamp": "2024-02-03T10:30:00"
}
```

---

## Usage Examples

### Example 1: Simple Page Verification

**Instruction:**
```
Go to https://example.com and verify the page title contains "Example Domain"
```

**What happens:**
1. LLM generates test plan with navigate + assert steps
2. Browser opens example.com
3. Page title is checked
4. Result: ✅ PASSED

---

### Example 2: Search Functionality

**Instruction:**
```
Open Google, search for "Playwright automation", and verify at least 5 results appear
```

**Generated Steps:**
1. Navigate to google.com
2. Fill search box with "Playwright automation"
3. Click search button
4. Wait for results to load
5. Assert result count >= 5

---

### Example 3: Form Submission

**Instruction:**
```
Go to https://httpbin.org/forms/post, fill in customer name as "John Doe", email as "john@example.com", and submit the form
```

**Generated Steps:**
1. Navigate to form page
2. Fill name field
3. Fill email field
4. Click submit button
5. Wait for response
6. Verify submission success

---

### Example 4: Complex User Flow

**Instruction:**
```
Navigate to GitHub, search for "playwright", click the first repository result, and verify the repository name is visible
```

**This demonstrates:**
- Multi-step navigation
- Dynamic element interaction
- Element visibility assertions

---

## Troubleshooting

### Issue: Ollama not connecting

**Solution:**
```bash
# Check if Ollama is running
ps aux | grep ollama

# Start Ollama
ollama serve

# Test connection
curl http://localhost:11434/api/tags
```

---

### Issue: Playwright browser not launching

**Solution:**
```bash
# Reinstall browsers
playwright install chromium

# Install system dependencies (Linux)
playwright install-deps chromium

# On WSL2, you may need to install additional packages
sudo apt-get install libgbm1
```

---

### Issue: Model not found

**Solution:**
```bash
# List installed models
ollama list

# Pull the model
ollama pull llama3.2:3b

# Verify it's available
ollama list
```

---

### Issue: CORS errors in frontend

**Solution:**
Update `backend/config.py`:
```python
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",  # Add this if testing from API docs
]
```

---

### Issue: Tests timing out

**Solution:**
1. Increase timeout in `.env`:
```env
BROWSER_TIMEOUT=60000  # 60 seconds
OLLAMA_TIMEOUT=180  # 3 minutes
```

2. Or simplify your test instruction to be more specific

---

### Issue: Selectors not found

**Symptoms:** Test fails with "Element not found"

**Solution:**
1. Set `BROWSER_HEADLESS=false` to see what's happening
2. Add wait steps in your instruction:
```
Go to example.com, wait 2 seconds, then click the button
```

3. The LLM will learn to add appropriate waits

---

## Architecture Deep Dive

### Request Flow

```
1. User enters instruction
   ↓
2. Frontend sends POST to /api/test/execute
   ↓
3. Backend receives request
   ↓
4. LLM Service calls Ollama
   ↓
5. Ollama generates JSON test plan
   ↓
6. Test Executor launches Playwright
   ↓
7. Each step is executed sequentially
   ↓
8. Results collected (screenshots, logs)
   ↓
9. Report generated and stored
   ↓
10. Frontend displays results
```

### Component Communication

```
┌─────────────┐
│   Browser   │ ← Playwright controls
└──────┬──────┘
       │
┌──────▼──────────────┐
│  Test Executor      │
│  - Execute steps    │
│  - Capture screens  │
│  - Handle errors    │
└──────┬──────────────┘
       │
┌──────▼──────────────┐
│  FastAPI Backend    │
│  - Orchestration    │
│  - API endpoints    │
└──────┬──────────────┘
       │
┌──────▼──────────────┐
│  LLM Service        │
│  - Prompt building  │
│  - JSON parsing     │
└──────┬──────────────┘
       │
┌──────▼──────────────┐
│  Ollama (LLM)       │
│  - Intent parsing   │
│  - Test generation  │
└─────────────────────┘
```

### Data Flow

**Input:**
```json
{
  "instruction": "Test login with wrong password",
  "url": "https://example.com/login"
}
```

**LLM Output:**
```json
{
  "test_name": "Login Failure Test",
  "steps": [
    {"action": "navigate", "url": "...", "description": "..."},
    {"action": "fill", "selector": "...", "value": "...", "description": "..."},
    {"action": "click", "selector": "...", "description": "..."},
    {"action": "assert", "selector": "...", "expected": "...", "description": "..."}
  ]
}
```

**Final Report:**
```json
{
  "test_id": "uuid",
  "status": "PASSED",
  "duration_ms": 3450,
  "steps_executed": [...],
  "screenshots": [...]
}
```

---

## Performance Optimization

### For Faster Execution

1. **Use smaller model:**
```bash
ollama pull llama3.2:3b  # Faster than 8b
```

2. **Reduce browser overhead:**
```env
BROWSER_HEADLESS=true
SCREENSHOT_ON_SUCCESS=false
```

3. **Optimize selectors:**
Write specific selectors in instructions:
```
Click the button with id="submit-btn"
```

### For Better Accuracy

1. **Use larger model:**
```bash
ollama pull llama3.1:8b
```

2. **Be more specific:**
Instead of: "test the login"
Use: "Go to /login, enter username 'test', password 'wrong', click submit, verify error message appears"

---

## Next Steps

1. ✅ Run the example tests
2. ✅ Try your own test instructions
3. ✅ Review the generated test plans (use Validate button)
4. ✅ Explore the API documentation at /docs
5. ✅ Read the code to understand how it works
6. ✅ Contribute improvements!

---

## Additional Resources

- [Playwright Documentation](https://playwright.dev/python/)
- [Ollama Documentation](https://ollama.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LLaMA Models](https://ollama.com/library/llama3.2)

---

## Getting Help

If you encounter issues:

1. Check the logs:
```bash
# Backend logs
tail -f backend/logs/*.log

# Docker logs
docker-compose logs -f backend
```

2. Enable debug logging:
```env
LOG_LEVEL=DEBUG
```

3. Test components individually:
```bash
# Test Ollama
curl http://localhost:11434/api/tags

# Test Playwright
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print('OK')"
```

4. Open an issue on GitHub with:
   - Error message
   - System info (OS, Python version)
   - Steps to reproduce

---

**Happy Testing! 🚀**
