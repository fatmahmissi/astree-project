require('dotenv').config();

const express = require('express');
const cors = require('cors');
const path = require('path');
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

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'astree-chatbot-backend' });
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