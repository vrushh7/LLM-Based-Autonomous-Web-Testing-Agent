# Step-by-Step Tutorial: Building the AI Testing Agent

This tutorial walks you through building the AI Testing Agent from scratch, explaining each component and how they work together.

## Table of Contents

1. [Understanding the Architecture](#understanding-the-architecture)
2. [Phase 1: Environment Setup](#phase-1-environment-setup)
3. [Phase 2: Backend Development](#phase-2-backend-development)
4. [Phase 3: LLM Integration](#phase-3-llm-integration)
5. [Phase 4: Browser Automation](#phase-4-browser-automation)
6. [Phase 5: Frontend Development](#phase-5-frontend-development)
7. [Phase 6: Testing & Debugging](#phase-6-testing--debugging)
8. [Phase 7: Deployment](#phase-7-deployment)

---

## Understanding the Architecture

### High-Level Overview

The AI Testing Agent consists of three main components:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Backend    │────▶│     LLM      │
│  (HTML/JS)   │     │  (FastAPI)   │     │  (Ollama)    │
└──────────────┘     └──────┬───────┘     └──────────────┘
                             │
                             ▼
                     ┌──────────────┐
                     │   Browser    │
                     │ (Playwright) │
                     └──────────────┘
```

### Data Flow

1. **User Input**: User enters a natural language testing instruction
2. **API Request**: Frontend sends instruction to backend
3. **LLM Processing**: Backend sends instruction to LLM for conversion
4. **Test Plan**: LLM returns structured JSON test steps
5. **Execution**: Backend executes test steps using browser automation
6. **Results**: Backend generates report and sends back to frontend
7. **Display**: Frontend displays results to user

---

## Phase 1: Environment Setup

### Step 1.1: Install Prerequisites

**Python 3.9+**
```bash
# Check Python version
python3 --version

# If not installed, visit: https://www.python.org/downloads/
```

**Node.js 16+**
```bash
# Check Node version
node --version

# If not installed, visit: https://nodejs.org/
```

### Step 1.2: Install Ollama

**Why Ollama?**
- Free, local LLM runtime
- Easy to use
- Supports LLaMA-3 model
- No API keys required

**Installation:**

macOS/Linux:
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

Windows:
- Download from https://ollama.ai/download

**Verify:**
```bash
ollama --version
```

### Step 1.3: Download LLaMA-3 Model

```bash
# This downloads ~4GB
ollama pull llama3

# Verify it's installed
ollama list
```

### Step 1.4: Create Project Structure

```bash
mkdir ai-testing-agent
cd ai-testing-agent

# Create directories
mkdir -p backend frontend docs tests
```

---

## Phase 2: Backend Development

### Step 2.1: Set Up Python Environment

```bash
cd backend

# Create requirements.txt
cat > requirements.txt << EOF
fastapi==0.104.1
uvicorn[standard]==0.24.0
playwright==1.40.0
requests==2.31.0
pydantic==2.5.0
python-multipart==0.0.6
Pillow==10.1.0
aiofiles==23.2.1
EOF

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### Step 2.2: Create Configuration Module

**File: `backend/config.py`**

Key configuration areas:
- Server settings (host, port)
- LLM settings (model, temperature)
- Browser settings (headless mode, timeout)
- File paths

```python
# Example configuration
HOST = "0.0.0.0"
PORT = 8000
LLM_MODEL = "llama3"
BROWSER_HEADLESS = False  # Set True for production
```

### Step 2.3: Create Basic FastAPI Server

**File: `backend/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Testing Agent")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "AI Testing Agent API"}

@app.get("/health")
def health():
    return {"status": "healthy"}
```

**Test it:**
```bash
python main.py
# Visit: http://localhost:8000/docs
```

---

## Phase 3: LLM Integration

### Step 3.1: Understanding the LLM Service

The LLM service:
1. Takes natural language input
2. Sends it to Ollama with a specialized prompt
3. Receives structured JSON response
4. Parses and validates the response

### Step 3.2: Create LLM Service Module

**File: `backend/llm_service.py`**

Key components:
- **Prompt Engineering**: The most critical part
- **API Communication**: HTTP calls to Ollama
- **Response Parsing**: Extract JSON from LLM output
- **Error Handling**: Handle malformed responses

### Step 3.3: Prompt Engineering

The prompt is structured to:

1. **Set Context**: "You are an expert testing AI"
2. **Define Task**: Convert instruction to JSON
3. **Provide Schema**: Show exact JSON structure
4. **Give Examples**: Show sample conversions
5. **Set Rules**: Constraints and guidelines

**Example Prompt Structure:**
```
You are an expert software testing AI.
Convert: "Open Google and search for Python"

JSON Structure:
{
  "url": "base URL",
  "steps": [
    {"action": "navigate", "url": "..."},
    {"action": "fill", "selector": "...", "value": "..."},
    ...
  ]
}

Rules:
- Use common CSS selectors
- Keep steps sequential
- Be specific but practical

Return ONLY valid JSON.
```

### Step 3.4: Test LLM Service

```python
# Quick test
from llm_service import llm_service

result = llm_service.generate_test_steps(
    "Open example.com and verify page loads"
)
print(result)
```

---

## Phase 4: Browser Automation

### Step 4.1: Understanding Playwright

**Why Playwright?**
- Modern, fast browser automation
- Supports multiple browsers
- Good async support
- Reliable element selection
- Built-in waiting mechanisms

### Step 4.2: Create Automation Engine

**File: `backend/automation_engine.py`**

Key features:
- Browser lifecycle management
- Step execution
- Screenshot capture
- Error handling

### Step 4.3: Implement Test Actions

**Navigation:**
```python
async def _action_navigate(self, step: Dict):
    url = step.get('url')
    await self.page.goto(url, wait_until='domcontentloaded')
```

**Click:**
```python
async def _action_click(self, step: Dict):
    selector = step.get('selector')
    element = await self.page.wait_for_selector(selector)
    await element.click()
```

**Fill:**
```python
async def _action_fill(self, step: Dict):
    selector = step.get('selector')
    value = step.get('value')
    await self.page.fill(selector, value)
```

**Assert:**
```python
async def _action_assert(self, step: Dict):
    assertion_type = step.get('assertion_type')
    
    if assertion_type == 'visible':
        element = await self.page.wait_for_selector(
            selector, 
            state='visible'
        )
```

### Step 4.4: Test Browser Automation

```python
# Simple test
import asyncio
from automation_engine import automation_engine

test_plan = {
    "url": "https://example.com",
    "steps": [
        {
            "action": "navigate",
            "url": "https://example.com"
        },
        {
            "action": "assert",
            "selector": "h1",
            "assertion_type": "visible"
        }
    ]
}

async def test():
    result = await automation_engine.execute_test_plan(test_plan)
    print(result)

asyncio.run(test())
```

---

## Phase 5: Frontend Development

### Step 5.1: Create HTML Structure

**File: `frontend/index.html`**

Key sections:
- Header with health status
- Input section for instructions
- Results display area
- Test history sidebar

### Step 5.2: Style with CSS

**File: `frontend/style.css`**

Design principles:
- Modern, clean interface
- Color-coded status (green=pass, red=fail)
- Responsive layout
- Smooth animations

### Step 5.3: Implement JavaScript Logic

**File: `frontend/app.js`**

Key functions:

```javascript
// Health check
async function checkHealth() {
    const response = await fetch(`${API_BASE_URL}/health`);
    // Update UI based on response
}

// Run test
async function runTest() {
    const instruction = instructionInput.value;
    
    const response = await fetch(`${API_BASE_URL}/api/test`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ instruction })
    });
    
    const data = await response.json();
    displayResults(data.report);
}

// Display results
function displayResults(report) {
    // Update DOM with test results
}
```

---

## Phase 6: Testing & Debugging

### Step 6.1: Backend Testing

**Test LLM Service:**
```bash
cd backend
python -c "
from llm_service import llm_service
result = llm_service.generate_test_steps('Open Google')
print(result)
"
```

**Test API Endpoints:**
```bash
# Start server
python main.py

# In another terminal
curl http://localhost:8000/health

curl -X POST http://localhost:8000/api/test \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Open example.com"}'
```

### Step 6.2: Integration Testing

**Complete Flow Test:**

1. Start Ollama: `ollama serve`
2. Start Backend: `python backend/main.py`
3. Start Frontend: `python -m http.server 8080` (in frontend/)
4. Open browser: `http://localhost:8080`
5. Run test: "Open example.com and verify page loads"

### Step 6.3: Common Issues & Solutions

**Issue: LLM not responding**
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Pull model again if needed
ollama pull llama3
```

**Issue: Browser not opening**
```bash
# Reinstall browsers
playwright install chromium --with-deps
```

**Issue: CORS errors**
```python
# In main.py, ensure CORS is configured
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific origins
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Phase 7: Deployment

### Step 7.1: Docker Deployment

**Build and Run:**
```bash
# Build image
docker build -t ai-testing-agent .

# Run container
docker run -p 8000:8000 ai-testing-agent
```

### Step 7.2: Docker Compose

**Run all services:**
```bash
docker-compose up -d

# Pull LLM model (first time only)
docker exec -it ai-testing-agent-ollama ollama pull llama3

# View logs
docker-compose logs -f
```

### Step 7.3: Cloud Deployment

**Options:**

1. **AWS EC2**
   - Launch Ubuntu instance
   - Install dependencies
   - Run application

2. **Google Cloud Run**
   - Containerize application
   - Deploy to Cloud Run
   - Configure environment variables

3. **Railway**
   - Connect GitHub repository
   - Auto-deploy on push
   - Easy environment configuration

---

## Best Practices

### LLM Prompt Engineering

1. **Be Specific**: Clear instructions produce better results
2. **Provide Examples**: Show desired output format
3. **Set Constraints**: Define rules and limitations
4. **Handle Errors**: Parse and validate LLM responses

### Browser Automation

1. **Use Reliable Selectors**: Prefer IDs and data attributes
2. **Add Waits**: Wait for elements before interaction
3. **Handle Timeouts**: Set appropriate timeout values
4. **Capture Screenshots**: Take screenshots on failures

### API Design

1. **RESTful Routes**: Follow REST conventions
2. **Error Handling**: Return meaningful error messages
3. **Validation**: Validate all inputs
4. **Documentation**: Use FastAPI auto-docs

### Frontend

1. **User Feedback**: Show loading states
2. **Error Messages**: Display clear error information
3. **Responsive Design**: Work on all screen sizes
4. **Accessibility**: Follow accessibility guidelines

---

## Next Steps

After completing this tutorial, you can:

1. **Add Features:**
   - User authentication
   - Test scheduling
   - Parallel test execution
   - Mobile browser testing
   - API testing support

2. **Improve LLM:**
   - Fine-tune prompts
   - Add few-shot examples
   - Implement feedback loop
   - Use different models

3. **Enhance UI:**
   - Add test templates
   - Implement test editor
   - Create dashboard
   - Add analytics

4. **Production Ready:**
   - Add logging
   - Implement monitoring
   - Set up CI/CD
   - Add security measures

---

## Conclusion

You've now built a complete AI-powered testing agent! This project demonstrates:

- Integration of LLMs with traditional software
- Browser automation with Playwright
- Full-stack web development
- API design and implementation
- Modern deployment practices

**Keep exploring and building!** 🚀
