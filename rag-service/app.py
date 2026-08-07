"""
Micro-service FastAPI RAG pour ASTREE Assurances.
Utilise fastembed (sans torch) pour reduire l'empreinte memoire sur Render.

Lancement local :
    pip install -r requirements.txt
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TORCH_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import json
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone

import chromadb
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel

load_dotenv()

# ============================================================
# Config
# ============================================================
CHROMA_PATH = os.getenv("CHROMA_PATH", "./output/chroma_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "astree_rag_v2")
SUPPORTED_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", SUPPORTED_EMBEDDING_MODEL)
if EMBEDDING_MODEL_NAME in {
    "intfloat/multilingual-e5-small",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
}:
    EMBEDDING_MODEL_NAME = SUPPORTED_EMBEDDING_MODEL

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "500"))

# Validation des variables critiques
if not GROQ_API_KEY:
    print("⚠️  ATTENTION: GROQ_API_KEY n'est pas definie !")
else:
    print(f"✓ GROQ_API_KEY configurée (modele: {GROQ_MODEL})")

TOP_K_RETRIEVAL = 12
TOP_K_FINAL = 5
MAX_DISTANCE = 0.60
BOOST_PAR_MOT_CLE = 0.08
LOG_FILE = os.getenv("LOG_FILE", "./output/admin_logs.json")
MAX_LOG_ENTRIES = int(os.getenv("MAX_LOG_ENTRIES", "5000"))

STOPWORDS_FR = {
    "quel", "quels", "quelle", "quelles", "que", "qu", "est", "ce", "de", "des",
    "du", "la", "le", "les", "un", "une", "pour", "avec", "comment", "dans", "sur",
    "mon", "ma", "mes", "suis", "je", "vous", "votre", "vos", "au", "aux", "en", "et", "ou",
}

URLS_GENERIQUES = {
    "https://www.astree.com.tn/fr/faq",
    "https://www.astree.com.tn/fr/agences",
    "https://www.astree.com.tn/fr/particuliers",
    "https://www.astree.com.tn/fr/entreprises-professionnels",
}

SYNONYMES_METIER = {
    "contact": {"telephone", "numero", "joindre", "contacter"},
    "telephone": {"contact", "numero", "joindre", "contacter"},
    "numero": {"telephone", "contact", "joindre", "contacter"},
    "joindre": {"contact", "telephone", "numero", "contacter"},
    "contacter": {"contact", "telephone", "numero", "joindre"},
}

REFUS_EXACT = "Je n'ai pas trouve cette information dans la documentation ASTREE."
HORS_SUJET_EXACT = (
    "Cette question ne concerne pas les services ou produits ASTREE.\n"
    "Je peux uniquement repondre aux questions liees aux assurances ASTREE."
)
GREETING_MESSAGE = (
    "Bonjour, je suis l'assistant ASTREE Assurances. "
    "Comment puis-je vous aider concernant vos assurances (habitation, auto, voyage...) ? "
    "Je m'appuie sur la documentation officielle pour vous répondre."
)

SYSTEM_PROMPT = """Tu es l'assistant officiel d'ASTREE Assurances.

Tu dois repondre uniquement a partir des documents du CONTEXTE.

REGLES OBLIGATOIRES :

1. N'invente jamais une information.
2. N'utilise jamais tes connaissances personnelles.
3. Avant de repondre, verifie qu'au moins un document repond reellement a la question.
4. Ignore tous les documents qui concernent un produit ou service different de
   celui explicitement demande dans la question, meme s'ils appartiennent a la
   meme categorie generale (assurance).
5. Si plusieurs documents concernent le meme produit, combine leurs informations
   en une reponse unique et coherente, sans repeter les details redondants et
   sans melanger des informations venant de produits differents.
6. Si aucune information pertinente n'existe dans le contexte, reponds exactement :
   Je n'ai pas trouve cette information dans la documentation ASTREE.
   Ne complete jamais cette absence d'information par une supposition, une
   reponse generale ou une information provenant d'un autre produit.
7. Ne jamais inventer une procedure.
8. Ne jamais inventer un numero de telephone.
9. Reponds en francais.
10. Reponse courte (maximum 5 phrases).
11. N'ecris jamais "Source :", "URL :" ou "Extrait :" - le systeme les affiche automatiquement.
12. Si la question ne concerne pas ASTREE ou les assurances, reponds exactement :
    Cette question ne concerne pas les services ou produits ASTREE.
    Je peux uniquement repondre aux questions liees aux assurances ASTREE.
13. Si une partie seulement de la reponse est presente dans le contexte, reponds
    uniquement avec cette partie sans completer avec des suppositions.
