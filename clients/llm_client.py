import os
import json
import logging
from typing import Dict, List, Any, Optional
from io import BytesIO

import google.genai as genai
from google.genai.types import HarmCategory, HarmBlockThreshold, GenerateContentConfig, ThinkingConfig
from PIL import Image

# Import configuration
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import (
    MODEL_PRICING, DEFAULT_MODEL, THINKING_BUDGET,
    TEMPERATURE, TOP_P, TOP_K, MAX_OUTPUT_TOKENS, CANDIDATE_COUNT
)

# Import prompt templates
from prompts.image_prompt import get_image_prompt_parts
from prompts.text_prompt import get_text_prompt_parts

# Configure logging
logger = logging.getLogger("DataProcessor")

class LLMClient:
    """Client for Google Generative AI LLM API."""

    def __init__(self):
        """Initialize Google Generative AI client."""
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("GOOGLE_MODEL", DEFAULT_MODEL)

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        # Initialize client with the new SDK
        self.client = genai.Client(api_key=self.api_key)
        logger.info(f"Initialized Google LLM Client with model: {self.model_name}")

    def get_model_pricing(self) -> Dict[str, float]:
        """
        Retrieves the pricing for the current model.
        **WARNING:** Uses hardcoded placeholder values. Update MODEL_PRICING.
        """
        pricing = MODEL_PRICING.get(self.model_name, MODEL_PRICING["DEFAULT"])
        if self.model_name not in MODEL_PRICING:
            logger.warning(f"Pricing for model '{self.model_name}' not explicitly found. Using default pricing.")
            logger.warning("PLEASE UPDATE THE 'MODEL_PRICING' DICTIONARY WITH ACCURATE VALUES.")
        elif MODEL_PRICING == {"DEFAULT": MODEL_PRICING["DEFAULT"]}: # Check if only default exists
            logger.warning("Using default pricing as specific model pricing is not set.")
            logger.warning("PLEASE UPDATE THE 'MODEL_PRICING' DICTIONARY WITH ACCURATE VALUES.")

        return pricing

    def process_image(self,
                      image_data: bytes,
                      mime_type: str,
                      schema: Dict,
                      examples: Dict = None,
                      log_thinking: bool = False
                     ) -> Dict[str, Any]:
        """Process image input through the Google Generative AI LLM."""
        logger.info(f"Processing image ({mime_type}) with Google model {self.model_name}")

        # Get prompt parts from the image prompt template
        prompt_parts = get_image_prompt_parts(schema, examples)

        # Convert image bytes to PIL Image object
        try:
            image = Image.open(BytesIO(image_data))
            content = prompt_parts + [image]
        except Exception as e:
            logger.error(f"Failed to convert image data to PIL Image: {str(e)}")
            return {
                "text": "",
                "usage_metadata": None,
                "error": f"Image conversion failed: {str(e)}"
            }

        # Generate content with the LLM
        return self._generate_content(content, log_thinking)

    def process_text(self,
                     text_data: str,
                     schema: Dict,
                     examples: Dict = None,
                     log_thinking: bool = False
                    ) -> Dict[str, Any]:
        """Process text input through the Google Generative AI LLM."""
        logger.info(f"Processing text data with Google model {self.model_name}")

        # Get prompt parts from the text prompt template
        prompt_parts = get_text_prompt_parts(schema, examples)

        # Add the text data to the prompt
        content = prompt_parts + [text_data]

        # Generate content with the LLM
        return self._generate_content(content, log_thinking)
        
    def _generate_content(self, content, log_thinking=False):
        """
        Generate content with the LLM using the provided content.
        This internal method handles the common processing for both text and image inputs.
        
        Args:
            content: The content array to send to the LLM
            log_thinking: Whether to enable LLM thinking logs
            
        Returns:
            Dictionary with response text, usage metadata, and any error
        """
        try:
            # First, get token count before generation
            prompt_token_count = 0
            try:
                # Using the correct API: client.models.count_tokens()
                token_info = self.client.models.count_tokens(
                    model=self.model_name, 
                    contents=content
                )
                prompt_token_count = getattr(token_info, 'total_tokens', 0)
                logger.info(f"Token count before generation: {prompt_token_count} tokens")
            except Exception as token_e:
                logger.warning(f"Error counting tokens: {str(token_e)}")

            # Generate content with safety settings
            safety_settings = [
                genai.types.SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                ),
                genai.types.SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                ),
                genai.types.SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                ),
                genai.types.SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                ),
            ]

            # Set thinking budget if log_thinking is enabled
            thinking_budget = THINKING_BUDGET if log_thinking else 0
            
            # Configure generation parameters using values from config
            generation_config = GenerateContentConfig(
                temperature=TEMPERATURE,
                top_p=TOP_P,
                top_k=TOP_K,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                candidate_count=CANDIDATE_COUNT,
                thinking_config=ThinkingConfig(thinking_budget=thinking_budget),
                safety_settings=safety_settings
            )
            
            # Log generation parameters for transparency
            logger.info(f"Generation parameters: temperature={TEMPERATURE}, top_p={TOP_P}, top_k={TOP_K}, max_output_tokens={MAX_OUTPUT_TOKENS}, candidate_count={CANDIDATE_COUNT}")
            if log_thinking:
                logger.info(f"Thinking budget (maximum allowed): {thinking_budget} tokens")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=content,
                config=generation_config
            )

            # Extract results and metadata
            response_text = ""
            usage_metadata = None
            error_message = None

            # Check for blocked content
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
                error_message = f"Content blocked. Reason: {response.prompt_feedback.block_reason}"
                logger.error(error_message)
                logger.error(f"Safety Ratings: {response.prompt_feedback.safety_ratings}")
                if log_thinking:
                    logger.info(f"--- LLM Raw Blocked Response (Thinking Log) ---\n{response}\n------------------------------------------")

            # Check if response has content
            elif not response.candidates or not response.candidates[0].content.parts:
                error_message = "LLM response is empty or has no content parts."
                logger.error(error_message)
                if hasattr(response, 'text'):
                    response_text = response.text.strip()
                    if response_text:
                        logger.warning(f"Response had no parts but contained text: '{response_text[:100]}...'")
                        error_message = None
                    else:
                        logger.error("Response .text is also empty.")
                if log_thinking:
                    logger.info(f"--- LLM Raw Empty Response (Thinking Log) ---\n{response}\n----------------------------------------------------")

            else:
                response_text = response.text.strip()

            # Get usage metadata from response - THIS IS THE PRIMARY SOURCE OF TRUTH
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                # Direct extraction of usage metadata from response
                prompt_token_count = getattr(response.usage_metadata, 'prompt_token_count', 0)
                candidates_token_count = getattr(response.usage_metadata, 'candidates_token_count', 0)
                total_token_count = getattr(response.usage_metadata, 'total_token_count', 0)
                
                # Calculate actual thinking tokens used (not just the budget)
                thinking_tokens_used = max(0, total_token_count - prompt_token_count - candidates_token_count)
                
                # Check if thinking tokens exceed the budget
                if log_thinking and thinking_tokens_used > thinking_budget:
                    logger.warning(f"Thinking tokens ({thinking_tokens_used}) exceeded the configured budget ({thinking_budget})!")
                    logger.warning(f"This is expected behavior as the thinking_budget is a target, not a hard limit.")
                    logger.warning(f"You will be billed for the actual thinking tokens used: {thinking_tokens_used}")
                
                usage_metadata = {
                    "prompt_token_count": prompt_token_count,
                    "candidates_token_count": candidates_token_count,
                    "total_token_count": total_token_count,
                    "thinking_enabled": log_thinking,
                    "thinking_budget": thinking_budget if log_thinking else 0,
                    "thinking_tokens_used": thinking_tokens_used if log_thinking else 0,
                    "thinking_budget_exceeded": thinking_tokens_used > thinking_budget if log_thinking else False
                }
                
                # Log any discrepancies between pre-counted tokens and API-reported tokens
                if prompt_token_count > 0 and abs(prompt_token_count - usage_metadata["prompt_token_count"]) > 10:
                    logger.warning(f"Significant token count discrepancy: Pre-counted {prompt_token_count} vs API-reported {usage_metadata['prompt_token_count']}")
                    
                logger.info(f"Retrieved usage metadata from API response: {usage_metadata}")
                if log_thinking:
                    logger.info(f"Thinking tokens used: {thinking_tokens_used} (out of {thinking_budget} budget)")
            else:
                logger.warning("Usage metadata not found in the response. Falling back to manual counting.")
                # Fallback only if usage_metadata is not available
                try:
                    # Count response tokens using the correct API
                    response_token_info = self.client.models.count_tokens(
                        model=self.model_name, 
                        contents=[response_text]
                    )
                    response_tokens = getattr(response_token_info, 'total_tokens', 0)
                    logger.info(f"Response tokens (manual count): {response_tokens}")
                    
                    usage_metadata = {
                        "prompt_token_count": prompt_token_count,
                        "candidates_token_count": response_tokens,
                        "total_token_count": prompt_token_count + response_tokens,
                        "thinking_enabled": log_thinking,
                        "thinking_budget": thinking_budget if log_thinking else 0,
                        "is_estimated": True
                    }
                    logger.warning("Using manually counted tokens since usage_metadata was not available")
                except Exception as token_e:
                    logger.warning(f"Could not count response tokens: {str(token_e)}")
                    usage_metadata = None

            if log_thinking and not error_message:
                logger.info(f"--- LLM Raw Response Text (Thinking Log) ---\n{response_text}\n--------------------------------------------")
                if usage_metadata:
                    logger.info(f"--- LLM Usage Metadata (Thinking Log) ---\n{usage_metadata}\n-------------------------------------------")

            return {
                "text": response_text,
                "usage_metadata": usage_metadata,
                "error": error_message
            }

        except Exception as e:
            logger.exception(f"An unexpected error occurred during Google Generative AI call: {str(e)}")
            return {
                "text": "",
                "usage_metadata": None,
                "error": f"API call failed: {str(e)}"
            }

    def validate_json_output(self, json_str: str) -> List[Dict]:
        """Validates and cleans JSON output from the LLM."""
        if not json_str:
            logger.warning("Received empty string for JSON validation. Returning empty list.")
            return []

        original_json_str = json_str

        # Try to strip markdown formatting first
        if json_str.startswith("```json"):
            json_str = json_str[len("```json"):].strip()
        elif json_str.startswith("```"):
            json_str = json_str[len("```"):].strip()

        if json_str.endswith("```"):
            json_str = json_str[:-len("```")].strip()

        # Ensure it starts with '[' and ends with ']'
        if not json_str.startswith('['):
            logger.warning("JSON output does not start with '['. Attempting to fix.")
            start_index = json_str.find('[')
            if start_index != -1:
                json_str = json_str[start_index:]
            else:
                logger.error("Could not find starting '[' in the JSON string.")
                logger.debug(f"Problematic JSON string (no '['): {original_json_str}")
                raise json.JSONDecodeError("JSON string does not start with '['", json_str, 0)

        if not json_str.endswith(']'):
            logger.warning("JSON output does not end with ']'. Attempting to fix.")
            end_index = json_str.rfind(']')
            if end_index != -1:
                json_str = json_str[:end_index + 1]
            else:
                logger.error("Could not find ending ']' in the JSON string.")
                logger.debug(f"Problematic JSON string (no ']'): {original_json_str}")
                raise json.JSONDecodeError("JSON string does not end with ']'", json_str, len(json_str))

        try:
            data = json.loads(json_str)

            if isinstance(data, dict):
                logger.warning("LLM returned a single JSON object instead of an array. Wrapping in a list.")
                data = [data]
            elif not isinstance(data, list):
                logger.error(f"Parsed JSON is not a list or dictionary. Type: {type(data)}")
                logger.debug(f"Problematic JSON string after cleaning: {json_str}")
                raise TypeError(f"Expected list or dict after JSON parsing, got {type(data)}")

            return data

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON output even after cleaning: {str(e)}")
            logger.error(f"Attempted JSON string: {json_str}")
            logger.debug(f"Original raw JSON string from LLM: {original_json_str}")
            raise