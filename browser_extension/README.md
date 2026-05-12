# JOSEPH Browser Extension

Ask Joseph about any webpage directly from Chrome.

## Install in Chrome

1. Open Chrome and go to: `chrome://extensions/`
2. Enable **Developer mode** (toggle in top right)
3. Click **Load unpacked**
4. Select this folder: `C:\Users\Grayson\Desktop\Joseph\browser_extension`
5. The JOSEPH icon appears in your toolbar

## Usage

- Click the JOSEPH icon in the toolbar to open the chat popup
- Ask Joseph to summarize, explain, or answer questions about the current page
- Right-click selected text → "Ask Joseph about this"
- Right-click anywhere → "Summarize with Joseph"
- Press **Alt+J** on any page to focus the extension

## Requirements

Joseph must be running (`python main.py`) for the extension to work.
The extension connects to `http://localhost:8000` (Joseph's API server).

## Quick Actions

- **Summarize** — Get a 3-5 sentence summary of the page
- **Key Points** — Extract the main points
- **Explain** — Get a simple explanation
- **Save Note** — Save the page info to Joseph's notes
