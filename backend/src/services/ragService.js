const axios = require('axios');

const RAG_SERVICE_URL = process.env.RAG_SERVICE_URL || 'http://localhost:8000';
const RETRY_STATUS = [502, 503, 504];
const MAX_RETRIES = 2;

function pause(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Appelle le micro-service Python (FastAPI) qui execute le pipeline RAG.
 * @param {string} question
 * @param {Array<{question: string, reponse: string}>} historique
 * @returns {Promise<{reponse: string, sources: Array, nbChunks: number, dureeMs: number}>}
 */
async function interrogerRAG(question, historique = []) {
  let tentative = 0;

  while (true) {
    tentative += 1;

    try {
      const { data } = await axios.post(
        `${RAG_SERVICE_URL}/ask`,
        { question, history: historique },
        { timeout: 60000 } // le LLM peut prendre plusieurs secondes
      );

      const sources = Array.isArray(data.sources) ? data.sources : [];

      return {
        reponse: data.reponse,
        sources: sources.map((s) => ({
          url: s.url,
          pageTitre: s.page_titre,
          distance: s.distance,
        })),
        nbChunks: data.nb_chunks ?? 0,
        dureeMs: data.duree_ms ?? 0,
      };
    } catch (erreur) {
      const status = erreur.response?.status;
      const estTransitoire = status && RETRY_STATUS.includes(status);

      if (estTransitoire && tentative <= MAX_RETRIES) {
        console.warn(
          `RAG service temporairement indisponible (status ${status}). Tentative ${tentative}/${MAX_RETRIES}. Reessai dans ${tentative * 500}ms.`
        );
        await pause(tentative * 500);
        continue;
      }

      if (erreur.code === 'ECONNREFUSED') {
        const err = new Error(
          'Le service RAG Python est injoignable. Verifie qu\'il tourne sur ' + RAG_SERVICE_URL
        );
        err.status = 503;
        throw err;
      }

      if (erreur.response) {
        const message = erreur.response.data?.detail || erreur.message || 'Erreur inconnue du service RAG';
        const err = new Error(`Erreur du service RAG (${status}): ${message}`);

        if (estTransitoire) {
          err.status = 503;
        }

        throw err;
      }

      throw erreur;
    }
  }
}

module.exports = { interrogerRAG };
