# Quick Start

## 1. Install Dependencies

```bash
# Using UV (recommended)
uv sync

# Or pip
pip install -r requirements.txt
```

## 2. Set API Key

Create a `.env` file:
```bash
GOOGLE_API_KEY=your-google-api-key
```

## 3. Run

```bash
reflex run
```

- Open `http://localhost:3001`
- Upload documents in the left panel
- Click **Process & Vectorize**
- Ask questions in the chat panel
- Switch to **Document Analysis** to inspect structure

## 4. Verify Multi-User Isolation

1. Process a document in your main browser window.
2. Open an incognito window to `http://localhost:3001`.
3. The incognito window should show **no** processed documents.
4. Upload a different document in the incognito window.
5. The main window should still only see its original document.
