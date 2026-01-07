# Quick Start Guide - Enterprise RAG App

Get up and running in 5 minutes!

## 📋 Prerequisites Checklist

- [ ] Python 3.10 or higher installed
- [ ] Google Gemini API key (get one at https://aistudio.google.com/app/apikey)
- [ ] Terminal/Command prompt access

## ⚡ Installation Steps

### 1. Setup Environment

```bash
# Navigate to project directory
cd enterprise_rag_app

# Create virtual environment
python -m venv venv

# Activate it
# Mac/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### 2. Install Dependencies

```bash
# IMPORTANT: Install PyTorch CPU first
pip install torch==2.5.1+cpu torchvision==0.20.1+cpu --index-url https://download.pytorch.org/whl/cpu

# Then install other dependencies
pip install -r requirements.txt
```

### 3. Configure API Key

```bash
# Create .env file
cp .env.example .env

# Edit .env file and add your API key:
# GOOGLE_API_KEY=your_actual_api_key_here
```

Or on Windows:
```bash
copy .env.example .env
notepad .env
```

### 4. Run the Application

```bash
# Initialize Reflex (first time only)
reflex init

# Start the app
reflex run
```

That's it! The app will open automatically in your browser at http://localhost:3000

## 🎯 First Use

1. **Upload a PDF**
   - Click "Select Documents" button
   - Choose a PDF file
   - Click "Upload Files"
   - Wait for upload to complete

2. **Process Documents**
   - Click "Process & Vectorize" button
   - Watch the progress bars
   - Wait for "Documents processed successfully!" message

3. **Start Chatting**
   - Type a question in the chat input
   - Press Enter or click Send
   - Get answers with source citations!

4. **Explore Structure** (Optional)
   - Click "Document Analysis" tab
   - Select your document
   - Browse through Summary, Hierarchy, Tables, and Images

## ❓ Common Issues

### Error: "Module not found"
```bash
# Make sure you activated the virtual environment
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate  # Windows

# Then reinstall
pip install -r requirements.txt
```

### Error: "API key not found"
```bash
# Check your .env file exists
ls .env  # Mac/Linux
dir .env  # Windows

# Make sure it contains:
# GOOGLE_API_KEY=your_key_here
```

### Error: "Port already in use"
```python
# Edit rxconfig.py and change ports:
frontend_port=3002,  # Change from 3001
backend_port=8003,   # Change from 8002
```

### Processing is very slow
- Large PDFs are automatically batched
- OCR processing takes time for scanned documents
- First run downloads AI models (~500MB)

## 🎓 Next Steps

- Read the full README.md for detailed documentation
- Explore the code structure in the repository
- Try uploading multiple documents
- Experiment with different questions
- Check out document structure analysis

## 💡 Pro Tips

1. **Start small**: Test with a 5-10 page PDF first
2. **Be specific**: Ask detailed questions for better answers
3. **Use citations**: AI provides page numbers for verification
4. **Clear when needed**: Click "Clear All" to reset everything
5. **Check structure**: Use Document Analysis tab to verify extraction quality

## 📞 Need Help?

- Review error messages in the terminal
- Check that all dependencies installed correctly
- Verify your API key is valid
- Ensure you have internet connection for API calls

---

**Ready to build amazing RAG applications! 🚀**
