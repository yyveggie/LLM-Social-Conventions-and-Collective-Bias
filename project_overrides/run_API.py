#%%
import json
import re
import requests
import time
import yaml
from datetime import datetime, timezone
from pathlib import Path
from munch import munchify
#%%
ROOT = Path(__file__).resolve().parents[1]
with open(ROOT / "config.yaml", "r") as f:
    doc = yaml.safe_load(f)
config = munchify(doc)
if "api" not in doc:
    raise ValueError("Missing api configuration in config.yaml.")
api_doc = doc["api"]
api_config = munchify(api_doc)
# set temperature to 0 for deterministic outcomes
temperature = config.params.temperature
request_config = getattr(api_config, "request", munchify({}))
provider_name = api_config.active_provider
provider = api_config.providers[provider_name]
provider_type = provider.type
model_name = provider.model
timeout_seconds = getattr(provider, "timeout_seconds", getattr(request_config, "timeout_seconds", 120))
retry_sleep_seconds = getattr(request_config, "retry_sleep_seconds", 2.5)
rate_limit_sleep_seconds = getattr(request_config, "rate_limit_sleep_seconds", 450)
max_retries = getattr(request_config, "max_retries", 100)
api_key = getattr(provider, "api_key", "")
if api_key in ["", "<YOUR_API_KEY>", "<YOUR_TOKEN_HERE>"]:
    raise ValueError(f"Missing API key for provider '{provider_name}'. Set api.providers.{provider_name}.api_key in config.yaml.")
base_url = getattr(provider, "base_url", "")
if base_url.endswith("/"):
    base_url = base_url[:-1]
log_config = getattr(config, "logging", munchify({}))
log_enabled = getattr(log_config, "enabled", False)
log_dir = ROOT / getattr(log_config, "dir", "logs")
save_prompts = getattr(log_config, "save_prompts", True)
save_raw_responses = getattr(log_config, "save_raw_responses", True)
log_file = log_dir / f"{provider_name}_api_calls.jsonl"
if temperature == 0:
    llm_params = {"do_sample": False,
            "max_new_tokens": 12,
            "return_full_text": False, 
            }
else:
    llm_params = {"do_sample": True,
            "temperature": temperature,
            "top_k": getattr(provider, "top_k", 10),
            "max_new_tokens": 15,
            "return_full_text": False, 
            }  
#%%
def _write_log(record):
    if not log_enabled:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    record["provider"] = provider_name
    record["model"] = model_name
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

def _headers():
    if provider_type == "anthropic":
        return {
            "x-api-key": api_key,
            "anthropic-version": getattr(provider, "anthropic_version", "2023-06-01"),
            "content-type": "application/json",
        }
    if provider_type == "gemini":
        return {"content-type": "application/json"}
    return {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}

