import importlib
import sys
import types
import unittest
from pathlib import Path


class DummySentenceTransformer:
    def __init__(self, *args, **kwargs):
        pass

    def encode(self, *args, **kwargs):
        return [0.0]


class DummyGroq:
    def __init__(self, *args, **kwargs):
        pass


class DummyCollection:
    def count(self):
        return 0


class DummyPersistentClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_collection(self, name):
        return DummyCollection()


class DummyFastAPI:
    def __init__(self, *args, **kwargs):
        self.routes = []

    def add_middleware(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    def post(self, *args, **kwargs):
        def decorator(fn):
            return fn
        return decorator


class DummyHTTPException(Exception):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class DummyBaseModel:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def dict(self):
        return self.__dict__


class DummyCORSMiddleware:
    def __init__(self, *args, **kwargs):
        pass


class AppImportTest(unittest.TestCase):
    def setUp(self):
        self.module_name = "rag_service_app"
        sys.modules.pop(self.module_name, None)

        fake_chromadb = types.ModuleType("chromadb")
        fake_chromadb.PersistentClient = DummyPersistentClient

        fake_dotenv = types.ModuleType("dotenv")
        fake_dotenv.load_dotenv = lambda: None

        fake_fastapi = types.ModuleType("fastapi")
        fake_fastapi.FastAPI = DummyFastAPI
        fake_fastapi.HTTPException = DummyHTTPException

        fake_fastapi_responses = types.ModuleType("fastapi.responses")
        fake_fastapi_responses.HTMLResponse = str

        fake_cors = types.ModuleType("fastapi.middleware.cors")
        fake_cors.CORSMiddleware = DummyCORSMiddleware

        fake_groq = types.ModuleType("groq")
        fake_groq.Groq = DummyGroq

        fake_pydantic = types.ModuleType("pydantic")
        fake_pydantic.BaseModel = DummyBaseModel

        fake_sentence = types.ModuleType("sentence_transformers")
        fake_sentence.SentenceTransformer = DummySentenceTransformer

        sys.modules["chromadb"] = fake_chromadb
        sys.modules["dotenv"] = fake_dotenv
        sys.modules["fastapi"] = fake_fastapi
        sys.modules["fastapi.middleware"] = types.ModuleType("fastapi.middleware")
        sys.modules["fastapi.middleware.cors"] = fake_cors
        sys.modules["fastapi.responses"] = fake_fastapi_responses
        sys.modules["groq"] = fake_groq
        sys.modules["pydantic"] = fake_pydantic
        sys.modules["sentence_transformers"] = fake_sentence

    def test_sources_are_deduplicated(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        spec = importlib.util.spec_from_file_location(self.module_name, app_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[self.module_name] = module
        spec.loader.exec_module(module)

        chunks = [
            {"url": "https://a", "page_titre": "Titre A", "distance": 0.1},
            {"url": "https://a", "page_titre": "Titre A", "distance": 0.2},
            {"url": "https://b", "page_titre": "Titre B", "distance": 0.3},
        ]

        sources = module.construire_sources(chunks)

        self.assertEqual(len(sources), 2)
        self.assertEqual([item["url"] for item in sources], ["https://a", "https://b"])

    def test_internal_labels_are_removed(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        spec = importlib.util.spec_from_file_location(self.module_name, app_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[self.module_name] = module
        spec.loader.exec_module(module)

        cleaned = module.nettoyer_reponse("Voici le DOCUMENT 4 et la source: https://x")

        self.assertNotIn("DOCUMENT", cleaned)
        self.assertNotIn("source", cleaned.lower())

    def test_greeting_returns_conversational_reply(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        spec = importlib.util.spec_from_file_location(self.module_name, app_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[self.module_name] = module
        spec.loader.exec_module(module)

        reply, chunks = module.ask("bonjour")

        self.assertEqual(chunks, [])
        self.assertIn("bonjour", reply.lower())
        self.assertNotIn("Je n'ai pas trouve cette information", reply)


if __name__ == "__main__":
    unittest.main()
