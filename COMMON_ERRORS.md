# Common Errors & Solutions - Windows

This guide shows you EXACTLY what to do when you see common error messages.

---

## 🔴 ERROR 1: "python is not recognized as an internal or external command"

### What You See:
```
'python' is not recognized as an internal or external command,
operable program or batch file.
```

### What It Means:
Python is not installed OR not added to Windows PATH

### Solution:

**Option 1: Reinstall Python (Recommended)**

1. **Uninstall Python:**
   - Press Windows Key
   - Type "Add or Remove Programs"
   - Find "Python 3.x.x"
   - Click "Uninstall"

2. **Download Python Again:**
   - Go to: https://www.python.org/downloads/
   - Download the latest version

3. **Install Correctly:**
   - Run the installer
   - ⚠️ **IMPORTANT:** CHECK the box "Add Python to PATH"
   - Click "Install Now"
   - Restart Command Prompt

4. **Test:**
   ```
   python --version
   ```

**Option 2: Add to PATH Manually**

1. Find where Python is installed (usually: `C:\Users\YourName\AppData\Local\Programs\Python\Python311`)
2. Press Windows Key
3. Type "Environment Variables"
4. Click "Edit system environment variables"
5. Click "Environment Variables"
6. Under "System variables", find "Path"
7. Click "Edit"
8. Click "New"
9. Add the Python path
10. Click OK on everything
11. Restart Command Prompt

---

## 🔴 ERROR 2: "ollama: command not found" or "ollama is not recognized"

### What You See:
```
'ollama' is not recognized as an internal or external command
```

### What It Means:
Ollama is not installed

### Solution:

1. **Download Ollama:**
   - Go to: https://ollama.ai/download
   - Click "Download for Windows"

2. **Install:**
   - Run the downloaded installer
   - Follow the installation steps

3. **Verify Ollama is Running:**
   - Look at your system tray (bottom-right corner)
   - You should see the Ollama icon

4. **If Not Running:**
   - Press Windows Key
   - Type "Ollama"
   - Click to run it

5. **Test:**
   ```
   ollama --version
   ```

6. **Download the Model:**
   ```
   ollama pull llama3
   ```

---

## 🔴 ERROR 3: "pip: command not found" or "pip is not recognized"

### What You See:
```
'pip' is not recognized as an internal or external command
```

### What It Means:
pip (Python package installer) is not in PATH

### Solution:

**Use python -m pip instead:**

Instead of:
```
pip install -r requirements.txt
```

Use:
```
python -m pip install -r requirements.txt
```

Or reinstall Python with PATH correctly (see Error 1).

---

## 🔴 ERROR 4: "playwright: command not found"

### What You See:
```
'playwright' is not recognized as an internal or external command
```

### What It Means:
Playwright needs to be run through Python

### Solution:

Instead of:
```
playwright install chromium
```

Use:
```
python -m playwright install chromium
```

---

## 🔴 ERROR 5: Health Status Shows "LLM Unavailable"

### What You See:
In the browser, the health indicator is RED and says "LLM Unavailable"

### What It Means:
Ollama is not running or llama3 model is not installed

### Solution:

1. **Start Ollama:**
   - Press Windows Key
   - Type "Ollama"
   - Click to run it
   - Wait 10 seconds

2. **Check if Model is Downloaded:**
   Open Command Prompt:
   ```
   ollama list
   ```

3. **If llama3 is NOT in the list:**
   ```
   ollama pull llama3
   ```
   Wait 5-10 minutes

4. **Refresh your browser**

---

## 🔴 ERROR 6: "Address already in use" (Port 8000 or 8080)

### What You See:
```
OSError: [WinError 10048] Only one usage of each socket address 
(protocol/network address/port) is normally permitted
```

### What It Means:
The port is already being used by another program

### Solution A: Close Existing Process

1. Press **Ctrl + Shift + Esc** (opens Task Manager)
2. Click "More details" if needed
3. Look for any "Python" processes
4. Right-click each one → "End Task"
5. Try starting the server again

### Solution B: Use Different Port

**For Backend (if port 8000 is busy):**

1. Open `backend/config.py` in VS Code
2. Find the line: `PORT = 8000`
3. Change to: `PORT = 8001`
4. Save the file
5. Start backend again

**For Frontend (if port 8080 is busy):**

Instead of:
```
python -m http.server 8080
```

Use:
```
python -m http.server 8081
```

Then open browser at: `http://localhost:8081`

---

## 🔴 ERROR 7: "No module named 'fastapi'" (or other module)

### What You See:
```
ModuleNotFoundError: No module named 'fastapi'
```

### What It Means:
Dependencies were not installed

### Solution:

1. **Make sure you're in the backend folder:**
   ```
   cd backend
   ```

2. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

