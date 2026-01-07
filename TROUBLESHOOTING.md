# Troubleshooting Guide

Common issues and their solutions for the Enterprise RAG Application.

## 🔧 Installation Issues

### Problem: PyTorch GPU version installed (large download)

**Symptoms**: Installation takes forever, downloads 2+ GB

**Solution**:

```bash
# Uninstall first
pip uninstall torch torchvision

# Install CPU version
pip install torch==2.5.1+cpu torchvision==0.20.1+cpu --index-url https://download.pytorch.org/whl/cpu

# Then reinstall other packages
pip install -r requirements.txt
```

### Problem: "Module not found" errors

**Symptoms**: ImportError or ModuleNotFoundError

**Solution**:

```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt

# If still fails, try one by one
pip install reflex
pip install docling[rapidocr]
# etc.
```

### Problem: "Cannot import name X from Y"

**Symptoms**: Import errors after installation

**Solution**:

```bash
# Version mismatch - reinstall with exact versions
pip uninstall -y langchain langchain-core langgraph
pip install langchain>=0.3.0 langgraph>=0.2.0
```

## 🚀 Runtime Issues

### Problem: "Agent not initialized" in chat

**Symptoms**: Error message when trying to chat

**Cause**: Documents not processed yet

**Solution**:

1. Upload documents first
2. Click "Process & Vectorize"
3. Wait for "Documents processed successfully!" message
4. Then try chatting

### Problem: Processing hangs/freezes

**Symptoms**: Progress bar stuck, no updates

**Solutions**:

1. **Check terminal for errors**:

   ```bash
   # Look for Python errors in the terminal where you ran `reflex run`
   ```

2. **Reduce batch size** (for very large PDFs):

   ```python
   # Edit services/vector_store.py
   BATCH_SIZE = 25  # Change from 50 to 25
   ```

3. **Increase timeout**:

   ```python
   # Edit rxconfig.py
   timeout=900,  # Increase from 600 to 900
   ```

4. **Check memory**:

   ```bash
   # Monitor memory usage
   # Mac/Linux:
   top
   # Windows:
   taskmgr
   ```

### Problem: "No API key found" or "Invalid API key"

**Symptoms**: API errors in terminal

**Solution**:

```bash
# 1. Check .env file exists
cat .env  # Mac/Linux
type .env # Windows

# 2. Verify format (no spaces, no quotes unless key has them)
GOOGLE_API_KEY=AIza...your_key_here

# 3. Restart the app after editing .env
# Kill the server (Ctrl+C) and run again:
reflex run

# 4. Test API key manually
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('API Key:', os.getenv('GOOGLE_API_KEY')[:10] + '...')
"
```

### Problem: Port already in use

**Symptoms**: "Address already in use" error

**Solution**:

```python
# Edit rxconfig.py
config = rx.Config(
    frontend_port=3002,  # Change from 3001
    backend_port=8003,   # Change from 8002
)
```

Or kill the existing process:

```bash
# Mac/Linux:
lsof -ti:3001 | xargs kill -9
lsof -ti:8002 | xargs kill -9

# Windows:
netstat -ano | findstr :3001
taskkill /PID <pid_from_above> /F
```

## 💬 Chat Issues

### Problem: Slow responses

**Symptoms**: Takes long time to get answers

**Causes & Solutions**:

1. **First query after upload** - Agent initializing
   - Wait 10-20 seconds for first query
   - Subsequent queries will be faster

2. **Large document** - Searching many chunks
   - Reduce k value in vector search:

   ```python
   # Edit services/llm_service.py
   results = await vector_store.search(query, k=4)  # Reduce from 8
   ```

3. **API latency** - Gemini response time
   - Try faster model:

   ```python
   # Edit services/llm_service.py
   def create_agent(self, model_name: str = "gemini-2.5-flash"):  # Faster model
   ```

### Problem: Answers not citing sources

**Symptoms**: Responses don't include page numbers

**Cause**: Search not finding results

**Solution**:

1. Verify documents processed successfully
2. Check Document Analysis tab to confirm content extracted
3. Try rephrasing your question
4. Ensure question relates to uploaded documents

### Problem: "Error: ..." in chat response

**Symptoms**: Error message in chat bubble

**Debug Steps**:

```bash
# 1. Check terminal for full error
# 2. Common causes:

# API rate limit
# Solution: Wait 1 minute, try again

# Out of memory
# Solution: Restart app, process fewer documents

# Network error
# Solution: Check internet connection
```

## 📊 Document Processing Issues

### Problem: "No documents were successfully processed"

**Symptoms**: Upload succeeds but processing fails

**Solutions**:

1. **Check PDF validity**:

   ```python
   # Test with a simple PDF first
   # Try a different PDF to rule out corruption
   ```

