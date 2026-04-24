# Development Guide

## Project Structure

```
ai-testing-agent/
├── backend/                    # Python FastAPI backend
│   ├── main.py                # Main server and API endpoints
│   ├── llm_service.py         # LLM integration (Ollama)
│   ├── automation_engine.py   # Playwright browser automation
│   ├── report_generator.py    # Test reporting logic
│   ├── config.py              # Configuration settings
│   ├── requirements.txt       # Python dependencies
│   ├── screenshots/           # Auto-generated screenshots
│   └── reports/               # Auto-generated test reports
├── frontend/                   # Web UI
│   ├── index.html             # Main HTML page
│   ├── style.css              # Styling
│   └── app.js                 # Frontend JavaScript
├── tests/                      # Test files
│   └── test_samples.py        # Sample test cases
├── docs/                       # Documentation
│   └── DEVELOPMENT.md         # This file
└── README.md                   # Project overview
```

## Development Phases

### Phase 1: Environment Setup ✅

**Objective**: Set up the development environment and verify all tools are working.

**Steps**:

1. **Install Python 3.9+**
   ```bash
   python --version  # Should be 3.9 or higher
   ```

2. **Install Node.js** (for Playwright)
   ```bash
   node --version  # Should be 16 or higher
   ```

3. **Install Ollama**
   - Visit: https://ollama.ai/download
   - Download and install for your OS
   - Verify installation:
     ```bash
     ollama --version
     ```

4. **Pull LLaMA-3 Model**
   ```bash
   ollama pull llama3
   ollama list  # Verify llama3 is listed
   ```

5. **Install Python Dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

6. **Install Playwright Browsers**
   ```bash
   playwright install chromium
   ```

### Phase 2: Backend Development

**Key Components**:

1. **config.py**: Configuration management
   - Server settings (host, port)
   - LLM settings (model, temperature)
   - Browser settings (headless, timeout)
   - File paths for screenshots and reports

2. **llm_service.py**: LLM Integration
   - Communicates with Ollama API
   - Converts natural language to structured JSON
   - Handles prompt engineering
   - Error handling and parsing

3. **automation_engine.py**: Browser Automation
   - Uses Playwright for browser control
   - Executes test steps (navigate, click, fill, assert)
   - Captures screenshots on failure
   - Manages browser lifecycle

4. **report_generator.py**: Reporting
   - Generates test reports
   - Formats execution results
   - Saves reports to JSON files
   - Provides history tracking

5. **main.py**: FastAPI Server
   - Exposes REST API endpoints
   - Orchestrates the testing pipeline
   - Handles CORS for frontend
   - Error handling and logging

### Phase 3: Testing the Backend

**Start the Backend Server**:
```bash
cd backend
python main.py
```

**Test Endpoints**:

1. **Health Check**:
   ```bash
   curl http://localhost:8000/health
   ```
   Expected: `{"status": "healthy", "llm_available": true, ...}`

2. **Run a Test**:
   ```bash
   curl -X POST http://localhost:8000/api/test \
     -H "Content-Type: application/json" \
     -d '{"instruction": "Open Google and search for Python"}'
   ```

3. **View API Documentation**:
   - Visit: http://localhost:8000/docs
   - FastAPI provides interactive Swagger docs

### Phase 4: Frontend Development

**Key Components**:

1. **index.html**: UI Structure
   - Input section for test instructions
   - Results section for displaying reports
   - History section for past tests
   - Status indicators

2. **style.css**: Styling
   - Modern, responsive design
   - Color-coded status indicators
   - Smooth animations and transitions

3. **app.js**: Frontend Logic
   - API communication
   - Dynamic UI updates
   - Event handling
   - Error handling

**Running the Frontend**:
```bash
cd frontend
python -m http.server 8080
# OR
npx serve .
```

Visit: http://localhost:8080

### Phase 5: Integration Testing

**Test the Complete Flow**:

1. Start backend: `python backend/main.py`
2. Start frontend: `python -m http.server 8080` (in frontend/)
3. Open browser: http://localhost:8080
4. Enter test instruction: "Open example.com and verify page loads"
5. Click "Run Test"
6. Verify results are displayed

**Common Test Instructions**:

```
1. Simple Navigation:
   "Open example.com and verify the page title"

2. Search Functionality:
   "Go to Google, search for 'Python testing', and verify results appear"

3. Form Interaction:
   "Navigate to GitHub, click Sign in, and verify login form is visible"

4. Multi-step Test:
   "Open example.com, click on More information, and verify the new page loads"
```

## Architecture Deep Dive

### Request Flow

