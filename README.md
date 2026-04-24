# AI-Powered Autonomous Software Testing Agent

## 🎯 Project Overview

An intelligent testing agent that understands plain English instructions and automatically generates, executes, and reports software test cases using browser automation and LLM technology.

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Node.js 16+ (for Playwright)
- Docker (optional, for deployment)
- 8GB+ RAM (for running Ollama locally)

### Installation

```bash
# Clone and navigate to project
cd ai-testing-agent

# Install Python dependencies
pip install -r backend/requirements.txt

# Install Playwright browsers
playwright install chromium

# Install and run Ollama (for local LLM)
# Visit: https://ollama.ai/download
# After installation:
ollama pull llama3
```

### Running the Application

```bash
# Terminal 1: Start the backend server
cd backend
python main.py

# Terminal 2: Serve the frontend (or open index.html in browser)
cd frontend
python -m http.server 8080
```

Visit: `http://localhost:8080`

### Run locally (one-command)

If you are on Windows PowerShell, the repository includes `start_all.ps1` to create the virtualenv (if needed), start the backend on port 8001 and serve the frontend on port 8000 as background jobs:

```powershell
# from project root
.\start_all.ps1

# show jobs
Get-Job | Format-Table -AutoSize

# stop jobs
Get-Job -Name ait_backend,ait_frontend | Stop-Job
```

Backend API docs will be available at: `http://localhost:8001/docs` and frontend at `http://localhost:8000`.

## 📁 Project Structure

```
ai-testing-agent/
├── backend/
│   ├── main.py                 # FastAPI server
│   ├── llm_service.py          # LLM integration (Ollama)
│   ├── automation_engine.py    # Playwright automation
│   ├── report_generator.py     # Test reporting
│   ├── requirements.txt        # Python dependencies
│   └── config.py               # Configuration settings
├── frontend/
│   ├── index.html              # Main UI
│   ├── style.css               # Styling
│   └── app.js                  # Frontend logic
├── tests/
│   └── test_samples.py         # Sample test cases
├── docs/
│   └── DEVELOPMENT.md          # Development guide
└── README.md
```

## 🛠️ Technology Stack

- **Backend**: Python, FastAPI
- **LLM**: Ollama + LLaMA-3 (8B)
- **Automation**: Playwright
- **Frontend**: HTML/CSS/JavaScript
- **Deployment**: Docker (optional)

## 📖 How It Works

1. User enters a plain English testing instruction
2. Backend sends instruction to LLM (Ollama + LLaMA-3)
3. LLM converts instruction into structured JSON test steps
4. Automation engine executes steps using Playwright
5. Results are captured and formatted into a report
6. Report is displayed to the user with pass/fail status

## 🎓 Development Phases

### Phase 1: Setup ✅
- Environment configuration
- Basic browser automation
- Backend skeleton

### Phase 2: LLM Integration
- Ollama integration
- Prompt engineering
- Natural language → JSON conversion

### Phase 3: Execution Pipeline
- Full automation workflow
- Error handling
- Screenshot capture

### Phase 4: UI & Reporting
- Frontend interface
- Report visualization
- Test history

### Phase 5: Deployment
- Docker containerization
- Cloud deployment
- Production hardening

## 🔧 Configuration

Edit `backend/config.py` to customize:
- LLM model selection
- Browser settings
- API endpoints
- Timeout values

## 📝 Example Usage

**Input:**
```
Open Google, search for "Python testing", and verify results appear
```

**Generated Test Steps:**
```json
{
  "steps": [
    {"action": "navigate", "url": "https://google.com"},
    {"action": "fill", "selector": "input[name='q']", "value": "Python testing"},
    {"action": "click", "selector": "input[type='submit']"},
    {"action": "assert", "type": "visible", "selector": "#search"}
  ]
}
```

## 🤝 Contributing

This is an academic project. For improvements or suggestions, please document them in the issues section.

## 📄 License

MIT License - Academic Project

## 🎯 Academic Significance

This project demonstrates:
- Practical application of LLMs in software engineering
- Integration of AI with traditional automation tools
- Natural language processing for test generation
- Modern full-stack development practices
