const mongoose = require('mongoose');

async function connecterMongoDB() {
  const uri = process.env.MONGODB_URI || 'mongodb://localhost:27017/astree_chatbot';

  try {
    await mongoose.connect(uri);
    console.log('MongoDB connecte :', uri);
  } catch (erreur) {
    console.error('Erreur de connexion MongoDB :', erreur.message);
    // On ne fait pas planter le serveur si Mongo est indisponible en dev --
    // le chat fonctionne toujours, seul l'historique sera indisponible.
  }
}

module.exports = connecterMongoDB;
