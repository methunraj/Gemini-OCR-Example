import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Paths Configuration ---
INPUT_PATH = os.getenv("INPUT_PATH", "/Users/methunraj/Downloads/1916 2682_2686_Spisok_pogib_ranen_VV")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/Users/methunraj/Desktop/Image Processing/output_folder")
PROCESS_RECURSIVELY = os.getenv("PROCESS_RECURSIVELY", "True").lower() in ("true", "t", "1", "yes", "y")

# --- Checkpointing Configuration ---
ENABLE_CHECKPOINTING = os.getenv("ENABLE_CHECKPOINTING", "True").lower() in ("true", "t", "1", "yes", "y")
CHECKPOINT_FILE = os.getenv("CHECKPOINT_FILE", "processing_checkpoint.json")
RESUME_FROM_CHECKPOINT = os.getenv("RESUME_FROM_CHECKPOINT", "False").lower() in ("true", "t", "1", "yes", "y")

# --- Logging and Cost Calculation ---
LOG_LLM_THINKING = os.getenv("LOG_LLM_THINKING", "False").lower() in ("true", "t", "1", "yes", "y")
CALCULATE_COST = os.getenv("CALCULATE_COST", "True").lower() in ("true", "t", "1", "yes", "y")

# --- Thinking Budget Configuration ---
try:
    THINKING_BUDGET = int(os.getenv("THINKING_BUDGET", "8192"))
except ValueError:
    THINKING_BUDGET = 8192  # Default fallback if env variable is not a valid integer
SAVE_THINKING_OUTPUT = os.getenv("SAVE_THINKING_OUTPUT", "False").lower() in ("true", "t", "1", "yes", "y")

# --- Parallel Processing Configuration ---
ENABLE_PARALLEL = os.getenv("ENABLE_PARALLEL_PROCESSING", "False").lower() in ("true", "t", "1", "yes", "y")
try:
    MAX_WORKERS = int(os.getenv("MAX_WORKER_PROCESSES", "0"))
except ValueError:
    MAX_WORKERS = 0  # Auto-detection

# --- Currency Conversion ---
try:
    USD_TO_INR_RATE = float(os.getenv("USD_TO_INR_RATE", "83.5"))
except ValueError:
    USD_TO_INR_RATE = 83.5  # Default fallback if env variable is not a valid float

# --- LLM Configuration ---
DEFAULT_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash-preview-04-17")

# --- LLM Generation Parameters ---
try:
    MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "65536"))
except ValueError:
    MAX_OUTPUT_TOKENS = 65536  # Default fallback

try:
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.0"))
except ValueError:
    TEMPERATURE = 0.0  # Default fallback

try:
    TOP_P = float(os.getenv("TOP_P", "0.95"))
except ValueError:
    TOP_P = 0.95  # Default fallback

try:
    TOP_K = int(os.getenv("TOP_K", "40"))
except ValueError:
    TOP_K = 40  # Default fallback

try:
    CANDIDATE_COUNT = int(os.getenv("CANDIDATE_COUNT", "1"))
except ValueError:
    CANDIDATE_COUNT = 1  # Default fallback

# --- Pricing (EXAMPLE - MUST BE UPDATED WITH CURRENT GOOGLE PRICING) ---
# Prices per 1 Million tokens (Illustrative - Verify Current Pricing!)
# Find current pricing at https://ai.google.dev/pricing or Google Cloud Pricing pages
MODEL_PRICING = {
    "gemini-2.5-flash-preview-04-17": {
        "input_cost_per_million_tokens": 0.15,  # EXAMPLE PRICE USD
        "output_cost_per_million_tokens": 0.60,  # EXAMPLE PRICE USD
        "thinking_cost_per_million_tokens": 3.50,  # EXAMPLE PRICE USD (typically same as input)
        # Note: Per-image costs might apply separately or be included in token counts.
        # Check Google's documentation for the specific model.
    },
    # Add other models if needed
    "DEFAULT": {  # Fallback if model not listed
        "input_cost_per_million_tokens": 0.15,  # EXAMPLE PRICE USD
        "output_cost_per_million_tokens": 0.60,  # EXAMPLE PRICE USD
        "thinking_cost_per_million_tokens": 3.50,  # EXAMPLE PRICE USD (typically same as input)
    }
}