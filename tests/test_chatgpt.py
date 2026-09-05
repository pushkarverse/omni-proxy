import os
import json
import tempfile
import unittest
from unittest.mock import patch

from omni_apis.config import CONFIG
from omni_apis.chatgpt import load_chatgpt_auth, _chatgpt_cache


class ChatGPTAuthTests(unittest.TestCase):
    def setUp(self):
        self.original_config = dict(CONFIG)
        self.original_cache = dict(_chatgpt_cache)
        _chatgpt_cache.update({"session_token": None, "pow_token": None, "mtime": 0})
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w")
        self.temp_file_path = self.temp_file.name

    def tearDown(self):
        CONFIG.clear()
        CONFIG.update(self.original_config)
        _chatgpt_cache.update(self.original_cache)
        
        if os.path.exists(self.temp_file_path):
            os.remove(self.temp_file_path)

    def test_load_auth_fallback_to_config(self):
        CONFIG["cookie_file"] = "nonexistent_file.json"
        CONFIG["openai_session_token"] = "config_session"
        CONFIG["openai_pow_token"] = "config_pow"
        
        session_token, pow_token = load_chatgpt_auth()
        
        self.assertEqual(session_token, "config_session")
        self.assertEqual(pow_token, "config_pow")

    def test_load_auth_from_json_file(self):
        CONFIG["cookie_file"] = self.temp_file_path
        json.dump({
            "openai_session_token": "file_session_token",
            "openai_pow_token": "file_pow_token"
        }, self.temp_file)
        self.temp_file.flush()
        
        session_token, pow_token = load_chatgpt_auth()
        self.assertEqual(session_token, "file_session_token")
        self.assertEqual(pow_token, "file_pow_token")
        self.assertEqual(_chatgpt_cache["session_token"], "file_session_token")

    def test_load_auth_uses_cache(self):
        CONFIG["cookie_file"] = self.temp_file_path
        json.dump({
            "openai_session_token": "first_read_session",
            "openai_pow_token": "first_read_pow"
        }, self.temp_file)
        self.temp_file.flush()
        
        load_chatgpt_auth()
        self.assertEqual(_chatgpt_cache["session_token"], "first_read_session")
        with patch('os.path.getmtime', return_value=_chatgpt_cache["mtime"]):
            session_token, pow_token = load_chatgpt_auth()
            self.assertEqual(session_token, "first_read_session")

if __name__ == "__main__":
    unittest.main()
