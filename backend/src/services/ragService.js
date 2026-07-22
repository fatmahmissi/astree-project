const axios = require('axios');

const RAG_SERVICE_URL = process.env.RAG_SERVICE_URL || 'http://localhost:8000';

/**
 * Appelle le micro-service Python (FastAPI) qui execute le pipeline RAG.
 * @param {string} question
 * @param {Array<{question: string, reponse: string}>} historique
 * @returns {Promise<{reponse: string, sources: Array, nbChunks: number, dureeMs: number}>}
 */
async function interrogerRAG(question, historique = []) {
  try {
    const { data } = await axios.post(
      `${RAG_SERVICE_URL}/ask`,
      { question, history: historique },
      { timeout: 30000 } // le LLM peut prendre plusieurs secondes
    );

    return {
      reponse: data.reponse,
      sources: data.sources.map((s) => ({
        url: s.url,
        pageTitre: s.page_titre,
        distance: s.distance,
      })),
      nbChunks: data.nb_chunks,
      dureeMs: data.duree_ms,
    };
  } catch (erreur) {
    if (erreur.code === 'ECONNREFUSED') {
      throw new Error(
        'Le service RAG Python est injoignable. Verifie qu\'il tourne sur ' + RAG_SERVICE_URL
      );
    }
    if (erreur.response) {
      throw new Error(`Erreur du service RAG (${erreur.response.status}): ${erreur.response.data?.detail || erreur.message}`);
    }
    throw erreur;
  }
}

module.exports = { interrogerRAG };
