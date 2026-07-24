const express = require('express');
const { v4: uuidv4 } = require('uuid');

const { interrogerRAG } = require('../services/ragService');
const {
  obtenirOuCreerSession,
  enregistrerMessage,
  obtenirHistorique,
  obtenirDernierEchanges,
  obtenirHistoriqueGlobal,
} = require('../services/sessionService');

const router = express.Router();

/**
 * @openapi
 * /api/chat:
 *   post:
 *     summary: Envoyer une question au chatbot et recevoir une reponse
 *     tags: [Chat]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required:
 *               - question
 *             properties:
 *               question:
 *                 type: string
 *                 example: Quelles sont les garanties de l'assurance habitation ?
 *               sessionId:
 *                 type: string
 *                 description: Identifiant de conversation. Si absent, une nouvelle session est creee.
 *                 example: 550e8400-e29b-41d4-a716-446655440000
 *     responses:
 *       200:
 *         description: Reponse du chatbot
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 sessionId:
 *                   type: string
 *                 reponse:
 *                   type: string
 *                 sources:
 *                   type: array
 *                   items:
 *                     type: object
 *                     properties:
 *                       url:
 *                         type: string
 *                       pageTitre:
 *                         type: string
 *                       distance:
 *                         type: number
 *                 nbChunks:
 *                   type: integer
 *                 dureeMs:
 *                   type: integer
 *       400:
 *         description: Question manquante ou invalide
 *       503:
 *         description: Le service RAG Python est indisponible
 */
router.post('/chat', async (req, res, next) => {
  try {
    const { question, sessionId: sessionIdRecue } = req.body;

    if (!question || typeof question !== 'string' || !question.trim()) {
      return res.status(400).json({ erreur: true, message: 'Le champ "question" est requis.' });
    }

    const sessionId = sessionIdRecue || uuidv4();
    await obtenirOuCreerSession(sessionId);

    const historique = await obtenirDernierEchanges(sessionId, 5);

    const resultat = await interrogerRAG(question.trim(), historique);

    await enregistrerMessage(sessionId, {
      question: question.trim(),
      reponse: resultat.reponse,
      sources: resultat.sources,
      nbChunks: resultat.nbChunks,
      dureeMs: resultat.dureeMs,
    });

    res.json({
      sessionId,
      reponse: resultat.reponse,
      sources: resultat.sources,
      nbChunks: resultat.nbChunks,
      dureeMs: resultat.dureeMs,
    });
  }  catch (erreur) {
    if (
      erreur.message.includes('injoignable') ||
      erreur.response?.status === 502
    ) {
      erreur.status = 503;
    }
    next(erreur);
  }
});

/**
 * @openapi
 * /api/historique/{sessionId}:
 *   get:
 *     summary: Recuperer l'historique des messages d'une conversation
 *     tags: [Chat]
 *     parameters:
 *       - in: path
 *         name: sessionId
 *         required: true
 *         schema:
 *           type: string
 *         description: Identifiant de la session
 *     responses:
 *       200:
 *         description: Liste des messages de la session, du plus ancien au plus recent
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 sessionId:
 *                   type: string
 *                 messages:
 *                   type: array
 *                   items:
 *                     type: object
 *                     properties:
 *                       question:
 *                         type: string
 *                       reponse:
 *                         type: string
 *                       createdAt:
 *                         type: string
 *                         format: date-time
 *       400:
 *         description: sessionId manquant
 */
router.get('/historique/:sessionId', async (req, res, next) => {
  try {
    const { sessionId } = req.params;

    if (!sessionId) {
      return res.status(400).json({ erreur: true, message: 'sessionId requis.' });
    }

    const messages = await obtenirHistorique(sessionId);

    res.json({
      sessionId,
      messages: messages.map((m) => ({
        question: m.question,
        reponse: m.reponse,
        sources: m.sources,
        createdAt: m.createdAt,
      })),
    });
  } catch (erreur) {
    next(erreur);
  }
});

/**
 * @openapi
 * /api/historique/global:
 *   get:
 *     summary: Recuperer l'historique global de toutes les sessions
 *     tags: [Chat]
 *     responses:
 *       200:
 *         description: Liste des echanges de toutes les sessions
 *         content:
 *           application/json:
 *             schema:
 *               type: array
 *               items:
 *                 type: object
 *                 properties:
 *                   id:
 *                     type: string
 *                   sessionId:
 *                     type: string
 *                   question:
 *                     type: string
 *                   reponse:
 *                     type: string
 *                   sources:
 *                     type: array
 *                     items:
 *                       type: object
 *                   createdAt:
 *                     type: string
 *                     format: date-time
 */
router.get('/historique/global', async (req, res, next) => {
  try {
    const messages = await obtenirHistoriqueGlobal();

    res.json(
      messages.map((m) => ({
        id: m._id,
        sessionId: m.sessionId,
        question: m.question,
        reponse: m.reponse,
        sources: m.sources,
        createdAt: m.createdAt,
      }))
    );
  } catch (erreur) {
    next(erreur);
  }
});

module.exports = router;
