import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path, override=True)
load_dotenv(override=True)

# LLM Providers Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Models
GROQ_TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "openai/gpt-oss-120b")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "openai/gpt-oss-20b")

# Local Fallback (Ollama)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:latest")

# Core AI Parameter Configurations
TEMPERATURE_TRIAGE = 0.0      # Deterministic intent routing & safety
TEMPERATURE_SUPPORT = 0.0     # Strict policy adherence & zero improvisation
TEMPERATURE_SHOPPER = 0.4     # Natural, engaging conversational recommendations
MAX_OUTPUT_TOKENS = 1024
TOP_P = 0.9

# Business Policy Guardrails (Cannot be overridden by LLM)
MAX_AUTO_REFUND_AMOUNT = 50.00  # Any refund over $50 triggers Human Handoff
RETURN_POLICY_DAYS = 30         # Return window cutoff in days
