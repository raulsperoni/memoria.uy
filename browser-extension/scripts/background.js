// background.js - Service worker for extension

// Listen for extension installation
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('Memoria.uy extension installed');

    // Set default API URL
    chrome.storage.sync.set({
      apiUrl: 'http://localhost:8000'
    });

    // Open welcome page
    chrome.tabs.create({
      url: 'https://memoria.uy/bienvenida'
    });
  }
});

// Optional: Badge to show if article was already voted on
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    await checkAndUpdateBadge(tab);
  } catch (error) {
    console.error('Error checking badge:', error);
  }
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    await checkAndUpdateBadge(tab);
  }
});

async function checkAndUpdateBadge(tab) {
  if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('about:')) {
    return;
  }

  try {
    const { apiUrl } = await chrome.storage.sync.get({ apiUrl: 'http://localhost:8000' });
    const { sessionId } = await chrome.storage.local.get('sessionId');

    if (!sessionId) return;

    const response = await fetch(
      `${apiUrl}/api/check-vote/?url=${encodeURIComponent(tab.url)}`,
      {
        headers: {
          'X-Extension-Session': sessionId
        }
      }
    );

    if (response.ok) {
      const data = await response.json();

      if (data.voted) {
        // Show badge indicating already voted
        chrome.action.setBadgeText({ text: '✓', tabId: tab.id });
        chrome.action.setBadgeBackgroundColor({ color: '#059669', tabId: tab.id });
      } else {
        chrome.action.setBadgeText({ text: '', tabId: tab.id });
      }
    }
  } catch (error) {
    // Silently fail - server might be down
    console.error('Error checking vote status:', error);
  }
}

// Handle messages from popup or content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'clearBadge') {
    chrome.action.setBadgeText({ text: '', tabId: sender.tab.id });
    sendResponse({ success: true });
  }
  return true;
});
