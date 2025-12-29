// popup.js - Handles popup UI and voting logic

const API_BASE_URL = 'http://localhost:8000';  // Will be configurable
let currentTab = null;
let selectedVote = null;

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  // Get current tab info
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTab = tab;

  // Display article info
  document.getElementById('article-title').textContent = tab.title || 'Sin título';
  document.getElementById('article-url').textContent = tab.url;

  // Setup vote buttons
  document.querySelectorAll('.vote-btn').forEach(btn => {
    btn.addEventListener('click', () => handleVoteSelection(btn));
  });

  // Setup submit button
  document.getElementById('submit-btn').addEventListener('click', handleSubmit);

  // Setup config link
  document.getElementById('config-link').addEventListener('click', (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });

  // Check if article already exists and has user's vote
  await checkExistingVote();
});

function handleVoteSelection(button) {
  // Remove previous selection
  document.querySelectorAll('.vote-btn').forEach(btn => {
    btn.classList.remove('selected');
  });

  // Select this button
  button.classList.add('selected');
  selectedVote = button.dataset.vote;

  // Enable submit button
  document.getElementById('submit-btn').disabled = false;
}

async function handleSubmit() {
  if (!selectedVote) return;

  const submitBtn = document.getElementById('submit-btn');
  const statusDiv = document.getElementById('status');

  // Disable button and show loading
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span>Enviando...';
  statusDiv.classList.remove('show', 'success', 'error');

  try {
    // Extract article HTML from content script
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Send message to content script to get HTML
    let response;
    try {
      response = await chrome.tabs.sendMessage(tab.id, { action: 'getArticleData' });
    } catch (error) {
      // Content script not loaded yet - inject it
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['scripts/content.js']
      });

      // Wait a bit and try again
      await new Promise(resolve => setTimeout(resolve, 100));
      response = await chrome.tabs.sendMessage(tab.id, { action: 'getArticleData' });
    }

    if (!response || !response.html) {
      throw new Error('No se pudo extraer el HTML de la página');
    }

    // Get API URL from storage
    const { apiUrl } = await chrome.storage.sync.get({ apiUrl: API_BASE_URL });

    // Submit to backend
    const result = await submitArticle({
      url: tab.url,
      title: tab.title,
      html: response.html,
      metadata: response.metadata,  // Include extracted metadata
      vote: selectedVote
    }, apiUrl);

    // Show success
    statusDiv.textContent = '¡Voto enviado correctamente!';
    statusDiv.classList.add('show', 'success');
    submitBtn.innerHTML = '✓ Enviado';

    // Close popup after 1.5 seconds
    setTimeout(() => window.close(), 1500);

  } catch (error) {
    console.error('Error submitting:', error);
    statusDiv.textContent = error.message || 'Error al enviar. Inténtalo de nuevo.';
    statusDiv.classList.add('show', 'error');
    submitBtn.disabled = false;
    submitBtn.innerHTML = 'Reintentar';
  }
}

async function submitArticle(data, apiUrl) {
  // Get or create session ID
  let { sessionId } = await chrome.storage.local.get('sessionId');

  if (!sessionId) {
    sessionId = generateSessionId();
    await chrome.storage.local.set({ sessionId });
  }

  const response = await fetch(`${apiUrl}/api/submit-from-extension/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Extension-Session': sessionId
    },
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || `Error ${response.status}`);
  }

  return await response.json();
}

async function checkExistingVote() {
  try {
    const { apiUrl } = await chrome.storage.sync.get({ apiUrl: API_BASE_URL });
    const { sessionId } = await chrome.storage.local.get('sessionId');

    if (!sessionId) return;

    const response = await fetch(
      `${apiUrl}/api/check-vote/?url=${encodeURIComponent(currentTab.url)}`,
      {
        headers: {
          'X-Extension-Session': sessionId
        }
      }
    );

    if (response.ok) {
      const data = await response.json();
      if (data.voted && data.opinion) {
        // Pre-select the user's existing vote
        const btn = document.querySelector(`.vote-btn[data-vote="${data.opinion}"]`);
        if (btn) {
          btn.classList.add('selected');
          selectedVote = data.opinion;
          document.getElementById('submit-btn').disabled = false;
          document.getElementById('submit-btn').textContent = 'Actualizar voto';
        }
      }
    }
  } catch (error) {
    console.error('Error checking existing vote:', error);
    // Fail silently - not critical
  }
}

function generateSessionId() {
  return 'ext_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}
