require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3001;
const { createProxyMiddleware } = require('http-proxy-middleware');

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Proxy all /api routes (except /api/assistant which is handled locally below)
// and /health route to the SANKET-main FastAPI backend
const apiProxy = createProxyMiddleware({
  target: 'http://localhost:8000',
  changeOrigin: true,
});

app.get('/health', (req, res, next) => {
  // Reset url so proxy doesn't strip it
  req.url = '/health';
  apiProxy(req, res, next);
});
app.all('/api/*', (req, res, next) => {
  if (req.path === '/api/assistant' || req.url === '/assistant') {
    next(); // skip proxy for assistant
  } else {
    // using req.originalUrl ensures the proxy receives /api/... instead of just /...
    apiProxy(req, res, next);
  }
});

/* ── Gemini AI Assistant endpoint ─────────────────────────── */
app.post('/api/assistant', async (req, res) => {
  const apiKey = process.env.GEMINI_API_KEY;

  if (!apiKey || apiKey === 'your_gemini_api_key_here') {
    return res.status(503).json({
      error: true,
      message:
        'SANKET Analyst is offline — GEMINI_API_KEY is not configured. Copy .env.example to .env and add your key.',
    });
  }

  const { message, context } = req.body;

  if (!message || typeof message !== 'string' || message.trim().length === 0) {
    return res.status(400).json({ error: true, message: 'Message is required.' });
  }

  if (message.length > 2000) {
    return res.status(400).json({ error: true, message: 'Message exceeds 2 000 character limit.' });
  }

  try {
    const { GoogleGenerativeAI } = require('@google/generative-ai');
    const genAI = new GoogleGenerativeAI(apiKey);
    const systemInstruction = `You are the SANKET Analyst Assistant — a concise, data-driven infrastructure-risk analyst embedded in the SANKET command-center dashboard.

RULES:
1. Base every claim on the dashboard context supplied below. Cite specific metrics (e.g., "Score 92/100", "−27.3 % MoRTH discrepancy").
2. Clearly distinguish hard data from inference. Use phrases like "Data shows…" vs "This suggests…".
3. Never fabricate statistics, project names, or sensor readings that are not in the context.
4. When a critical threshold is exceeded (score ≥ 90, variance > 15 %, stagnation > 30 days) recommend escalation and cite the relevant protocol (Sec. 14 Notice, Emergency Dispatch).
5. Keep answers compact — aim for 3-6 sentences unless the user asks for detail.
6. Use professional, government-operations tone. No emojis.

DASHBOARD CONTEXT (live snapshot):
${JSON.stringify(context, null, 2)}`;

    const model = genAI.getGenerativeModel({ 
      model: 'gemini-3.6-flash',
      systemInstruction: systemInstruction 
    });

    const chat = model.startChat({
      history: []
    });

    const result = await chat.sendMessage(message);
    const response = result.response.text();

    return res.json({ reply: response });
  } catch (err) {
    console.error('Gemini API error:', err.message || err);

    if (err.message?.includes('429') || err.message?.includes('quota')) {
      return res.status(429).json({
        error: true,
        message: 'Rate limit reached. Please wait a moment before retrying.',
      });
    }

    return res.status(500).json({
      error: true,
      message: 'SANKET Analyst encountered an internal error. Please retry.',
    });
  }
});

app.post('/api/assistant/key', (req, res) => {
  const { apiKey } = req.body;
  if (!apiKey) return res.status(400).json({ error: true, message: 'API key is required' });
  
  process.env.GEMINI_API_KEY = apiKey;
  
  try {
    const envPath = path.join(__dirname, '.env');
    let envContent = '';
    if (fs.existsSync(envPath)) {
      envContent = fs.readFileSync(envPath, 'utf8');
      if (envContent.includes('GEMINI_API_KEY=')) {
        envContent = envContent.replace(/GEMINI_API_KEY=.*/, `GEMINI_API_KEY=${apiKey}`);
      } else {
        envContent += `\nGEMINI_API_KEY=${apiKey}\n`;
      }
    } else {
      envContent = `GEMINI_API_KEY=${apiKey}\nPORT=3001\n`;
    }
    fs.writeFileSync(envPath, envContent);
    res.json({ success: true, message: 'API key saved securely.' });
  } catch (err) {
    console.error('Failed to save API key:', err);
    res.status(500).json({ error: true, message: 'Failed to save API key.' });
  }
});

/* ── Catch-all → index.html ──────────────────────────────── */
app.get('*', (_req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`\n  ╔══════════════════════════════════════════╗`);
  console.log(`  ║  SANKET // RISKSYS  —  Server Online       ║`);
  console.log(`  ║  http://localhost:${PORT}                    ║`);
  console.log(`  ╚══════════════════════════════════════════╝\n`);
});
