# Running AI Testing Agent on Windows with VS Code - Step by Step

## 🎯 Complete Beginner-Friendly Guide

Follow these exact steps to get the AI Testing Agent running on your Windows PC using VS Code.

---

## ✅ STEP 1: Install Python

### Download Python

1. Open your web browser
2. Go to: https://www.python.org/downloads/
3. Click the yellow **"Download Python 3.x.x"** button
4. Save the installer file

### Install Python

1. **Double-click** the downloaded installer file
2. ⚠️ **VERY IMPORTANT:** Check the box that says **"Add Python to PATH"**
3. Click **"Install Now"**
4. Wait for installation to complete
5. Click **"Close"**

### Verify Python is Installed

1. Press **Windows Key + R**
2. Type `cmd` and press Enter
3. In the black window (Command Prompt), type:
   ```
   python --version
   ```
4. You should see something like: `Python 3.11.x`
5. Close the Command Prompt

---

## ✅ STEP 2: Install VS Code

### Download VS Code

1. Go to: https://code.visualstudio.com/
2. Click **"Download for Windows"**
3. Save the installer

### Install VS Code

1. Double-click the installer
2. Accept the license agreement
3. Click **"Next"** through all the steps
4. Click **"Install"**
5. Click **"Finish"**

---

## ✅ STEP 3: Install Ollama (The AI Brain)

### Download Ollama

1. Go to: https://ollama.ai/download
2. Click **"Download for Windows"**
3. Save the installer file

### Install Ollama

1. Double-click the installer
2. Follow the installation steps
3. Ollama will start automatically in the background
4. You'll see an Ollama icon in your system tray (bottom-right corner)

### Download the AI Model

1. Press **Windows Key + R**
2. Type `cmd` and press Enter
3. In the Command Prompt, type:
   ```
   ollama pull llama3
   ```
4. Press Enter
5. ⏳ **Wait 5-10 minutes** - It's downloading ~4GB
6. When you see "success", it's done!
7. Leave Command Prompt open

### Verify Model is Installed

In the same Command Prompt, type:
```
ollama list
```

You should see `llama3` in the list. ✅

---

## ✅ STEP 4: Get the Project Files

### Option A: You Already Have the Folder

1. Copy the **ai-testing-agent** folder to a location like:
   - `C:\Users\YourName\Documents\ai-testing-agent`
   - Or anywhere you want to keep it

### Option B: Download from Cloud/USB

1. Extract/copy the folder to your PC
2. Remember where you put it!

---

## ✅ STEP 5: Open Project in VS Code

### Open VS Code

1. Click the Windows Start button
2. Type **"Visual Studio Code"**
3. Click to open it

### Open the Project

1. In VS Code, click **"File"** (top-left)
2. Click **"Open Folder..."**
3. Navigate to your `ai-testing-agent` folder
4. Click **"Select Folder"**
5. If prompted "Do you trust the authors?", click **"Yes, I trust the authors"**

You should now see all the project files in the left sidebar! 📁

---

## ✅ STEP 6: Install Python Extension (First Time Only)

1. Click the **Extensions** icon on the left sidebar (4 squares icon)
2. In the search box, type: **"Python"**
3. Find **"Python"** by Microsoft
4. Click **"Install"**
5. Wait for it to install

---

## ✅ STEP 7: Open Terminal in VS Code

1. In VS Code, click **"Terminal"** in the top menu
2. Click **"New Terminal"**
3. A terminal panel will appear at the bottom of VS Code

**You should see something like:**
```
PS C:\Users\YourName\Documents\ai-testing-agent>
```

---

## ✅ STEP 8: Install Backend Dependencies

### Navigate to Backend Folder

In the VS Code terminal (bottom panel), type:
```
cd backend
```
Press **Enter**

Now you should see:
```
PS C:\Users\YourName\Documents\ai-testing-agent\backend>
```

### Install Python Packages

Type this command:
```
pip install -r requirements.txt
```
Press **Enter**

⏳ **Wait 2-3 minutes** - It's installing packages

You'll see lots of text scrolling by. That's normal!

When you see the prompt again, it's done. ✅

### Install Browser for Testing

Type this command:
```
playwright install chromium
```
Press **Enter**

⏳ **Wait 1-2 minutes** - It's downloading the browser

When done, you'll see "success" messages. ✅

---

## ✅ STEP 9: Start the Backend Server

### Make Sure Ollama is Running

1. Look at your system tray (bottom-right corner near the clock)
2. You should see the Ollama icon
3. If not, search for "Ollama" in Windows Start and run it

### Start the Backend

In the VS Code terminal (should still be in the `backend` folder), type:
```
python main.py
```
Press **Enter**

🎉 **You should see:**
```
╔══════════════════════════════════════════════════════════╗
║        AI-Powered Autonomous Testing Agent              ║
║  Server running at: http://0.0.0.0:8000                 ║
╚══════════════════════════════════════════════════════════╝
```

✅ **Success!** The backend is running!

**⚠️ IMPORTANT: Leave this terminal running! Don't close it!**

---

## ✅ STEP 10: Start the Frontend (User Interface)

### Open a New Terminal

1. In VS Code, look at the terminal panel (bottom)
2. Click the **"+"** button (top-right of terminal panel)
3. A **new terminal** will open

