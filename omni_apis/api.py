import time
import uuid
import json
import secrets
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import CONFIG
from .models import MODELS, resolve_model
from .gemini import generate, generate_stream, log
from .tools import messages_to_prompt, parse_tool_calls, google_contents_to_prompt, parse_google_function_calls
from .multimodal import detect_image_mime, fetch_image_bytes, upload_image
from . import __version__

app = FastAPI(title="omni-proxy", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def verify_api_key(request: Request):
    keys = CONFIG.get("api_keys") or []
    if not keys:
        return
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        if any(secrets.compare_digest(token, key) for key in keys):
            return
    for h in ("x-api-key", "x-goog-api-key"):
        token = request.headers.get(h, "")
        if token and any(secrets.compare_digest(token, key) for key in keys):
            return
    key_param = request.query_params.get("key")
    if key_param and any(secrets.compare_digest(key_param, key) for key in keys):
        return
    raise HTTPException(status_code=401, detail="Invalid API key")

async def _upload_images(images: list) -> list:
    if not images:
        return None
    file_refs = []
    for item in images:
        if not (isinstance(item, tuple) and len(item) == 2):
            continue
        data, mime = item
        if isinstance(data, str):
            data = await fetch_image_bytes(data)
            mime = mime or "image/png"
        if not data:
            raise RuntimeError("image fetch failed")
        mime = detect_image_mime(data, mime or "image/png")
        try:
            ref = await upload_image(data, "image.png", mime or "image/png")
            file_refs.append(ref)
        except Exception as e:
            raise RuntimeError(f"image upload failed: {e}") from e
    return file_refs if file_refs else None

@app.get("/")
async def root():
    models_list = []
    for p_models in MODELS.values():
        models_list.extend(p_models.keys())
    return {"status": "ok", "version": __version__, "models": models_list}

@app.get("/v1/models")
async def list_models(dependencies=Depends(verify_api_key)):
    models_list = []
    for provider, provider_models in MODELS.items():
        for n, c in provider_models.items():
            models_list.append({"id": n, "object": "model", "created": 1700000000, "owned_by": provider, "description": c["desc"]})
    return {"object": "list", "data": models_list}

@app.get("/v1beta/models")
async def list_models_beta(dependencies=Depends(verify_api_key)):
    models_list = []
    for _, provider_models in MODELS.items():
        for n, c in provider_models.items():
            models_list.append({"name": f"models/{n}", "displayName": n, "description": c["desc"], "supportedGenerationMethods": ["generateContent", "streamGenerateContent"]})
    return {"models": models_list}

@app.post("/v1/chat/completions")
async def chat_completions(request: Request, dependencies=Depends(verify_api_key)):
    req = await request.json()
    model_name, model_id, think_mode, err, extra_fields, provider = resolve_model(req.get("model", CONFIG["default_model"]))
    if err:
        raise HTTPException(status_code=400, detail=err)

    tools = req.get("tools")
    tool_choice = req.get("tool_choice", "auto")
    stream = req.get("stream", False)
    if provider == "openai":
        from .chatgpt import handle_chatgpt_web_request
        try:
            return await handle_chatgpt_web_request(
                model_name=model_name,
                messages=req.get("messages", []),
                stream=stream
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"ChatGPT upstream error: {e}")
    prompt, images = messages_to_prompt(req.get("messages", []), tools, tool_choice)
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="empty prompt")

    cid = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    
    try:
        file_refs = await _upload_images(images)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"upstream error: {e}")

    if stream and (not tools or tool_choice == "none"):
        async def event_generator():
            first_chunk = {
                "id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                "model": model_name, "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]
            }
            yield f"data: {json.dumps(first_chunk)}\n\n"
            async for delta in generate_stream(prompt, model_id, think_mode, file_refs, extra_fields):
                chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                         "model": model_name, "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}]}
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            end = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                   "model": model_name, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            yield f"data: {json.dumps(end)}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    try:
        text = await generate(prompt, model_id, think_mode, file_refs, extra_fields)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"upstream error: {e}")

    tool_calls = None
    if tools and text and tool_choice != "none":
        text, tool_calls = parse_tool_calls(text)
    msg = {"role": "assistant", "content": text or None}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    finish = "tool_calls" if tool_calls else "stop"

    if stream:
        async def stream_tool_response():
            chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                     "model": model_name, "choices": [{"index": 0, "delta": msg, "finish_reason": finish}]}
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(stream_tool_response(), media_type="text/event-stream")

    return {
        "id": cid, "object": "chat.completion", "created": int(time.time()),
        "model": model_name,
        "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
        "usage": {"prompt_tokens": len(prompt)//4, "completion_tokens": len(text or "")//4,
                  "total_tokens": (len(prompt)+len(text or ""))//4},
    }

@app.post("/v1/images/generations")
async def handle_generate_images(request: Request, dependencies=Depends(verify_api_key)):
    req = await request.json()
    prompt = req.get("prompt")
    model = req.get("model", "")
    
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required for Image Generation")
        
    try:
        from .models import resolve_model
        _, _, _, err, _, provider = resolve_model(model or CONFIG["default_model"])
        
        if provider == "openai":
            from .chatgpt import generate_images
        else:
            from .gemini import generate_images
            
        image_urls = await generate_images(prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Image generation failed: {e}")
        
    data = []
    for url in image_urls:
        data.append({
            "url": url,
            "revised_prompt": prompt
        })
    
    return {
        "created": int(time.time()),
        "data": data
    }
