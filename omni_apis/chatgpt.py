import json
import uuid
import httpx
import os
import asyncio
import re
from fastapi.responses import StreamingResponse

from .config import CONFIG

_chatgpt_cache = {"session_token": None, "pow_token": None, "mtime": 0}

def load_chatgpt_auth():
    cookie_file = CONFIG.get("cookie_file")
    if not cookie_file or not os.path.exists(cookie_file):
        return CONFIG.get("openai_session_token", "MOCK_SESSION_TOKEN"), CONFIG.get("openai_pow_token", "MOCK_POW_TOKEN")
    try:
        mtime = os.path.getmtime(cookie_file)
        if mtime == _chatgpt_cache["mtime"] and _chatgpt_cache["session_token"] is not None:
            return _chatgpt_cache["session_token"], _chatgpt_cache["pow_token"]
            
        with open(cookie_file, "r") as f:
            content = f.read().strip()
            
        if content.startswith("{"):
            data = json.loads(content)
            session_token = data.get("openai_session_token") or CONFIG.get("openai_session_token", "MOCK_SESSION_TOKEN")
            pow_token = data.get("openai_pow_token") or CONFIG.get("openai_pow_token", "MOCK_POW_TOKEN")
        else:
            session_token = CONFIG.get("openai_session_token", "MOCK_SESSION_TOKEN")
            pow_token = CONFIG.get("openai_pow_token", "MOCK_POW_TOKEN")
            
        _chatgpt_cache.update({"session_token": session_token, "pow_token": pow_token, "mtime": mtime})
        return session_token, pow_token
    except Exception as e:
        print(f"ChatGPT auth load error: {e}")
        return _chatgpt_cache.get("session_token") or "MOCK_SESSION_TOKEN", _chatgpt_cache.get("pow_token") or "MOCK_POW_TOKEN"


async def handle_chatgpt_web_request(model_name: str, messages: list, stream: bool):
    session_token, pow_token = load_chatgpt_auth()
    device_id = str(uuid.uuid4())

    headers = {
        "Authorization": f"Bearer {session_token}",
        "Content-Type": "application/json",
        "OAI-Device-Id": device_id,
        "OpenAI-Sentinel-Proof-Token": pow_token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            "id": str(uuid.uuid4()),
            "author": {"role": msg["role"]},
            "content": {"content_type": "text", "parts": [msg.get("content", "")]}
        })

    payload = {
        "action": "next",
        "messages": formatted_messages,
        "model": model_name,
        "parent_message_id": str(uuid.uuid4()),
        "timezone_offset_min": -330
    }

    url = "https://chatgpt.com/backend-api/conversation"
    proxy = CONFIG.get("proxy")
    
    async def fetch_stream():
        last_err = None
        for attempt in range(CONFIG.get("retry_attempts", 3)):
            try:
                async with httpx.AsyncClient(proxy=proxy) as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        if response.status_code != 200:
                            yield f"data: {json.dumps({'error': f'Failed to bypass ChatGPT: HTTP {response.status_code}. PoW token might be expired.'})}\n\n"
                            yield "data: [DONE]\n\n"
                            return

                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    yield "data: [DONE]\n\n"
                                    break
                                try:
                                    data = json.loads(data_str)
                                    if "message" in data and "content" in data["message"]:
                                        parts = data["message"]["content"].get("parts", [])
                                        if parts:
                                            chunk = {
                                                "choices": [{"delta": {"content": parts[0]}}]
                                            }
                                            yield f"data: {json.dumps(chunk)}\n\n"
                                except json.JSONDecodeError:
                                    pass
                return
            except Exception as e:
                last_err = e
                if attempt < CONFIG.get("retry_attempts", 3) - 1:
                    print(f"ChatGPT Stream retry {attempt+1}/{CONFIG.get('retry_attempts', 3)}: {e}")
                    await asyncio.sleep(CONFIG.get("retry_delay_sec", 2))
        
        yield f"data: {json.dumps({'error': f'ChatGPT upstream error after retries: {last_err}'})}\n\n"
        yield "data: [DONE]\n\n"

    if stream:
        return StreamingResponse(fetch_stream(), media_type="text/event-stream")
    else:
        final_text = ""
        async for chunk_str in fetch_stream():
            if chunk_str.startswith("data: ") and not chunk_str.startswith("data: [DONE]"):
                try:
                    data = json.loads(chunk_str[6:])
                    if "choices" in data and len(data["choices"]) > 0:
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            final_text = delta["content"]
                except json.JSONDecodeError:
                    pass
                    
        return {
            "choices": [{"message": {"content": final_text}}]
        }


async def generate_images(prompt: str) -> list:
    full_prompt = f"Generate an image of the following. ONLY return the markdown image URL or raw URL, no text: {prompt}"
    response = await handle_chatgpt_web_request("gpt-4o", [{"role": "user", "content": full_prompt}], stream=False)
    
    try:
        if isinstance(response, StreamingResponse):
            return []
            
        raw_response = response["choices"][0]["message"]["content"]
        urls = re.findall(r'(https?://[^\s)"]+)', raw_response)
        
        return list(set(urls))
    except Exception as e:
        print(f"ChatGPT Image Generation parsing error: {e}")
        return []