```
User Input (Frontend)
    ↓
POST /api/test (FastAPI)
    ↓
LLM Service (Ollama + LLaMA-3)
    ↓
Test Plan (JSON)
    ↓
Automation Engine (Playwright)
    ↓
Browser Actions
    ↓
Execution Results
    ↓
Report Generator
    ↓
JSON Report
    ↓
Frontend Display
```

### LLM Prompt Engineering

The LLM service uses a carefully crafted prompt to convert natural language to structured JSON:

**Prompt Structure**:
1. System context (you are an expert testing AI)
2. User instruction
3. JSON schema definition
4. Available actions and rules
5. Example conversion
6. Request for conversion

**Key Considerations**:
- Clear JSON structure definition
- Examples for better understanding
- Explicit rules for selector syntax
- Error handling for invalid responses

### Browser Automation Actions

**Supported Actions**:

1. **navigate**: Go to a URL
   ```json
   {"action": "navigate", "url": "https://example.com"}
   ```

2. **click**: Click an element
   ```json
   {"action": "click", "selector": "button#submit"}
   ```

3. **fill**: Enter text into input
   ```json
   {"action": "fill", "selector": "input[name='q']", "value": "search query"}
   ```

4. **assert**: Verify page state
   ```json
   {
     "action": "assert",
     "selector": "#results",
     "assertion_type": "visible"
   }
   ```

5. **wait**: Pause execution
   ```json
   {"action": "wait", "duration": 1000}
   ```

## Debugging

### Backend Debugging

**Enable Debug Mode**:
```bash
# Set in config.py or environment
DEBUG = True
LOG_LEVEL = "DEBUG"
```

**Common Issues**:

1. **Ollama Not Running**:
   ```bash
   # Start Ollama
   ollama serve
   ```

2. **Model Not Found**:
   ```bash
   ollama pull llama3
   ```

3. **Browser Launch Fails**:
   ```bash
   # Reinstall browsers
   playwright install chromium
   ```

4. **Port Already in Use**:
   ```bash
   # Change port in config.py
   PORT = 8001
   ```

### Frontend Debugging

**Check Console**:
- Open browser DevTools (F12)
- Check Console tab for errors
- Check Network tab for API calls

**Common Issues**:

1. **CORS Errors**: Ensure backend CORS settings include frontend URL
2. **API Connection Failed**: Verify backend is running on correct port
3. **Results Not Displaying**: Check browser console for JavaScript errors

## Environment Variables

Create a `.env` file in the backend directory:

```env
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=True

# LLM
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3
LLM_TEMPERATURE=0.1

# Browser
BROWSER_HEADLESS=False
BROWSER_TIMEOUT=30000

# Logging
LOG_LEVEL=INFO
```

## Performance Optimization

**Backend**:
- Use async/await for I/O operations
- Implement connection pooling for Ollama
- Cache frequently used test plans

**Frontend**:
- Lazy load test history
- Debounce user input
- Optimize image loading

**Browser Automation**:
- Reuse browser instances when possible
- Use headless mode in production
- Set appropriate timeouts

## Deployment

### Docker Deployment (Future)

```dockerfile
# Example Dockerfile
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg

# Install Playwright dependencies
RUN pip install playwright
RUN playwright install chromium --with-deps

# Copy application
COPY backend /app/backend
WORKDIR /app/backend

# Install Python dependencies
RUN pip install -r requirements.txt

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "main.py"]
```

### Cloud Deployment Options

1. **AWS**: EC2 + Elastic Beanstalk
2. **GCP**: Cloud Run + Compute Engine
3. **Azure**: App Service + Container Instances
4. **Railway**: Simple deployment with Dockerfile

## Testing Strategy

**Unit Tests**:
- Test individual functions in each module
- Mock external dependencies (LLM, browser)

**Integration Tests**:
- Test complete pipeline with sample instructions
- Verify API responses

**End-to-End Tests**:
- Test full user flow from frontend to backend
- Verify browser automation works correctly

## Contributing Guidelines

1. Follow Python PEP 8 style guide
2. Add docstrings to all functions
3. Write tests for new features
4. Update documentation
5. Use meaningful commit messages

## Resources

- **FastAPI**: https://fastapi.tiangolo.com/
- **Playwright**: https://playwright.dev/python/
- **Ollama**: https://ollama.ai/
- **LLaMA**: https://ai.meta.com/llama/

## Troubleshooting

See [README.md](../README.md) for common issues and solutions.

## Next Steps

1. ✅ Complete Phase 1-4
2. Add authentication and user management
3. Implement test scheduling
4. Add support for mobile testing
5. Create Docker containerization
6. Deploy to cloud platform
7. Add CI/CD pipeline
8. Implement analytics and monitoring