14. Si plusieurs documents se contredisent, privilegie celui dont la distance est
    la plus faible.
15. Si tu utilises la phrase de refus (regle 6) ou la phrase hors-sujet (regle 12),
    n'ajoute STRICTEMENT RIEN d'autre apres.
16. Si l'utilisateur dit simplement bonjour, bonsoir, salut ou hello, reponds avec
    un message de bienvenue court et naturel :
    Bonjour, je suis l'assistant ASTREE Assurances. Posez-moi une question sur vos
    assurances (habitation, auto, voyage...) et je m'appuie sur la documentation
    officielle pour vous répondre.
"""

# ============================================================
# LAZY LOADING - modeles charges a la premiere requete uniquement
# ============================================================
_embedding_model = None
_chroma_collection = None
_groq_client = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        print("Chargement du modele d'embedding (fastembed)...")
        from fastembed import TextEmbedding
        _embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
        print("Modele d'embedding charge.")
    return _embedding_model


def get_collection():
    global _chroma_collection
    if _chroma_collection is None:
        print("Connexion a ChromaDB...")
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _chroma_collection = client.get_collection(name=COLLECTION_NAME)
        print(f"Collection chargee : {_chroma_collection.count()} chunks.")
    return _chroma_collection


def get_groq_client():
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


# ============================================================
# Logs
# ============================================================
def charger_logs():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, OSError):
        return []
    return []


def sauvegarder_logs():
    dossier = os.path.dirname(LOG_FILE) or "."
    os.makedirs(dossier, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as fh:
        json.dump(conversation_logs, fh, ensure_ascii=False, indent=2)


conversation_logs = charger_logs()

print("Service pret (modeles charges a la premiere requete).")


# ============================================================
# Fonctions RAG
# ============================================================
def _normaliser(txt):
    txt = txt.lower()
    return "".join(c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn")


def _normaliser_accents(txt):
    return _normaliser(txt)


def _radical(mot):
    return mot[:-1] if mot.endswith(("s", "x")) and len(mot) > 4 else mot


def extraire_mots_cles(question):
    mots = re.findall(r"[a-zA-Z]+", _normaliser(question))
    mots_cles = set()
    for mot in mots:
        if mot in STOPWORDS_FR or len(mot) <= 3:
            continue
        mots_cles.add(mot)
        mots_cles.update(SYNONYMES_METIER.get(mot, set()))
    return [m for m in mots_cles if m not in STOPWORDS_FR and len(m) > 3]


def est_generique(url):
    return url in URLS_GENERIQUES


def retrieve_chunks_lexical(question, col):
    mots_cles = extraire_mots_cles(question)
    if not mots_cles:
        return []

    question_norm = _normaliser(question)
    demande_auto = any(
        terme in question_norm
        for terme in ("auto", "automobile", "vehicule", "voiture")
    )
    donnees = col.get(include=["documents", "metadatas"])
    candidates = []
    for doc, meta in zip(donnees["documents"], donnees["metadatas"]):
        titre = meta.get("page_titre", "")
        url = meta.get("url", "")
        texte = _normaliser(f"{titre} {url} {doc}")
        if demande_auto and "automobile" not in texte and "auto" not in texte:
            continue
        nb_matches = sum(1 for mot in mots_cles if _radical(mot) in texte)
        if nb_matches < (1 if demande_auto else 2):
            continue
        candidates.append({
            "document": doc,
            "url": url,
            "page_titre": titre,
            "distance": 0.59,
            "score": -nb_matches,
        })

    candidates.sort(key=lambda x: x["score"])
    return candidates[:TOP_K_FINAL]


def retrieve_chunks(question):
    model = get_embedding_model()
    col = get_collection()

    question_norm = _normaliser(question)
    demande_auto = any(
        terme in question_norm
        for terme in ("auto", "automobile", "vehicule", "voiture")
    )
    if demande_auto:
        lexical_chunks = retrieve_chunks_lexical(question, col)
        if lexical_chunks:
            return lexical_chunks

    query_text = question
    if "e5" in EMBEDDING_MODEL_NAME.lower():
        query_text = "query: " + question
    query_embedding = list(model.embed([query_text]))[0].tolist()

    results = col.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K_RETRIEVAL
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    mots_cles = extraire_mots_cles(question)

    candidates = []
    for doc, meta, dist in zip(docs, metas, distances):
        if dist > MAX_DISTANCE:
            continue
        url = meta.get("url", "")
        titre = meta.get("page_titre", "")
        texte_ref = _normaliser(url + " " + titre)
        nb_matches = sum(1 for m in mots_cles if _radical(m) in texte_ref)
        boost = nb_matches * BOOST_PAR_MOT_CLE
        candidates.append({
            "document": doc,
            "url": url,
            "page_titre": titre,
            "distance": float(dist),
            "score": float(dist) - boost,
        })

    if not candidates:
        return retrieve_chunks_lexical(question, col)

    candidates.sort(key=lambda x: x["score"])

    specifiques = [c for c in candidates if not est_generique(c["url"])]
    generiques = [c for c in candidates if est_generique(c["url"])]

    if specifiques:
        produit_principal = specifiques[0]["url"]
        specifiques = [c for c in specifiques if c["url"] == produit_principal]

    n_generiques = min(2, len(generiques))
    n_specifiques = TOP_K_FINAL - n_generiques
    resultat = specifiques[:n_specifiques] + generiques[:n_generiques]
    if len(resultat) < TOP_K_FINAL:
        reste = specifiques[n_specifiques:]
        resultat += reste[: TOP_K_FINAL - len(resultat)]

    return resultat


def construire_sources(chunks):
    deja_vu = set()
    sources = []
    for chunk in chunks:
        url = chunk["url"]
        if url in deja_vu:
            continue
        deja_vu.add(url)
        sources.append({
            "url": url,
            "page_titre": chunk["page_titre"],
            "distance": chunk["distance"],
        })
    return sources


def build_context(chunks):
    if not chunks:
        return None
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(
            "========================\n"
            f"DOCUMENT {i}\n\n"
            f"Titre :\n{c['page_titre']}\n\n"
            f"Contenu :\n{c['document']}\n\n"
            f"Source :\n{c['url']}\n"
            "========================"
        )
    return "\n".join(parts)


def construire_ligne_sources(chunks):
    if not chunks:
        return ""
    deja_vu = set()
    sources = []
    for chunk in chunks:
        cle = (chunk["page_titre"], chunk["url"])
        if cle not in deja_vu:
            deja_vu.add(cle)
            sources.append(f"{chunk['page_titre']} - {chunk['url']}")
    return "\n\n(Source : " + " ; ".join(sources) + ")"


def nettoyer_reponse(reponse):
    texte = re.sub(r"\[\s*\]", "", reponse)
    texte = re.sub(r"\b(D['\u2019]apr[e\u00e8]s|Selon)\s*,\s*", "", texte, flags=re.IGNORECASE)
    texte = re.sub(r"\(?\s*Source\s*:.*?\)?(?=\n|$)", "", texte, flags=re.IGNORECASE)
    texte = re.sub(r"\bDOCUMENT\s*\d+\b", "", texte, flags=re.IGNORECASE)
    texte = re.sub(r"\s{2,}", " ", texte)
    texte = re.sub(r"\s+([.,;:!?])", r"\1", texte)
    texte = texte.strip()

    texte_norm = _normaliser_accents(texte)
    if _normaliser_accents(REFUS_EXACT) in texte_norm:
        return REFUS_EXACT
    if _normaliser_accents(HORS_SUJET_EXACT.split("\n")[0]) in texte_norm:
        return HORS_SUJET_EXACT

    return texte


def est_requete_contact_sans_preuve(question, context):
    if not context:
        return False
    texte = _normaliser_accents(context)
    q = _normaliser(question)
    mots_contact = ("telephone", "téléphone", "contact", "numero", "numéro", "assistant")
    if not any(mot in q for mot in mots_contact):
        return False
    if re.search(r"\b\d{2}(?:[ .-]?\d{2}){3}\b", texte):
        return False
    if re.search(r"\b(?:tel|telephone|téléphone|contact|numero|numéro)\b", texte):
        return False
    return True


def generate_answer(question, context, chunks, history=None):
    if est_requete_contact_sans_preuve(question, context):
        return REFUS_EXACT

    try:
        client = get_groq_client()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            for h in history[-5:]:
                messages.append({"role": "user", "content": h["question"]})
                messages.append({"role": "assistant", "content": h["reponse"]})

        prompt = f"""DOCUMENTS

