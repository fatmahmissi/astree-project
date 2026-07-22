const request = require('supertest');

// On mocke le service RAG pour ne pas dependre d'un vrai appel HTTP/LLM
// pendant les tests -- plus rapide et deterministe.
jest.mock('../src/services/ragService', () => ({
  interrogerRAG: jest.fn(),
}));

// On mocke aussi Mongo pour ne pas dependre d'une vraie base pendant les tests.
jest.mock('../src/services/sessionService', () => ({
  obtenirOuCreerSession: jest.fn().mockResolvedValue({}),
  enregistrerMessage: jest.fn().mockResolvedValue({}),
  obtenirHistorique: jest.fn().mockResolvedValue([]),
  obtenirDernierEchanges: jest.fn().mockResolvedValue([]),
}));

const { interrogerRAG } = require('../src/services/ragService');
const { obtenirHistorique } = require('../src/services/sessionService');
const app = require('../server');

describe('POST /api/chat', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  test('retourne 400 si la question est manquante', async () => {
    const res = await request(app).post('/api/chat').send({});
    expect(res.status).toBe(400);
    expect(res.body.erreur).toBe(true);
  });

  test('retourne 400 si la question est une chaine vide', async () => {
    const res = await request(app).post('/api/chat').send({ question: '   ' });
    expect(res.status).toBe(400);
  });

  test('retourne la reponse du RAG avec un sessionId genere si absent', async () => {
    interrogerRAG.mockResolvedValue({
      reponse: 'La garantie prêt démarre dès la signature du contrat.',
      sources: [{ url: 'https://www.astree.com.tn/fr/particulier/garantie-pret', pageTitre: 'Garantie prêt', distance: 0.4 }],
      nbChunks: 3,
      dureeMs: 850,
    });

    const res = await request(app)
      .post('/api/chat')
      .send({ question: "Qu'est-ce que la garantie pret ?" });

    expect(res.status).toBe(200);
    expect(res.body.sessionId).toBeDefined();
    expect(res.body.reponse).toContain('garantie prêt');
    expect(res.body.sources).toHaveLength(1);
    expect(interrogerRAG).toHaveBeenCalledWith("Qu'est-ce que la garantie pret ?", []);
  });

  test('reutilise le sessionId fourni par le client', async () => {
    interrogerRAG.mockResolvedValue({
      reponse: 'Reponse test',
      sources: [],
      nbChunks: 0,
      dureeMs: 100,
    });

    const res = await request(app)
      .post('/api/chat')
      .send({ question: 'Test', sessionId: 'session-abc-123' });

    expect(res.status).toBe(200);
    expect(res.body.sessionId).toBe('session-abc-123');
  });

  test('retourne 503 si le service RAG est injoignable', async () => {
    interrogerRAG.mockRejectedValue(new Error('Le service RAG Python est injoignable. Verifie qu\'il tourne sur http://localhost:8000'));

    const res = await request(app)
      .post('/api/chat')
      .send({ question: 'Une question' });

    expect(res.status).toBe(503);
    expect(res.body.erreur).toBe(true);
  });
});

describe('GET /api/historique/:sessionId', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  test('retourne la liste des messages pour une session existante', async () => {
    obtenirHistorique.mockResolvedValue([
      {
        question: 'Question 1',
        reponse: 'Reponse 1',
        sources: [],
        createdAt: new Date('2026-07-01T10:00:00Z'),
      },
      {
        question: 'Question 2',
        reponse: 'Reponse 2',
        sources: [],
        createdAt: new Date('2026-07-01T10:01:00Z'),
      },
    ]);

    const res = await request(app).get('/api/historique/session-abc-123');

    expect(res.status).toBe(200);
    expect(res.body.sessionId).toBe('session-abc-123');
    expect(res.body.messages).toHaveLength(2);
    expect(res.body.messages[0].question).toBe('Question 1');
  });

  test('retourne une liste vide pour une session inconnue', async () => {
    obtenirHistorique.mockResolvedValue([]);

    const res = await request(app).get('/api/historique/session-inconnue');

    expect(res.status).toBe(200);
    expect(res.body.messages).toHaveLength(0);
  });
});

describe('GET /health', () => {
  test('retourne le statut du serveur', async () => {
    const res = await request(app).get('/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
  });
});
