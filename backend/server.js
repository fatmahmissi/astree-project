require('dotenv').config();

const express = require('express');
const cors = require('cors');
const swaggerUi = require('swagger-ui-express');

const connecterMongoDB = require('./src/config/db');
const swaggerSpec = require('./src/config/swagger');
const chatRoutes = require('./src/routes/chat.routes');
const errorHandler = require('./src/middlewares/errorHandler');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Documentation Swagger : http://localhost:3000/api-docs
app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec));

// Routes principales
app.use('/api', chatRoutes);

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'astree-chatbot-backend' });
});

// Gestion centralisee des erreurs (toujours en dernier)
app.use(errorHandler);

async function demarrer() {
  await connecterMongoDB();
  app.listen(PORT, () => {
    console.log(`Serveur demarre sur http://localhost:${PORT}`);
    console.log(`Documentation API : http://localhost:${PORT}/api-docs`);
  });
}

// On ne demarre le serveur que si ce fichier est execute directement
// (et pas quand il est importe par les tests Jest/Supertest).
if (require.main === module) {
  demarrer();
}

module.exports = app;