### Navigate to Frontend Folder

In the NEW terminal, type:
```
cd frontend
```
Press **Enter**

### Start the Web Server

Type:
```
python -m http.server 8080
```
Press **Enter**

You should see:
```
Serving HTTP on 0.0.0.0 port 8080 (http://0.0.0.0:8080/) ...
```

✅ **Success!** The frontend is running!

**⚠️ IMPORTANT: Leave this terminal running too!**

---

## ✅ STEP 11: Open the Application in Your Browser

1. Open your web browser (Chrome, Edge, Firefox, etc.)
2. In the address bar, type:
   ```
   http://localhost:8080
   ```
3. Press **Enter**

🎉 **YOU DID IT!** You should see the AI Testing Agent interface!

---

## 🎮 STEP 12: Run Your First Test

### Try This Test

1. In the text box, type:
   ```
   Open example.com and verify the page loads
   ```

2. Click the **"Run Test"** button

3. Watch the magic happen:
   - A browser window will open
   - It will navigate to example.com
   - Results will appear on the screen

### Try More Tests

```
Go to Google, search for "Python testing", and verify results appear
```

```
Navigate to GitHub and verify the page loads
```

---

## 📊 What You Should See

### In VS Code - 2 Terminals Running:

**Terminal 1 (Backend):**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Terminal 2 (Frontend):**
```
Serving HTTP on 0.0.0.0 port 8080...
127.0.0.1 - - [10/Feb/2025 10:30:45] "GET / HTTP/1.1" 200 -
```

### In Your Browser:
- Beautiful purple interface
- Input box for test instructions
- "Run Test" button
- Health status indicator (should be green "System Ready")

---

## 🛑 How to Stop Everything

### When You're Done Testing:

1. **Close the browser tab**

2. **Stop the Frontend:**
   - Click on Terminal 2 in VS Code
   - Press **Ctrl + C**

3. **Stop the Backend:**
   - Click on Terminal 1 in VS Code
   - Press **Ctrl + C**

4. **Close VS Code** if you want

### To Run Again Later:

Just repeat **Steps 9-11** (start backend, start frontend, open browser)

---

## 🐛 Troubleshooting

### ❌ "python is not recognized"

**Problem:** Python is not in your PATH

**Solution:**
1. Uninstall Python
2. Reinstall it
3. **Make sure** to check "Add Python to PATH" during installation

### ❌ "port 8080 is already in use"

**Problem:** Something else is using port 8080

**Solution:**
Use a different port:
```
python -m http.server 8081
```
Then visit: `http://localhost:8081`

### ❌ "LLM Unavailable" in the browser

**Problem:** Ollama is not running

**Solution:**
1. Press Windows Key
2. Type "Ollama"
3. Click to run it
4. Wait 10 seconds
5. Refresh the browser

### ❌ Backend won't start - "Address already in use"

**Problem:** Port 8000 is busy

**Solution:**
1. Open Task Manager (Ctrl + Shift + Esc)
2. Find any Python processes
3. End them
4. Try starting the backend again

### ❌ Browser window doesn't open during test

**Problem:** Playwright browser not installed correctly

**Solution:**
```
cd backend
playwright install chromium
```

---

## 📁 Folder Structure You Should See in VS Code

```
ai-testing-agent/
├── 📁 backend/
│   ├── main.py
│   ├── llm_service.py
│   ├── automation_engine.py
│   ├── report_generator.py
│   ├── config.py
│   └── requirements.txt
├── 📁 frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── 📁 docs/
├── 📁 tests/
├── README.md
└── QUICKSTART.md
```

---

## 🎯 Quick Reference Commands

### Starting the Application

```bash
# Terminal 1 - Backend
cd backend
python main.py

# Terminal 2 - Frontend  
cd frontend
python -m http.server 8080

# Browser
http://localhost:8080
```

### Checking If Everything is Installed

```bash
# Check Python
python --version

# Check Ollama
ollama list

# Check if backend is running
# Visit in browser: http://localhost:8000/health
```

---

## 💡 Tips

1. **Always start Ollama first** (it runs in the background automatically)
2. **Keep both terminals running** while using the app
3. **Don't close the terminal windows** that show "Server running"
4. **Bookmark** http://localhost:8080 for easy access
5. **Try simple tests first** before complex ones

---

## 🎓 Example Test Instructions to Try

### Beginner Level
```
Open example.com and verify the page loads
```

### Intermediate Level
```
Go to Google, search for "Python", and verify results appear
```

### Advanced Level
```
Navigate to GitHub, click on Sign in, and verify login form is visible
```

---

## ✅ Success Checklist

- [ ] Python installed and verified
- [ ] VS Code installed
- [ ] Ollama installed
- [ ] llama3 model downloaded
- [ ] Project opened in VS Code
- [ ] Backend dependencies installed
- [ ] Playwright installed
- [ ] Backend server running (Terminal 1)
- [ ] Frontend server running (Terminal 2)
- [ ] Browser showing the app at localhost:8080
- [ ] First test executed successfully

---

## 🎉 Congratulations!

If you made it here, you're now running an AI-powered testing agent on your Windows PC!

**Need help?** Check the troubleshooting section above or review the steps carefully.

**Happy Testing!** 🚀
