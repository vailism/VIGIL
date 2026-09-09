/* ═══════════════════════════════════════════════════════════
   SANKET // RISKSYS  —  AI Assistant Module
   ═══════════════════════════════════════════════════════════ */

const Assistant = (() => {
  const STORAGE_KEY = 'sanket_assistant_history';

  let isOpen = false;
  let isSending = false;
  let history = [];
  let lastFailedMessage = null;

  /* ── DOM refs ───────────────────────────────────────── */
  const fab        = () => document.getElementById('aiFab');
  const panel      = () => document.getElementById('aiPanel');
  const body       = () => document.getElementById('aiPanelBody');
  const messages   = () => document.getElementById('aiMessages');
  const input      = () => document.getElementById('aiInput');
  const sendBtn    = () => document.getElementById('aiSend');
  const closeBtn   = () => document.getElementById('aiPanelClose');
  const suggestions = () => document.getElementById('aiSuggestions');

  /* ── Persistence ────────────────────────────────────── */
  function loadHistory() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      history = raw ? JSON.parse(raw) : [];
    } catch { history = []; }
  }

  function saveHistory() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-50)));
    } catch { /* quota exceeded — ignore */ }
  }

  /* ── Rendering ──────────────────────────────────────── */
  function renderMessages() {
    const el = messages();
    if (!el) return;

    if (history.length === 0) {
      el.innerHTML = '';
      const sug = suggestions();
      if (sug) sug.style.display = '';
      return;
    }

    const sug = suggestions();
    if (sug) sug.style.display = 'none';

    el.innerHTML = history.map(msg => {
      if (msg.role === 'user') {
        return `<div class="ai-msg ai-msg-user">${escapeHtml(msg.content)}</div>`;
      }
      if (msg.error) {
        return `<div class="ai-msg ai-msg-error">${escapeHtml(msg.content)}<br/><button class="retry-btn" onclick="Assistant.retry()">↻ Retry</button></div>`;
      }
      return `<div class="ai-msg ai-msg-assistant">${formatAssistantMessage(msg.content)}</div>`;
    }).join('');

    scrollToBottom();
  }

  function showLoading() {
    const el = messages();
    if (!el) return;
    const loader = document.createElement('div');
    loader.className = 'ai-loading';
    loader.id = 'aiLoader';
    loader.innerHTML = '<span></span><span></span><span></span>';
    el.appendChild(loader);
    scrollToBottom();
  }

  function hideLoading() {
    const loader = document.getElementById('aiLoader');
    if (loader) loader.remove();
  }

  function scrollToBottom() {
    const b = body();
    if (b) setTimeout(() => b.scrollTop = b.scrollHeight, 50);
  }

  function escapeHtml(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function formatAssistantMessage(text) {
    // Basic markdown-like formatting
    return escapeHtml(text)
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.*?)`/g, '<code style="background:#f1f5f9;padding:1px 4px;border-radius:3px;font-size:10px;">$1</code>')
      .replace(/\n/g, '<br/>');
  }

  /* ── API ────────────────────────────────────────────── */
  async function sendMessage(text) {
    if (!text.trim() || isSending) return;

    lastFailedMessage = null;
    isSending = true;
    const inp = input();
    const btn = sendBtn();
    if (inp) inp.value = '';
    if (btn) btn.disabled = true;

    // Add user message
    history.push({ role: 'user', content: text.trim() });
    renderMessages();
    showLoading();
    saveHistory();

    try {
      const context = window.SANKET_DATA.getAssistantContext();
      const res = await fetch('/api/assistant', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text.trim(), context }),
      });

      const data = await res.json();
      hideLoading();

      if (!res.ok || data.error) {
        lastFailedMessage = text.trim();
        if (data.message === 'API key not configured.') {
          document.getElementById('aiApiKeyWarning').style.display = 'block';
          document.getElementById('aiWelcomeCard').style.display = 'none';
          // Don't push an error message to the history, just wait for key input
          hideLoading();
          isSending = false;
          if (btn) btn.disabled = false;
          return;
        }

        history.push({
          role: 'assistant',
          content: data.message || 'Connection to SANKET Analyst failed. Please retry.',
          error: true,
        });
      } else {
        history.push({ role: 'assistant', content: data.reply });
      }
    } catch (err) {
      hideLoading();
      lastFailedMessage = text.trim();
      history.push({
        role: 'assistant',
        content: 'Network error — unable to reach SANKET Analyst server. Check that the server is running.',
        error: true,
      });
    }

    isSending = false;
    if (btn) btn.disabled = false;
    renderMessages();
    saveHistory();
  }

  function retry() {
    if (lastFailedMessage) {
      // Remove the last error message and the preceding user message to prevent duplication
      if (history.length && history[history.length - 1].error) {
        history.pop();
        if (history.length && history[history.length - 1].role === 'user') {
          history.pop();
        }
      }
      const msg = lastFailedMessage;
      lastFailedMessage = null;
      sendMessage(msg);
    }
  }

  /* ── Panel toggle ───────────────────────────────────── */
  function toggle() {
    isOpen = !isOpen;
    const p = panel();
    const f = fab();
    if (isOpen) {
      p.classList.add('open');
      if (f) f.style.display = 'none';
      const inp = input();
      if (inp) setTimeout(() => inp.focus(), 100);
    } else {
      p.classList.remove('open');
      if (f) f.style.display = '';
    }
  }

  /* ── Init ───────────────────────────────────────────── */
  function init() {
    loadHistory();
    renderMessages();

    fab()?.addEventListener('click', toggle);
    closeBtn()?.addEventListener('click', toggle);

    sendBtn()?.addEventListener('click', () => {
      const val = input()?.value;
      if (val) sendMessage(val);
    });

    input()?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const val = input()?.value;
        if (val) sendMessage(val);
      }
    });

    // Suggestion buttons
    document.querySelectorAll('.ai-suggestion').forEach(btn => {
      btn.addEventListener('click', () => {
        const prompt = btn.dataset.prompt;
        if (prompt) sendMessage(prompt);
      });
    });

    // API Key Save Button
    const saveKeyBtn = document.getElementById('saveApiKeyBtn');
    if (saveKeyBtn) {
      saveKeyBtn.addEventListener('click', async () => {
        const key = document.getElementById('tempApiKeyInput').value.trim();
        if (!key) return;
        saveKeyBtn.textContent = 'Saving...';
        try {
          const res = await fetch('/api/assistant/key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ apiKey: key })
          });
          if (res.ok) {
            document.getElementById('aiApiKeyWarning').style.display = 'none';
            document.getElementById('aiWelcomeCard').style.display = 'flex';
            retry(); // Retry last failed message
          } else {
            saveKeyBtn.textContent = 'Failed!';
            setTimeout(() => saveKeyBtn.textContent = 'Save Key', 2000);
          }
        } catch (e) {
          saveKeyBtn.textContent = 'Error!';
          setTimeout(() => saveKeyBtn.textContent = 'Save Key', 2000);
        }
      });
    }
  }

  return { init, retry, toggle, sendMessage };
})();
