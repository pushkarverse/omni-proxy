import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from omni_apis.api import app
from omni_apis.config import CONFIG

class APITests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.original_config = dict(CONFIG)
        CONFIG["api_keys"] = []
        CONFIG["log_requests"] = False

    def tearDown(self):
        CONFIG.clear()
        CONFIG.update(self.original_config)

    def test_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_models_endpoint(self):
        response = self.client.get("/v1/models")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)
        models = [m["id"] for m in data["data"]]
        self.assertIn("gemini-3.6-flash", models)
        self.assertNotIn("gpt-4o", models)

    @patch("omni_apis.api.generate", new_callable=AsyncMock)
    def test_chat_completions_gemini(self, mock_generate):
        mock_generate.return_value = "Hello from Gemini"

        response = self.client.post("/v1/chat/completions", json={
            "model": "gemini-3.6-flash",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["choices"][0]["message"]["content"], "Hello from Gemini")
        mock_generate.assert_called_once()

    def test_images_endpoint_removed(self):
        response = self.client.post("/v1/images/generations", json={
            "prompt": "a cool image"
        })
        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
