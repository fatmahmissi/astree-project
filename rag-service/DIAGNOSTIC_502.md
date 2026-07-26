# Diagnostic Erreur 502 - Service RAG

## ✅ Corrections appliquées au Backend

### 1. **Chargement des modèles au démarrage**
- Avant : Modèles chargés à la 1ère requête → Timeout 502
- Après : Chargement à `startup` event → Service prêt avant les requêtes
- Vérifie dans les logs : `✓ Modele d'embedding charge`

### 2. **Gestion d'erreur robuste**
- Endpoint `/ask` capture les exceptions
- Logs détaillés pour debugger les vrais problèmes
- Retour 500 au lieu de 502 en cas d'erreur réelle

### 3. **Validation GROQ_API_KEY**
- Vérifie si la clé est configurée au démarrage
- Erreur explicite si manquante

---

## 🔍 Checklist de Diagnostic

### Backend (Service RAG)

- [ ] **Logs au démarrage** - Lance `uvicorn app:app` et vérifie :
  ```
  ✓ Modele d'embedding charge
  ✓ ChromaDB connecte
  ✓ Client GROQ initialise
  ✓ Service pret !
  ```

- [ ] **Variable GROQ_API_KEY** 
  ```bash
  echo $GROQ_API_KEY  # Doit afficher une clé, pas vide
  ```

- [ ] **Test direct du endpoint**
  ```bash
  curl -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -d '{"question":"Comment déclarer un sinistre?"}'
  ```

- [ ] **Logs du serveur** - Cherche des erreurs comme :
  - `❌ Erreur GROQ:`
  - `❌ Erreur dans ask():`
  - `TOKENIZERS_PARALLELISM not set`

- [ ] **Mémoire** - Service RAG consomme 500MB+ au démarrage
  ```bash
  # Windows
  tasklist | find "python"  # Vérifier si "python.exe" existe
  ```

### Frontend

- [ ] **Timeout de la requête** 
  - Frontend doit attendre au minimum 30-60s au premier appel
  - Implémenter retry exponential: 1s, 3s, 5s...

- [ ] **Headers CORS** - Vérifier :
  ```javascript
  const response = await fetch('http://localhost:8000/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: '...' })
  });
  ```

- [ ] **Message d'erreur 502** - Afficher au lieu de crash :
  ```javascript
  if (response.status === 502) {
    // Service en démarrage ou surchargé
    // Réessayer dans 3s
  }
  ```

---

## 📊 Flux d'erreur typique

```
Frontend requête
    ↓
[Attente 60s timeout]
    ↓
Backend: Modèle en train de charger (30-45s)
    ↓
Frontend timeout → 502 ❌
```

**Solution**: Le backend démarre maintenant les modèles immédiatement.

---

## 🚀 Redémarrer et Tester

1. **Backend** :
   ```bash
   cd rag-service
   pip install -r requirements.txt
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Vérifier les logs** - Attendre `✓ Service pret !`

3. **Frontend** - Faire une première requête, attendre réponse

4. **Monitoring** - Observer les logs pendant la requête

---

## 📝 Si l'erreur 502 persiste

**A Chercher**:
- [ ] Crash Python (segmentation fault)
- [ ] GROQ API timeout (rate limit ?)
- [ ] ChromaDB corrupted (supprimer `output/chroma_db/` et recharger données)
- [ ] OOM (Out of Memory) - vérifier RAM disponible

**Commande pour voir les vrais logs** :
```bash
uvicorn app:app --log-level debug
```