def _payload(chat, max_tokens):
    if provider_type == "huggingface":
        params = llm_params.copy()
        params["max_new_tokens"] = max_tokens
        return {"inputs": chat, "parameters": params, "options": {"use_cache": False}}
    if provider_type == "anthropic":
        return {
            "model": model_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": chat}],
        }
    if provider_type == "gemini":
        return {
            "contents": [{"parts": [{"text": chat}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
    return {
        "model": model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": chat}],
    }

def _url():
    if provider_type == "huggingface":
        return f"{base_url}/{model_name}"
    if provider_type == "anthropic":
        return f"{base_url}/messages"
    if provider_type == "gemini":
        return f"{base_url}/models/{model_name}:generateContent?key={api_key}"
    return f"{base_url}/chat/completions"

def _extract_text(response):
    if response is None:
        return None
    if provider_type == "huggingface":
        if isinstance(response, list) and len(response) > 0:
            return response[0].get("generated_text")
        return None
    if provider_type == "anthropic":
        content = response.get("content", [])
        return "".join([block.get("text", "") for block in content])
    if provider_type == "gemini":
        candidates = response.get("candidates", [])
        if len(candidates) == 0:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join([part.get("text", "") for part in parts])
    choices = response.get("choices", [])
    if len(choices) == 0:
        return None
    return choices[0].get("message", {}).get("content", "")

def _is_rate_limited(response):
    if not isinstance(response, dict):
        return False
    status = response.get("status_code")
    text = str(response.get("error", response))
    return status == 429 or "rate limit" in text.lower() or "Inference Endpoints" in text

def query(chat, max_tokens=15):
    for _ in range(max_retries):
        try:
            url = _url()
            payload = _payload(chat, max_tokens)
            start_time = time.time()
            response = requests.post(url, headers=_headers(), json=payload, timeout=timeout_seconds)
            elapsed_seconds = time.time() - start_time
            try:
                body = response.json()
            except ValueError:
                print('CAUGHT JSON ERROR')
                log_record = {
                    "event": "api_response",
                    "ok": False,
                    "status_code": response.status_code,
                    "elapsed_seconds": elapsed_seconds,
                    "error": "JSON decode error",
                }
                if save_prompts:
                    log_record["prompt"] = chat
                if save_raw_responses:
                    log_record["raw_response"] = response.text
                _write_log(log_record)
                time.sleep(retry_sleep_seconds)
                continue
            log_record = {
                "event": "api_response",
                "ok": response.status_code < 400,
                "status_code": response.status_code,
                "elapsed_seconds": elapsed_seconds,
                "extracted_text": _extract_text(body),
            }
            if save_prompts:
                log_record["prompt"] = chat
            if save_raw_responses:
                log_record["raw_response"] = body
            _write_log(log_record)
            if response.status_code >= 400:
                if isinstance(body, dict):
                    body["status_code"] = response.status_code
                print("AN EXCEPTION: ", body)
                if _is_rate_limited(body):
                    print("RATE LIMIT REACHED")
                    time.sleep(rate_limit_sleep_seconds)
                else:
                    time.sleep(retry_sleep_seconds)
                continue
            return body
        except requests.RequestException as exc:
            print('CAUGHT REQUEST ERROR')
            log_record = {
                "event": "api_response",
                "ok": False,
                "error": str(exc),
            }
            if save_prompts:
                log_record["prompt"] = chat
            _write_log(log_record)
            time.sleep(retry_sleep_seconds)
    return None

def _extract_choice(text, options):
    response_split = text.split("'")
    for opt in options:
        try:
            index = response_split.index(opt)
            return response_split[index]
        except ValueError:
            continue
    for opt in options:
        pattern = r"value['\"]?\s*:\s*['\"]?" + re.escape(opt) + r"(?![A-Za-z0-9_])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return opt
    for opt in options:
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(opt) + r"(?![A-Za-z0-9_])"
        if re.search(pattern, text):
            return opt
    return None

def get_response(chat, options):
    """Generate a response from the model."""

    overloaded = 1
    while overloaded == 1:
        response = query(chat, max_tokens=15)
        text = _extract_text(response)
        if text is None:
            print('CAUGHT EMPTY RESPONSE')
            continue
        answer = _extract_choice(text, options)
        if answer is not None:
            _write_log({
                "event": "parsed_answer",
                "options": options,
                "extracted_text": text,
                "parsed_answer": answer,
            })
            overloaded=0
    print(answer)
    return answer

def get_meta_response(chat):
    """Generate a response from the Llama model."""

    overloaded = 1
    while overloaded == 1:
        response = query(chat, max_tokens=15)
        text = _extract_text(response)
        if text is None:
            print('CAUGHT EMPTY RESPONSE')
            continue
        if 'value' in text:
            overloaded=0
    
            response_split = text.split(";")
            response_split = response_split[0].split(": ")
            if len(response_split)<2:
                overloaded = 1
    _write_log({
        "event": "parsed_meta_answer",
        "extracted_text": text,
        "parsed_answer": response_split[1],
    })
    print(response_split[1])
    return response_split[1]