2. **Check file size**:

   ```bash
   # Files over 100MB may have issues
   # Split large PDFs first
   ```

3. **OCR timeout**:

   ```python
   # Edit services/vector_store.py
   # Disable OCR for testing:
   pipeline_options.do_ocr = False
   ```

### Problem: Tables not appearing in Document Analysis

**Symptoms**: Tables tab shows "No tables found"

**Cause**: Document has no tables or table extraction failed

**Solutions**:

1. Check if document actually has tables
2. Tables might be images (not detected)
3. Try simpler tables (complex layouts may fail)

### Problem: Memory error during processing

**Symptoms**: "MemoryError" or app crashes

**Solutions**:

1. **Process fewer documents at once**:
   - Upload 1-2 PDFs at a time
   - Clear before uploading more

2. **Reduce batch size**:

   ```python
   # Edit services/vector_store.py
   BATCH_SIZE = 10  # Reduce from 50
   ```

3. **Disable images**:

   ```python
   # Edit services/vector_store.py
   pipeline_options.generate_picture_images = False
   ```

4. **Increase system swap/pagefile**

## 🎨 UI Issues

### Problem: Layout looks broken

**Symptoms**: Components overlapping, weird spacing

**Solutions**:

```bash
# 1. Hard refresh browser
# Mac/Linux: Cmd+Shift+R or Ctrl+Shift+R
# Windows: Ctrl+F5

# 2. Clear browser cache

# 3. Restart Reflex
reflex run --loglevel debug
```

### Problem: Progress bars not updating

**Symptoms**: Bars stuck at 0% but process completes

**Cause**: WebSocket update issue

**Solutions**:

```bash
# 1. Check browser console (F12) for errors

# 2. Restart with clean state
reflex db migrate  # Reset database
reflex run

# 3. Try different browser
```

### Problem: Chat input not working

**Symptoms**: Can't type or send messages

**Solutions**:

1. Ensure documents processed first
2. Check browser console for JS errors
3. Try clicking input field directly
4. Restart browser

## 🗄️ Database Issues

### Problem: "Database locked" error

**Symptoms**: SQLite database errors

**Solution**:

```bash
# Stop the app
# Delete the database
rm reflex.db  # Mac/Linux
del reflex.db # Windows

# Restart
reflex run
```

### Problem: State not persisting

**Symptoms**: Data disappears on refresh

**Expected Behavior**: 

- Reflex state is session-based
- Refresh = new session = clean state
- This is by design for security

**If you need persistence**:

```python
# Implement in your state class
def save_to_disk(self):
    with open("saved_state.json", "w") as f:
        json.dump(self.dict(), f)

def load_from_disk(self):
    with open("saved_state.json", "r") as f:
        data = json.load(f)
        # Update state from data
```

## 🐛 Debug Mode

Enable detailed logging:

```bash
# Run with debug logging
reflex run --loglevel debug

# Check for errors in:
# 1. Terminal output (backend errors)
# 2. Browser console (frontend errors)
# 3. Network tab (API failures)
```

Add debug prints:

```python
# In any state method
print(f"DEBUG: Current state: {self.dict()}")
print(f"DEBUG: Processing {len(files)} files")
```

## 📞 Getting Help

If none of these solutions work:

1. **Check error message carefully** - Often points to the exact issue
2. **Search GitHub issues** - Someone may have had same problem
3. **Check Reflex Discord** - Community support
4. **Review code** - Comment out sections to isolate issue
5. **Start fresh** - Sometimes cleanest solution

### Useful Commands for Debugging

```bash
# Check Python version
python --version  # Should be 3.10+

# Check installed packages
pip list | grep reflex
pip list | grep langchain

# Check port usage
# Mac/Linux:
lsof -i :3001
lsof -i :8002
# Windows:
netstat -ano | findstr :3001

# Monitor system resources
# Mac/Linux:
htop  # or top
# Windows:
Resource Monitor

# Test imports
python -c "import reflex; print(reflex.__version__)"
python -c "import docling; print('Docling OK')"
python -c "from langchain_google_genai import ChatGoogleGenerativeAI; print('LangChain OK')"
```

## 🔍 Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError` | Missing package | `pip install <package>` |
| `Address already in use` | Port taken | Change port in rxconfig.py |
| `API key not found` | Missing .env | Create .env with key |
| `MemoryError` | Not enough RAM | Reduce batch size |
| `Timeout` | Operation too long | Increase timeout in config |
| `Database locked` | SQLite conflict | Delete reflex.db |
| `Agent not initialized` | No documents | Process documents first |

---

**Still stuck? Check the README.md for more documentation, or review your terminal output carefully!**
