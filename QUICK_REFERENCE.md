# 🚀 Quick Start Checklist - Windows + VS Code

Print this page and follow along! ✅

---

## 📥 PART 1: INSTALL (Do Once)

```
┌─────────────────────────────────────────────────────────┐
│ 1. INSTALL PYTHON                                       │
│    └─ https://www.python.org/downloads/                │
│    └─ ✅ CHECK: "Add Python to PATH"                   │
│    └─ Test: Open CMD, type: python --version           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 2. INSTALL VS CODE                                      │
│    └─ https://code.visualstudio.com/                   │
│    └─ Download → Install → Done                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 3. INSTALL OLLAMA (AI Brain)                           │
│    └─ https://ollama.ai/download                       │
│    └─ Download → Install → Done                        │
│    └─ Open CMD and run: ollama pull llama3             │
│    └─ Wait 5-10 minutes (downloads 4GB)                │
│    └─ Test: ollama list                                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 4. GET PROJECT FILES                                    │
│    └─ Copy ai-testing-agent folder to:                 │
│       C:\Users\YourName\Documents\ai-testing-agent      │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 PART 2: SETUP (Do Once)

```
┌─────────────────────────────────────────────────────────┐
│ 5. OPEN IN VS CODE                                      │
│    └─ Open VS Code                                      │
│    └─ File → Open Folder                               │
│    └─ Select: ai-testing-agent                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 6. INSTALL DEPENDENCIES                                 │
│    In VS Code Terminal:                                 │
│                                                          │
│    cd backend                                           │
│    pip install -r requirements.txt                      │
│    playwright install chromium                          │
│                                                          │
│    Wait for completion!                                 │
└─────────────────────────────────────────────────────────┘
```

---

## ▶️ PART 3: RUN (Every Time You Want to Use It)

```
┌─────────────────────────────────────────────────────────┐
│ TERMINAL 1: Start Backend                              │
│                                                          │
│    cd backend                                           │
│    python main.py                                       │
│                                                          │
│    ✅ You should see:                                   │
│    "Server running at: http://0.0.0.0:8000"            │
│                                                          │
│    ⚠️ LEAVE THIS RUNNING!                               │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ TERMINAL 2: Start Frontend                             │
│    (Click + button in terminal to open new one)        │
│                                                          │
│    cd frontend                                          │
│    python -m http.server 8080                           │
│                                                          │
│    ✅ You should see:                                   │
│    "Serving HTTP on 0.0.0.0 port 8080"                 │
│                                                          │
│    ⚠️ LEAVE THIS RUNNING TOO!                           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ BROWSER: Open the App                                   │
│                                                          │
│    Open Chrome/Edge/Firefox                             │
│    Go to: http://localhost:8080                         │
│                                                          │
│    🎉 You should see the AI Testing Agent!              │
└─────────────────────────────────────────────────────────┘
```

---

## 🧪 PART 4: TEST IT!

```
┌─────────────────────────────────────────────────────────┐
│ Try Your First Test:                                    │
│                                                          │
│    1. Type in the text box:                            │
│       "Open example.com and verify the page loads"     │
│                                                          │
│    2. Click "Run Test"                                 │
│                                                          │
│    3. Watch:                                            │
│       → Browser opens automatically                     │
│       → Goes to example.com                            │
│       → Results show on screen                         │
│                                                          │
│    ✅ SUCCESS!                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 🛑 STOPPING

```
When Done:
1. Close browser
2. In VS Code terminals, press Ctrl+C (both terminals)
3. Close VS Code
```

---

## ⚡ Quick Troubleshooting

```
❌ "python is not recognized"
   → Reinstall Python with "Add to PATH" checked

❌ Health shows "LLM Unavailable"  
   → Open Windows Start, search "Ollama", run it
   → Wait 10 seconds, refresh browser

❌ "Port 8000 already in use"
   → Close all Python processes in Task Manager
   → Try again

❌ Browser doesn't open during test
   → Run: playwright install chromium
```

---

## 📝 PASTE THIS IN TERMINAL

**Setup (once):**
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```

**Run Backend (every time):**
```bash
cd backend
python main.py
```

**Run Frontend (every time, new terminal):**
```bash
cd frontend
python -m http.server 8080
```

---

## ✅ SUCCESS LOOKS LIKE:

```
VS Code:
├─ Terminal 1: "Server running at: http://0.0.0.0:8000"
└─ Terminal 2: "Serving HTTP on 0.0.0.0 port 8080"

Browser (localhost:8080):
├─ Purple header "AI Testing Agent"
├─ Green status "System Ready"
└─ Text box + "Run Test" button
```

---

## 🎯 SAMPLE TESTS TO TRY

```
1. Open example.com and verify the page loads

2. Go to Google, search for "Python testing", 
   and verify results appear

3. Navigate to GitHub, click Sign in, 
   and verify login form is visible

4. Open Wikipedia, search for "AI", 
   click first result, and verify article loads
```

---

## 📱 NEED HELP?

1. Read: WINDOWS_SETUP_GUIDE.md (detailed step-by-step)
2. Read: QUICKSTART.md
3. Check the Troubleshooting section above

---

**🎉 You Got This! Happy Testing! 🚀**
