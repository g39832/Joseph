# JOSEPH — Personal AI Assistant

A fully local, free, open-source Jarvis-style AI assistant built in Python.

**Current Phase: 1 — Foundation (CLI Chat + Memory)**

---

## What JOSEPH Can Do (Phase 1)

- Chat with you through the terminal
- Remember your conversations between sessions
- Learn facts about you over time
- Stream responses naturally (text appears word by word)
- Use a consistent personality
- Store memories with semantic search (ChromaDB)

---

## Full Setup Guide

### Step 1 — Install Python 3.12+

Download from: https://www.python.org/downloads/

During install, check **"Add Python to PATH"**.

Verify:
```
python --version
```
Should show `Python 3.12.x` or higher.

---

### Step 2 — Install Ollama

Download from: https://ollama.com/download

Install it, then open a terminal and run:
```
ollama serve
```
Leave this running in the background. Ollama must be running for JOSEPH to work.

---

### Step 3 — Pull the AI Model

In a new terminal window:
```
ollama pull llama3
```

This downloads the llama3 model (~4.7GB). It only needs to be done once.

Optional — pull the fallback model too:
```
ollama pull qwen2.5
```

Verify the model is available:
```
ollama list
```

---

### Step 4 — Set Up the Project

Open a terminal in the Joseph folder (`C:\Users\Grayson\Desktop\Joseph`).

Create a virtual environment:
```
python -m venv venv
```

Activate it (Windows CMD):
```
venv\Scripts\activate
```

You should see `(venv)` at the start of your prompt.

---

### Step 5 — Install Phase 1 Dependencies

Phase 1 only needs a subset of requirements.txt. Install just what's needed:

```
pip install python-dotenv pydantic pydantic-settings ollama chromadb rich colorama
```

Or install everything at once (takes longer, includes Phase 2-5 packages):
```
pip install -r requirements.txt
```

> **Note on TTS (Phase 2):** The `TTS` package requires PyTorch and is large (~2GB).
> Skip it for Phase 1 — it's not needed yet.

---

### Step 6 — Configure Your Settings

Open `.env` and update:
```
USER_NAME=YourName        # Your name (Joseph will use this)
OLLAMA_MODEL=llama3       # Or qwen2.5 if you prefer
```

Everything else works with defaults.

---

### Step 7 — Run JOSEPH

Make sure:
1. Ollama is running (`ollama serve` in a separate terminal)
2. Your venv is activated (`venv\Scripts\activate`)

Then:
```
python main.py
```

---

## Using JOSEPH

Just type and press Enter to chat.

### Special Commands

| Command | What it does |
|---------|-------------|
| `/help` | Show all commands |
| `/memory` | Show memory system status |
| `/facts` | Show what Joseph knows about you |
| `/remember <text>` | Explicitly save something to memory |
| `/search <query>` | Search your memories |
| `/clear` | Clear current conversation |
| `/status` | Show system status |
| `/quit` | Exit Joseph |

### Example Session

```
Joseph [09:15]: Good morning. What are we working on today?

You: I'm building a Python project for work. My name is Grayson.

Joseph [09:15]: Got it, Grayson. What kind of Python project are you working on?

You: /remember I prefer dark mode in all editors

✓ Saved to memory: I prefer dark mode in all editors

You: /facts
```

---

## Project Structure

```
joseph/
├── brain/              # LLM interface, personality, prompts
├── memory/             # Short-term, long-term, vector memory
├── voice/              # Phase 2: microphone, wake word, TTS
├── automation/         # Phase 3: browser + desktop automation
├── agents/             # Phase 4-5: planning and task agents
├── scheduler/          # Phase 5: reminders and scheduling
├── api/                # REST API server
├── ui/                 # CLI interface
├── configs/            # Settings, logging, JSON config
├── logs/               # Rotating log files
├── data/               # SQLite DB + ChromaDB (auto-created)
├── .env                # Your personal config (never commit this)
├── requirements.txt    # All dependencies
└── main.py             # Entry point
```

---

## Phases Roadmap

| Phase | Status | Features |
|-------|--------|---------|
| 1 | ✅ Complete | CLI chat, memory, personality, Ollama |
| 2 | 🔜 Next | Voice input/output, wake word "Joseph" |
| 3 | 🔜 | Browser automation, desktop control |
| 4 | 🔜 | Advanced memory, emotional context |
| 5 | 🔜 | Scheduling, reminders, autonomous tasks |

---

## Troubleshooting

**"Cannot connect to Ollama"**
→ Run `ollama serve` in a separate terminal window and keep it open.

**"Model not found"**
→ Run `ollama pull llama3` and wait for it to finish.

**"ModuleNotFoundError"**
→ Make sure your venv is activated: `venv\Scripts\activate`

**Responses are slow**
→ Normal for first response (model loads into memory). Subsequent responses are faster.
→ If consistently slow, try a smaller model: change `OLLAMA_MODEL=qwen2.5:3b` in `.env`

**ChromaDB errors on startup**
→ Joseph still works without it. SQLite memory is always available.
→ Try: `pip install chromadb --upgrade`

---

## Data & Privacy

All data stays on your machine:
- Conversations: `data/memory.db` (SQLite)
- Vector memories: `data/chroma/` (ChromaDB)
- Logs: `logs/joseph.log`

Nothing is sent to the internet. The LLM runs locally via Ollama.