{context}

QUESTION
{question}

Reponds en te basant uniquement sur les documents ci-dessus. Ne mentionne
jamais les mots "DOCUMENT", leur numero, ni le mot "Source" dans ta reponse :
ecris uniquement la reponse en langage naturel, sans aucune reference ni
etiquette. Si aucun document ne repond a la question, reponds exactement :
Je n'ai pas trouve cette information dans la documentation ASTREE.
"""
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )

        answer = nettoyer_reponse(response.choices[0].message.content)

        if _normaliser_accents("Je n'ai pas trouve cette information") not in _normaliser_accents(answer):
            answer += construire_ligne_sources(chunks)

        return answer
    except Exception as e:
        print(f"❌ Erreur GROQ: {e}")
        raise Exception(f"Erreur lors de la generation de reponse: {str(e)}")


def ask(question, history=None):
    question_nettoyee = question.strip()
    if not question_nettoyee:
        return REFUS_EXACT, []

    if re.fullmatch(r"(?:bonjour|salut|bonsoir|hello|hi)\s*!?", _normaliser(question_nettoyee)):
        return GREETING_MESSAGE, []

    chunks = retrieve_chunks(question_nettoyee)
    context = build_context(chunks)

    if context is None:
        return REFUS_EXACT, []

    if est_requete_contact_sans_preuve(question_nettoyee, context):
        return REFUS_EXACT, []

    answer = generate_answer(question_nettoyee, context, chunks, history)
    return answer, chunks


def normaliser_question_stat(question):
    texte = _normaliser(question)
    texte = re.sub(r"[^a-z0-9]+", " ", texte).strip()
    return texte


def enregistrer_interaction(question, answer, chunks, sources=None):
    question_nettoyee = (question or "").strip()
    if not question_nettoyee:
        return

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question_nettoyee,
        "answer": answer,
        "sources": sources or construire_sources(chunks),
        "nb_chunks": len(chunks),
    }
    conversation_logs.append(entry)
    if len(conversation_logs) > MAX_LOG_ENTRIES:
        conversation_logs[:] = conversation_logs[-MAX_LOG_ENTRIES:]
    sauvegarder_logs()


def construire_synthese_admin(limit=10, top_n=10):
    recent = []
    for entry in conversation_logs[-limit:]:
        recent.append({
            "timestamp": entry["timestamp"],
            "question": entry["question"],
            "answer": entry["answer"],
            "sources": entry.get("sources", []),
        })

    freqs = Counter()
    questions_par_defaut = {}
    for entry in conversation_logs:
        norme = normaliser_question_stat(entry["question"])
        if not norme:
            continue
        freqs[norme] += 1
        questions_par_defaut.setdefault(norme, entry["question"])

    top_questions = []
    for norme, count in freqs.most_common(top_n):
        top_questions.append({
            "question": questions_par_defaut[norme],
            "count": count,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_interactions": len(conversation_logs),
        "top_questions": top_questions,
        "recent_conversations": recent,
    }


def escape_html(value):
    return (str(value)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


# ============================================================
# API FastAPI
# ============================================================
app = FastAPI(title="ASTREE RAG Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Startup events
# ============================================================
@app.on_event("startup")
def startup_event():
    """Initialiser les modeles au demarrage au lieu de la premiere requete"""
    try:
        print("Demarrage : Chargement du modele d'embedding...")
        get_embedding_model()
        print("✓ Modele d'embedding charge")

        print("Demarrage : Connexion a ChromaDB...")
        get_collection()
        print("✓ ChromaDB connecte")

        print("Demarrage : Initialisation du client GROQ...")
        get_groq_client()
        print("✓ Client GROQ initialise")

        print("✓ Service pret !")
    except Exception as e:
        print(f"❌ Erreur au demarrage: {e}")
        raise


# ============================================================
# Pydantic Models
# ============================================================
class HistoryItem(BaseModel):
    question: str
    reponse: str


class AskRequest(BaseModel):
    question: str
    history: list[HistoryItem] | None = None


class SourceItem(BaseModel):
    url: str
    page_titre: str
    distance: float


class AskResponse(BaseModel):
    reponse: str
    sources: list[SourceItem]
    nb_chunks: int
    duree_ms: int


# ------------------------------------------------------------
# /health : supporte GET et HEAD.
# UptimeRobot (plan gratuit) envoie des requetes HEAD par defaut,
# et le champ HTTP method est verrouille sur ce plan. On utilise
# donc @app.api_route pour accepter les deux methodes plutot que
# @app.get, qui ne repond pas explicitement a HEAD.
# ------------------------------------------------------------
@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok", "service": "astree-rag-v2"}


@app.get("/admin/synthese", response_class=HTMLResponse)
def admin_synthese(limit: int = 10, top_n: int = 10):
    data = construire_synthese_admin(limit=limit, top_n=top_n)
    recent = data.get("recent_conversations", [])
    top_questions = data.get("top_questions", [])

    rows_recent = "".join(
        f"""
        <tr>
          <td>{escape_html(item.get('timestamp',''))}</td>
          <td>{escape_html(item.get('question',''))}</td>
          <td>{escape_html(item.get('answer',''))}</td>
          <td>{escape_html(' ; '.join([s.get('page_titre', s.get('url', '')) for s in item.get('sources', [])]))}</td>
        </tr>
        """
        for item in recent
    )

    rows_top = "".join(
        f"""
        <tr>
          <td>{escape_html(item['question'])}</td>
          <td>{item['count']}</td>
        </tr>
        """
        for item in top_questions
    )

    return f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Rapport de synthÃ¨se ASTREE</title>
        <style>
          :root {{ color-scheme: light; }}
          body {{ font-family: Inter, system-ui, sans-serif; margin: 0; background: #eff4fb; color: #1a2930; }}
          .container {{ max-width: 1180px; margin: 0 auto; padding: 28px 24px 48px; }}
          .header {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 18px; margin-bottom: 24px; }}
          .hero {{ flex: 1 1 320px; }}
          .hero h1 {{ margin: 0 0 10px; font-size: 2.2rem; letter-spacing: -0.03em; color: #102a43; }}
          .hero p {{ margin: 0; color: #52606d; line-height: 1.6; }}
          .stats {{ display: flex; flex-wrap: wrap; gap: 12px; }}
          .stat-card {{ background: white; border-radius: 18px; padding: 18px 20px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08); min-width: 170px; flex: 1; }}
          .stat-card strong {{ display: block; font-size: 1.75rem; color: #102a43; }}
          .stat-card span {{ color: #627d98; }}
          .card {{ background: white; border-radius: 20px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08); padding: 24px; margin-bottom: 22px; }}
          h2 {{ margin: 0 0 14px; color: #102a43; font-size: 1.35rem; }}
          .section-note {{ color: #52606d; margin-bottom: 18px; }}
          table {{ width: 100%; border-collapse: collapse; font-size: 0.95rem; }}
          th, td {{ padding: 14px 12px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
          th {{ text-align: left; background: #f8fbff; color: #1f4e79; font-weight: 700; }}
          tbody tr:hover {{ background: #f7fbff; }}
          .empty {{ color: #7b8a99; font-style: italic; }}
          @media (max-width: 860px) {{ .header {{ flex-direction: column; align-items: stretch; }} table {{ font-size: 0.92rem; }} }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <div class="hero">
              <h1>Rapport de synthÃ¨se ASTREE</h1>
              <p>Vue administrative des interactions utilisateur.</p>
            </div>
            <div class="stats">
              <div class="stat-card"><strong>{data.get('total_interactions', 0)}</strong><span>Interactions enregistrÃ©es</span></div>
              <div class="stat-card"><strong>{len(top_questions)}</strong><span>Questions frÃ©quentes</span></div>
              <div class="stat-card"><strong>{len(recent)}</strong><span>Conversations rÃ©centes</span></div>
            </div>
          </div>
          <div class="card">
            <h2>Questions les plus frÃ©quentes</h2>
            <table>
              <thead><tr><th>Question</th><th>Nb</th></tr></thead>
              <tbody>{rows_top if rows_top else '<tr><td colspan="2" class="empty">Aucune question.</td></tr>'}</tbody>
            </table>
          </div>
          <div class="card">
            <h2>Conversations rÃ©centes</h2>
            <table>
              <thead><tr><th>Horodatage</th><th>Question</th><th>RÃ©ponse</th><th>Sources</th></tr></thead>
              <tbody>{rows_recent if rows_recent else '<tr><td colspan="4" class="empty">Aucune conversation.</td></tr>'}</tbody>
            </table>
          </div>
        </div>
      </body>
    </html>
    """


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(payload: AskRequest):
    if not payload.question or not payload.question.strip():
        raise HTTPException(status_code=400, detail="La question ne peut pas etre vide.")

    debut = time.time()
    try:
        history = [h.dict() for h in payload.history] if payload.history else None
        reponse, chunks = ask(payload.question, history)
    except Exception as e:
        print(f"❌ ERREUR dans ask(): {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du service RAG: {str(e)}"
        )

    duree_ms = int((time.time() - debut) * 1000)

    reponse_norm = _normaliser_accents(reponse)
    est_refus = (
        _normaliser_accents(REFUS_EXACT) == reponse_norm
        or _normaliser_accents(HORS_SUJET_EXACT.split("\n")[0]) in reponse_norm
    )
    sources = [] if est_refus else construire_sources(chunks)
    enregistrer_interaction(payload.question, reponse, chunks, sources=sources)

    return {
        "reponse": reponse,
        "sources": sources,
        "nb_chunks": len(chunks),
        "duree_ms": duree_ms,
    }