MODELS = {
    "google": {
        "gemini-3.7-flash": {
            "mode": 1, "think": 4,
            "desc": "Latest all-around model (Gemini 3.7 Flash)",
        },
        "gemini-3.6-flash": {
            "mode": 1, "think": 4,
            "desc": "All-around model (Gemini 3.6 Flash)",
        },
        "gemini-3.5-flash": {
            "mode": 1, "think": 4,
            "desc": "Alias for gemini-3.6-flash (backend upgraded)",
        },
        "gemini-3.5-flash-thinking": {
            "mode": 2, "think": 0,
            "desc": "Deep thinking mode, longest output (~20k chars)",
        },
        "gemini-3.1-pro": {
            "mode": 3, "think": 4,
            "desc": "Pro model (requires cookie for real routing)",
        },
        "gemini-3.1-pro-enhanced": {
            "mode": 3, "think": 4, "extra": {31: 2, 80: 3},
            "desc": "Pro with enhanced output (experimental)",
        },
        "gemini-auto": {
            "mode": 4, "think": 4,
            "desc": "Auto model selection",
        },
        "gemini-3.5-flash-thinking-lite": {
            "mode": 5, "think": 0,
            "desc": "Dynamic thinking with adaptive depth",
        },
        "gemini-flash-lite": {
            "mode": 6, "think": 4,
            "desc": "Lightweight fast model",
        }
    },
    "openai": {
        "gpt-3.5-turbo": {
            "mode": 0, "think": 0,
            "desc": "Standard ChatGPT model",
        },
        "gpt-4o": {
            "mode": 0, "think": 0,
            "desc": "Advanced ChatGPT model",
        },
        "gpt-4o-mini": {
            "mode": 0, "think": 0,
            "desc": "Fast ChatGPT model",
        }
    }
}


def resolve_model(model_name: str, default_provider: str = "google", default_model: str = "gemini-3.6-flash"):
    think_override = None
    if "@think=" in model_name:
        model_name, think_str = model_name.rsplit("@think=", 1)
        try:
            think_override = int(think_str)
        except ValueError:
            return None, None, None, f"Invalid think level: {think_str}", None, None
            
    cfg = None
    provider = default_provider
    for p, p_models in MODELS.items():
        if model_name in p_models:
            cfg = p_models[model_name]
            provider = p
            break
            
    if not cfg:
        from .gemini import log
        log(f"Unknown model '{model_name}', falling back to '{default_model}' on '{default_provider}'")
        model_name = default_model
        cfg = MODELS.get(default_provider, {}).get(default_model)
        
        if not cfg:
            cfg = MODELS["google"]["gemini-3.6-flash"]
            default_provider = "google"
            
        provider = default_provider
        
    mode_id = cfg["mode"]
    think_mode = think_override if think_override is not None else cfg["think"]
    extra = cfg.get("extra")
    return model_name, mode_id, think_mode, None, extra, provider
