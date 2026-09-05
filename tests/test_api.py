import json
import base64
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
        self.assertIn("Omni-Proxy is running", response.text)

    def test_models_endpoint(self):
        response = self.client.get("/v1/models")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)
        models = [m["id"] for m in data["data"]]
        self.assertIn("gemini-1.5-pro", models)
        self.assertIn("gpt-4o", models)

    @patch("omni_apis.gemini.generate", new_callable=AsyncMock)
    def test_chat_completions_gemini(self, mock_generate):
        mock_generate.return_value = "Hello from Gemini"
        
        response = self.client.post("/v1/chat/completions", json={
            "model": "gemini-1.5-pro",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["choices"][0]["message"]["content"], "Hello from Gemini")
        mock_generate.assert_called_once()

    @patch("omni_apis.chatgpt.handle_chatgpt_web_request", new_callable=AsyncMock)
    def test_chat_completions_chatgpt(self, mock_handle):
        mock_handle.return_value = {
            "choices": [{"message": {"content": "Hello from ChatGPT"}}]
        }
        
        response = self.client.post("/v1/chat/completions", json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["choices"][0]["message"]["content"], "Hello from ChatGPT")
        mock_handle.assert_called_once()

    @patch("omni_apis.gemini.generate_images", new_callable=AsyncMock)
    def test_image_generations_gemini(self, mock_generate_images):
        mock_generate_images.return_value = ["http://gemini.image"]
        
        response = self.client.post("/v1/images/generations", json={
            "model": "gemini-1.5-pro",
            "prompt": "a cool image"
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["data"][0]["url"], "http://gemini.image")
        mock_generate_images.assert_called_once()

    @patch("omni_apis.chatgpt.generate_images", new_callable=AsyncMock)
    def test_image_generations_chatgpt(self, mock_generate_images):
        mock_generate_images.return_value = ["http://chatgpt.image"]
        
        response = self.client.post("/v1/images/generations", json={
            "model": "dall-e-3",
            "prompt": "a cool image"
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["data"][0]["url"], "http://chatgpt.image")
        mock_generate_images.assert_called_once()

if __name__ == "__main__":
    unittest.main()
