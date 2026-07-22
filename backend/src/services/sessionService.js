const Session = require('../models/Session');
const Message = require('../models/Message');

/**
 * Recupere une session existante ou en cree une nouvelle.
 */
async function obtenirOuCreerSession(sessionId) {
  let session = await Session.findOne({ sessionId });
  if (!session) {
    session = await Session.create({ sessionId });
  } else {
    session.derniereActivite = new Date();
    await session.save();
  }
  return session;
}

/**
 * Enregistre un echange question/reponse dans une session.
 */
async function enregistrerMessage(sessionId, { question, reponse, sources, nbChunks, dureeMs }) {
  return Message.create({
    sessionId,
    question,
    reponse,
    sources,
    nbChunks,
    dureeMs,
  });
}

/**
 * Recupere l'historique des messages d'une session, du plus ancien au plus recent.
 */
async function obtenirHistorique(sessionId, limite = 50) {
  return Message.find({ sessionId })
    .sort({ createdAt: 1 })
    .limit(limite)
    .lean();
}

/**
 * Recupere les N derniers echanges pour donner du contexte au LLM
 * (utilise en interne par la route /chat, pas expose directement).
 */
async function obtenirDernierEchanges(sessionId, n = 5) {
  const messages = await Message.find({ sessionId })
    .sort({ createdAt: -1 })
    .limit(n)
    .lean();
  return messages.reverse().map((m) => ({ question: m.question, reponse: m.reponse }));
}

module.exports = {
  obtenirOuCreerSession,
  enregistrerMessage,
  obtenirHistorique,
  obtenirDernierEchanges,
};
