require('dotenv').config();

const express = require('express');
const cors = require('cors');
const path = require('path');
const axios = require('axios');
const swaggerUi = require('swagger-ui-express');

const connecterMongoDB = require('./src/config/db');
const swaggerSpec = require('./src/config/swagger');
const chatRoutes = require('./src/routes/chat.routes');
const errorHandler = require('./src/middlewares/errorHandler');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec));
app.use('/api', chatRoutes);

app.get('/health', async (req, res) => {
  const RAG_SERVICE_URL = process.env.RAG_SERVICE_URL || 'http://localhost:8000';

  // Basic local health info
  const healthInfo = { status: 'ok', service: 'astree-chatbot-backend' };

  try {
    // Try RAG health endpoint first, fallback to base URL
    const urlsToTry = [`${RAG_SERVICE_URL.replace(/\/$/, '')}/health`, RAG_SERVICE_URL];

    let ragOk = false;
    let ragResp = null;

    for (const url of urlsToTry) {
      try {
        ragResp = await axios.get(url, { timeout: 3000 });
        ragOk = ragResp.status >= 200 && ragResp.status < 300;
        if (ragOk) break;
      } catch (e) {
        // ignore and try next
      }
    }

    if (!ragOk) {
      return res.status(503).json({ ...healthInfo, rag: 'unavailable' });
    }

    return res.json({ ...healthInfo, rag: 'available' });
  } catch (err) {
    console.error('Health check error:', err.message || err);
    return res.status(503).json({ ...healthInfo, rag: 'error' });
  }
});

// Sert le frontend build (React) depuis backend/public
app.use(express.static(path.join(__dirname, 'public')));

// Toute route non-API renvoie index.html (nécessaire pour le routing côté React)
app.get(/^(?!\/api|\/api-docs|\/health).*/, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.use(errorHandler);

async function demarrer() {
  await connecterMongoDB();
  const server = app.listen(PORT, () => {
    console.log(`Serveur demarre sur http://localhost:${PORT}`);
    console.log(`Documentation API : http://localhost:${PORT}/api-docs`);
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.error(`Le port ${PORT} est deja utilise. Verifiez qu'aucun autre processus n'utilise ce port ou changez-le dans .env.`);
    } else {
      console.error('Erreur de demarrage du serveur :', err);
    }
    process.exit(1);
  });
}

if (require.main === module) {
  demarrer();
}

module.exports = app;