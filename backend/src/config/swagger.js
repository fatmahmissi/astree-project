const swaggerJsdoc = require('swagger-jsdoc');

const options = {
  definition: {
    openapi: '3.0.0',
    info: {
      title: 'API Chatbot ASTREE',
      version: '1.0.0',
      description:
        'API REST pour le chatbot RAG d\'ASTREE Assurances. ' +
        'Permet d\'envoyer des questions et de recuperer l\'historique des conversations.',
    },
    servers: [
      {
        url: 'http://localhost:3000',
        description: 'Serveur local de developpement',
      },
    ],
  },
  apis: ['./src/routes/*.js'],
};

const swaggerSpec = swaggerJsdoc(options);

module.exports = swaggerSpec;
