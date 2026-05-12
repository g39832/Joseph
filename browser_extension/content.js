/**
 * content.js — JOSEPH Browser Extension Content Script
 * 
 * Runs on every page. Provides:
 * - Page text extraction for Joseph
 * - Keyboard shortcut (Alt+J) to open Joseph popup
 */

// Alt+J to open Joseph popup
document.addEventListener("keydown", (e) => {
  if (e.altKey && e.key === "j") {
    chrome.runtime.sendMessage({ type: "OPEN_POPUP" });
  }
});

// Listen for requests from popup to get page content
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "GET_PAGE_CONTENT") {
    const clone = document.cloneNode(true);
    clone.querySelectorAll("script, style, nav, footer, header, aside").forEach(el => el.remove());
    const text = (clone.body?.innerText || "").substring(0, 5000);
    sendResponse({ content: text, title: document.title, url: window.location.href });
  }
});
