/**
 * background.js — JOSEPH Browser Extension Service Worker
 * 
 * Handles:
 * - Context menu (right-click) integration
 * - Background API communication
 * - Extension lifecycle
 */

const JOSEPH_API = "http://localhost:8000";

// ------------------------------------------------------------------ //
// Context Menu Setup
// ------------------------------------------------------------------ //

chrome.runtime.onInstalled.addListener(() => {
  // Right-click menu on selected text
  chrome.contextMenus.create({
    id: "joseph-ask",
    title: "Ask Joseph about this",
    contexts: ["selection"],
  });

  chrome.contextMenus.create({
    id: "joseph-summarize",
    title: "Summarize with Joseph",
    contexts: ["page"],
  });

  chrome.contextMenus.create({
    id: "joseph-save-note",
    title: "Save as Joseph note",
    contexts: ["selection"],
  });

  console.log("JOSEPH extension installed");
});

// ------------------------------------------------------------------ //
// Context Menu Handlers
// ------------------------------------------------------------------ //

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "joseph-ask" && info.selectionText) {
    await sendToJoseph(
      `The user selected this text on "${tab.title}": "${info.selectionText}". What can you tell them about it?`,
      tab
    );
  }

  if (info.menuItemId === "joseph-summarize") {
    await sendToJoseph(
      `Summarize the page "${tab.title}" (${tab.url}) in 3-5 sentences.`,
      tab
    );
  }

  if (info.menuItemId === "joseph-save-note" && info.selectionText) {
    await saveNote(info.selectionText, tab.title);
  }
});

// ------------------------------------------------------------------ //
// API Communication
// ------------------------------------------------------------------ //

async function sendToJoseph(message, tab) {
  try {
    const resp = await fetch(`${JOSEPH_API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, include_memory: false }),
    });

    if (resp.ok) {
      const data = await resp.json();
      // Show response in a notification or badge
      chrome.action.setBadgeText({ text: "✓", tabId: tab.id });
      chrome.action.setBadgeBackgroundColor({ color: "#4d9de0" });
      setTimeout(() => chrome.action.setBadgeText({ text: "" }), 3000);
    }
  } catch (e) {
    console.error("Joseph API error:", e);
  }
}

async function saveNote(content, pageTitle) {
  try {
    await fetch(`${JOSEPH_API}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: `From "${pageTitle}": ${content}`,
        category: "web",
      }),
    });
  } catch (e) {
    console.error("Save note error:", e);
  }
}

// ------------------------------------------------------------------ //
// Message handling from popup/content scripts
// ------------------------------------------------------------------ //

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "CHECK_CONNECTION") {
    fetch(`${JOSEPH_API}/health`)
      .then(r => r.json())
      .then(data => sendResponse({ connected: true, data }))
      .catch(() => sendResponse({ connected: false }));
    return true; // Keep channel open for async response
  }
});