3. **Wait for completion**

4. **Try starting the server again**

---

## 🔴 ERROR 8: Browser Window Doesn't Open During Test

### What You See:
Test runs but no browser window appears, test fails

### What It Means:
Playwright browsers not installed

### Solution:

1. **In VS Code terminal:**
   ```
   cd backend
   python -m playwright install chromium
   ```

2. **Wait for installation**

3. **Try the test again**

---

## 🔴 ERROR 9: "Cannot connect to backend server"

### What You See:
In browser: Red health indicator "Backend Offline"

### What It Means:
The backend server is not running

### Solution:

1. **Check VS Code:**
   - Do you have a terminal showing "Server running at..."?
   - If NO, start the backend:
     ```
     cd backend
     python main.py
     ```

2. **Check if backend is actually running:**
   - Open browser
   - Go to: http://localhost:8000/health
   - Should see: `{"status":"healthy",...}`

3. **If nothing appears:**
   - Backend is not running
   - Start it following Step 1

---

## 🔴 ERROR 10: "CORS Error" in Browser Console

### What You See:
In browser Developer Tools (F12) console:
```
Access to fetch at 'http://localhost:8000/api/test' from origin 
'http://localhost:8080' has been blocked by CORS policy
```

### What It Means:
CORS is not properly configured (rare, should work out of the box)

### Solution:

1. **Stop the backend** (Ctrl+C in the terminal)

2. **Open `backend/main.py` in VS Code**

3. **Check that this code is present:**
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

4. **Restart backend:**
   ```
   python main.py
   ```

---

## 🔴 ERROR 11: Test Fails with "Timeout" Error

### What You See:
Test fails with message like: "Timeout 30000ms exceeded"

### What It Means:
The page is taking too long to load or element can't be found

### Solution:

1. **Check your internet connection**

2. **Try a simpler test first:**
   ```
   Open example.com and verify page loads
   ```

3. **If still failing, increase timeout:**
   - Open `backend/config.py`
   - Find: `BROWSER_TIMEOUT = 30000`
   - Change to: `BROWSER_TIMEOUT = 60000`
   - Save and restart backend

---

## 🔴 ERROR 12: "Permission Denied" Errors

### What You See:
```
PermissionError: [WinError 5] Access is denied
```

### Solution:

1. **Run VS Code as Administrator:**
   - Close VS Code
   - Right-click VS Code icon
   - Click "Run as Administrator"
   - Open the project again

2. **Or choose a different project location:**
   - Move the ai-testing-agent folder to:
   - `C:\Users\YourName\Documents\ai-testing-agent`

---

## 🔴 ERROR 13: Frontend Shows Blank Page

### What You See:
Browser shows blank white page at localhost:8080

### Solution:

1. **Check you're in the right directory:**
   ```
   cd frontend
   dir
   ```
   Should see: `index.html`, `style.css`, `app.js`

2. **Make sure you typed the URL correctly:**
   ```
   http://localhost:8080
   ```
   Not: https:// (no 's')

3. **Check the terminal for errors**

4. **Try a different browser** (Chrome, Edge, Firefox)

---

## 🔴 ERROR 14: "SyntaxError" in Python Files

### What You See:
```
SyntaxError: invalid syntax
```

### What It Means:
File got corrupted or edited incorrectly

### Solution:

1. **Re-download the project files**
2. **Extract fresh copy**
3. **Don't manually edit Python files** unless you know Python

---

## ✅ PREVENTION CHECKLIST

To avoid most errors:

- ✅ Install Python with "Add to PATH" checked
- ✅ Install all prerequisites BEFORE starting
- ✅ Always `cd backend` before running backend commands
- ✅ Always `cd frontend` before running frontend commands
- ✅ Keep both terminal windows running while using the app
- ✅ Make sure Ollama is running in background
- ✅ Download llama3 model completely before testing

---

## 🆘 STILL STUCK?

### Nuclear Option: Start Fresh

1. **Uninstall Everything:**
   - Uninstall Python
   - Uninstall Ollama
   - Delete ai-testing-agent folder

2. **Restart Your Computer**

3. **Follow WINDOWS_SETUP_GUIDE.md from Step 1**
   - Read each step carefully
   - Don't skip any steps
   - Verify each step before moving on

---

## 📞 Quick Checks

Before asking for help, verify:

```
✅ Python installed: python --version
✅ Ollama installed: ollama --version  
✅ Model downloaded: ollama list (should show llama3)
✅ In correct folder: Check VS Code bottom-left shows project folder
✅ Backend running: Terminal shows "Server running at..."
✅ Frontend running: Terminal shows "Serving HTTP on..."
✅ Browser URL: http://localhost:8080 (not https)
```

---

**Remember: Most errors are simple fixes! Don't panic! 🌟**
