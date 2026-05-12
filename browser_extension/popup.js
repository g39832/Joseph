/**
 * popup.js — JOSEPH Browser Extension
 * 
 * Handles the popup UI logic:
 * - Connects to Joseph's local API (localhost:8000)
 * - Sends page content with user questions
 * - Displays responses in the chat UI
 */

const JOSEPH_API = "http://localhost:8000";
let currentPageContent = "";
let currentPageTitle = "";
let currentPageUrl = "";

// ------------------------------------------------------------------ //
// Initialization
// ------------------------------------------------------------------ //

document.addEventListener("DOMContentLoaded", async () => {
  await checkConnection();
  await getPageContext();

  // Enter key to send
  document.getElementById("inputBox").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
});

async function checkConnection() {
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("statusText");

  try {
    const resp = await fetch(`${JOSEPH_API}/health`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) {
      const data = await resp.json();
      dot.classList.remove("offline");
      text.textContent = `Connected · ${data.model || "Joseph"}`;
    } else {
      throw new Error("Not OK");
    }
  } catch (e) {
    dot.classList.add("offline");
    text.textContent = "Joseph not running — start main.py";
  }
}

async function getPageContext() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentPageUrl = tab.url || "";
    currentPageTitle = tab.title || "Unknown page";

    document.getElementById("pageTitle").textContent =
      currentPageTitle.length > 50
        ? currentPageTitle.substring(0, 50) + "..."
        : currentPageTitle;

    // Get page text content via content script
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          // Extract readable text from page
          const clone = document.cloneNode(true);
          // Remove scripts, styles, nav
          clone.querySelectorAll("script, style, nav, footer, header, aside").forEach(el => el.remove());
          return (clone.body?.innerText || "").substring(0, 3000);
        },
      });
      currentPageContent = results?.[0]?.result || "";
    } catch (e) {
      currentPageContent = "";
    }
  } catch (e) {
    console.error("Page context error:", e);
  }
}

// ------------------------------------------------------------------ //
// Messaging
// ------------------------------------------------------------------ //

async function sendMessage() {
  const input = document.getElementById("inputBox");
  const message = input.value.trim();
  if (!message) return;

  input.value = "";
  addMessage("user", message);
  setThinking(true);

  try {
    // Build message with page context
    let fullMessage = message;
    if (currentPageContent) {
      fullMessage = `[User is on page: "${currentPageTitle}" (${currentPageUrl})]\n\n` +
        `Page content:\n${currentPageContent}\n\n` +
        `User question: ${message}`;
    }

    const resp = await fetch(`${JOSEPH_API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: fullMessage,
        include_memory: true,
      }),
      signal: AbortSignal.timeout(30000),
    });

    if (!resp.ok) throw new Error(`API error: ${resp.status}`);

    const data = await resp.json();
    addMessage("joseph", data.response);

  } catch (e) {
    if (e.name === "TimeoutError") {
      addMessage("joseph", "That took too long. Make sure Joseph is running and try again.");
    } else {
      addMessage("joseph", `Connection error: ${e.message}. Is Joseph running?`);
    }
  } finally {
    setThinking(false);
  }
}

function quickAction(action) {
  document.getElementById("inputBox").value = action;
  sendMessage();
}

// ------------------------------------------------------------------ //
// UI Helpers
// ------------------------------------------------------------------ //

function addMessage(role, text) {
  const chatArea = document.getElementById("chatArea");

  const messageDiv = document.createElement("div");
  messageDiv.className = "message";

  const nameSpan = document.createElement("span");
  nameSpan.className = `message-name ${role}`;
  nameSpan.textContent = role === "joseph" ? "Joseph" : "You";

  const bubble = document.createElement("div");
  bubble.className = `message-bubble ${role}`;
  bubble.textContent = text;

  messageDiv.appendChild(nameSpan);
  messageDiv.appendChild(bubble);
  chatArea.appendChild(messageDiv);

  // Scroll to bottom
  chatArea.scrollTop = chatArea.scrollHeight;
}

function setThinking(thinking) {
  const indicator = document.getElementById("thinking");
  const sendBtn = document.getElementById("sendBtn");

  if (thinking) {
    indicator.classList.add("visible");
    sendBtn.disabled = true;
  } else {
    indicator.classList.remove("visible");
    sendBtn.disabled = false;
  }
}
