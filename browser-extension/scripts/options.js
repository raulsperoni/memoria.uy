// options.js - Handles extension settings page

const DEFAULT_API_URL = 'https://memoria.uy';

// Load saved settings on page load
document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();

  // Setup form handlers
  document.getElementById('settings-form').addEventListener('submit', handleSave);
  document.getElementById('reset-btn').addEventListener('click', handleReset);
});

async function loadSettings() {
  const { apiUrl } = await chrome.storage.sync.get({
    apiUrl: DEFAULT_API_URL
  });

  document.getElementById('api-url').value = apiUrl;
}

async function handleSave(e) {
  e.preventDefault();

  const statusDiv = document.getElementById('status');
  const apiUrl = document.getElementById('api-url').value.trim();

  // Basic URL validation
  try {
    new URL(apiUrl);
  } catch (error) {
    showStatus('URL inválida. Usa formato: http://localhost:8000 o https://memoria.uy', 'error');
    return;
  }

  // Remove trailing slash
  const cleanUrl = apiUrl.replace(/\/$/, '');

  // Test connection before saving
  try {
    const response = await fetch(`${cleanUrl}/health/`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000)  // 5 second timeout
    });

    if (!response.ok) {
      throw new Error('Servidor no responde correctamente');
    }

    // Save settings
    await chrome.storage.sync.set({ apiUrl: cleanUrl });

    showStatus('✓ Configuración guardada correctamente', 'success');

  } catch (error) {
    console.error('Connection test failed:', error);
    showStatus(
      `⚠️  No se pudo conectar al servidor, pero la configuración se guardó.
      Verifica que el servidor esté ejecutándose.`,
      'error'
    );

    // Still save even if connection fails (user might start server later)
    await chrome.storage.sync.set({ apiUrl: cleanUrl });
  }
}

async function handleReset() {
  if (!confirm('¿Restablecer a configuración por defecto?')) {
    return;
  }

  await chrome.storage.sync.set({ apiUrl: DEFAULT_API_URL });
  document.getElementById('api-url').value = DEFAULT_API_URL;

  showStatus('✓ Configuración restablecida', 'success');
}

function showStatus(message, type) {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = message;
  statusDiv.className = `status show ${type}`;

  if (type === 'success') {
    setTimeout(() => {
      statusDiv.classList.remove('show');
    }, 3000);
  }
}
