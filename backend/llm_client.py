import time
import os
import json
from typing import List, Dict, Any, Optional
from groq import Groq
import httpx
from . import config

def get_groq_client() -> Optional[Groq]:
    api_key = config.GROQ_API_KEY.strip() or os.getenv("GROQ_API_KEY", "").strip()
    if api_key:
        return Groq(api_key=api_key)
    return None

def check_llm_status() -> Dict[str, Any]:
    """Checks whether Groq or local Ollama is active and ready."""
    client = get_groq_client()
    if client:
        return {
            "provider": "Groq",
            "model": config.GROQ_TEXT_MODEL,
            "vision_model": config.GROQ_VISION_MODEL,
            "status": "ready",
            "is_local": False
        }
    
    # Check if local Ollama is running
    try:
        res = httpx.get("http://localhost:11434/api/tags", timeout=1.5)
        if res.status_code == 200:
            return {
                "provider": "Ollama (Local Fallback)",
                "model": config.OLLAMA_MODEL,
                "vision_model": "None (Provide Groq API key for Vision)",
                "status": "ready",
                "is_local": True
            }
    except Exception:
        pass

    return {
        "provider": "None",
        "model": "None",
        "vision_model": "None",
        "status": "needs_key",
        "message": "Please enter your Groq API key in backend/.env or in the UI settings bar."
    }

def call_llm(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = config.MAX_OUTPUT_TOKENS,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: str = "auto"
) -> Dict[str, Any]:
    """
    Unified LLM call supporting Groq (primary) and Ollama (fallback).
    Measures and returns execution latency and token metrics.
    """
    client = get_groq_client()
    target_model = model or config.GROQ_TEXT_MODEL
    start_time = time.time()

    if client:
        kwargs: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": config.TOP_P,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        try:
            response = client.chat.completions.create(**kwargs)
            latency_ms = int((time.time() - start_time) * 1000)
            choice = response.choices[0]
            
            tool_calls = []
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments) if tc.function.arguments else {}
                    })

            usage = response.usage
            return {
                "content": choice.message.content or "",
                "tool_calls": tool_calls,
                "latency_ms": latency_ms,
                "tokens": {
                    "prompt": usage.prompt_tokens if usage else 0,
                    "completion": usage.completion_tokens if usage else 0,
                    "total": usage.total_tokens if usage else 0
                },
                "model": target_model,
                "provider": "Groq"
            }
        except Exception as e:
            return {
                "content": f"LLM Inference Error: {str(e)}",
                "tool_calls": [],
                "latency_ms": int((time.time() - start_time) * 1000),
                "tokens": {"total": 0},
                "error": str(e)
            }

    # Fallback to local Ollama via OpenAI-compatible endpoint
    try:
        payload: Dict[str, Any] = {
            "model": config.OLLAMA_MODEL,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        res = httpx.post("http://localhost:11434/v1/chat/completions", json=payload, timeout=60.0)
        data = res.json()
        latency_ms = int((time.time() - start_time) * 1000)
        content = data["choices"][0]["message"]["content"]
        return {
            "content": content,
            "tool_calls": [],
            "latency_ms": latency_ms,
            "tokens": {"total": data.get("usage", {}).get("total_tokens", 0)},
            "model": config.OLLAMA_MODEL,
            "provider": "Ollama"
        }
    except Exception as e:
        return {
            "content": "No LLM available. Please set GROQ_API_KEY in backend/.env or run Ollama locally.",
            "tool_calls": [],
            "latency_ms": int((time.time() - start_time) * 1000),
            "tokens": {"total": 0},
            "error": "Missing API key and Ollama offline"
        }

def analyze_image_with_vision(image_base64: str, prompt: str) -> Dict[str, Any]:
    """
    Multimodal Vision inference using Llama 3.2 Vision on Groq.
    """
    client = get_groq_client()
    if not client:
        return {
            "error": "Groq API key required for Multimodal Vision (Llama-3.2-11b-vision).",
            "description": "Please provide a Groq API key to enable visual product search & damage inspection."
        }
    
    start_time = time.time()
    try:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]
        response = client.chat.completions.create(
            model=config.GROQ_VISION_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=600
        )
        latency_ms = int((time.time() - start_time) * 1000)
        content = response.choices[0].message.content
        return {
            "description": content,
            "latency_ms": latency_ms,
            "model": config.GROQ_VISION_MODEL,
            "provider": "Groq Vision"
        }
    except Exception as e:
        return {
            "error": str(e),
            "description": f"Vision analysis failed: {str(e)}"
        }
