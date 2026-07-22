# Chatbot RAG ASTREE — Backend (S7)

Architecture :

```
Frontend React  --HTTP-->  Backend Node.js/Express (port 3000)
                                    |
                                    |--HTTP--> Micro-service Python FastAPI (port 8000, ton RAG)
                                    |
                                    +--> MongoDB (historique des conversations)
```

## 1. Lancer le micro-service Python (le RAG)

```bash
cd rag-service
pip install -r requirements.txt --break-system-packages
cp .env.example .env
# edite .env et mets ta cle GROQ_API_KEY

# IMPORTANT : copie ton dossier ./output/chroma_db (celui deja construit
# dans ton notebook de scraping) dans rag-service/output/chroma_db,
# ou ajuste CHROMA_PATH dans .env pour pointer vers son emplacement actuel.

uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Verifie que ca marche : http://localhost:8000/health

## 2. Lancer le backend Node.js

Prerequis : MongoDB doit tourner (localement via `mongod`, ou un cluster Atlas).

```bash
cd backend
npm install
cp .env.example .env
# ajuste .env si besoin (URL MongoDB, URL du service RAG)

npm run dev
```

Verifie que ca marche :
- http://localhost:3000/health
- http://localhost:3000/api-docs (documentation Swagger interactive)

## 3. Tester l'API

### Avec Postman / curl

```bash
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Quelles sont les garanties de l assurance habitation ?"}'
```

Reponse attendue :
```json
{
  "sessionId": "généré automatiquement",
  "reponse": "...",
  "sources": [...],
  "nbChunks": 5,
  "dureeMs": 850
}
```

Renvoie le meme `sessionId` dans les appels suivants pour continuer la
conversation (memoire des 5 derniers echanges) :

```bash
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Et pour le vol ?", "sessionId": "LE_SESSION_ID_RECU"}'
```

Recuperer l'historique :
```bash
curl http://localhost:3000/api/historique/LE_SESSION_ID_RECU
```

### Avec Jest (tests unitaires du backend)

```bash
cd backend
npm test
```

Les tests mockent le service RAG et MongoDB, donc ils tournent sans
dependance externe (pas besoin que Python ou Mongo soient lances).

## Structure du backend

```
backend/
  server.js                     point d'entree
  src/
    routes/chat.routes.js       POST /api/chat, GET /api/historique/:sessionId
    services/ragService.js      appelle le micro-service Python via HTTP
    services/sessionService.js  gere les sessions/messages dans MongoDB
    models/Session.js           schema Mongoose
    models/Message.js           schema Mongoose
    config/db.js                connexion MongoDB
    config/swagger.js           config documentation Swagger
    middlewares/errorHandler.js gestion centralisee des erreurs
  tests/chat.test.js            tests Jest + Supertest
```

## Prochaine etape (S8)

Une fois cette API validee avec Postman, le composant React du widget
chatbot pourra l'appeler directement (POST /api/chat).
