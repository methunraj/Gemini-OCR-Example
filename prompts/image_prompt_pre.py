#!/usr/bin/env python3
"""
Prompt Templates for Image Processing
------------------------------------
Contains system and user prompts for extracting data from images of historical Russian documents.
"""

# System prompt for image processing
SYSTEM_PROMPT = """You are a specialized extraction assistant designed for comprehensive JSON data processing from historical Russian documents and images. Your primary function is to extract ALL entries from the document image and convert them into properly structured JSON data.

CRITICAL DITTO MARK RULE: The symbol " (quotation mark) in the document is a ditto mark that means "same as above". When you encounter a " in a cell, you must copy the EXACT value from the cell directly above it.

You must:
1. Process EVERY SINGLE entry visible in the document image.
2. Include ALL entries in a JSON array.
3. Strictly adhere to the provided schema for each entry.
4. Handle ditto marks (") correctly by copying values from the cell above.
5. Only output valid JSON without any explanation text before or after.
6. Never skip or omit entries even if they seem incomplete or partially visible.
7. Never add explanatory text around the JSON.
8. Always return an array of objects, even if only one entry is found.
9. Preserve old Russian spelling (words ending in ъ, etc.).
10. Maintain proper case and formatting as seen in the document.

Remember: Your output will be programmatically parsed, so it must be valid JSON only."""

# User prompt template for image processing
USER_PROMPT_TEMPLATE = """Extract all the information from the provided historical Russian document image and convert it into a JSON array following the exact schema provided below. You MUST process and include EVERY entry from the image.

DITTO MARK HANDLING: The " symbol in the document means to repeat the value from the cell directly above it. For example:
- If cell 1 contains "Бессарабская губ."
- And cell 2 contains ""
- Then cell 2 should have the value "Бессарабская губ."

Schema:
{schema}
"""

# Additional instructions to append to the user prompt
ADDITIONAL_INSTRUCTIONS = """
For each entry in the document image, create a separate object in the JSON array following the EXACT format shown above. DO NOT combine multiple entries into a single object.

CRITICAL DITTO MARK INSTRUCTION: When you see a " symbol in any field, replace it with the exact value from the cell directly above it. This is essential for accurate data extraction.

Important instructions:
1. Process ALL entries, not just one example.
2. Handle ALL ditto marks (") by replacing them with the value from the cell above.
3. Return ONLY valid JSON without any surrounding explanation.
4. The final response must be a JSON array containing ALL entries.
5. Each array item must follow the schema exactly and match the format shown in the examples.
6. If any field is missing in an entry, use null.
7. Preserve old Russian spelling (Аккерманъ, Хотинъ, etc.).
8. Ensure all nullable fields are null if absent, not empty strings unless the schema dictates otherwise.
9. Output must be valid JSON that can be parsed with json.loads(). The output MUST start with '[' and end with ']'.
10. For rows with ditto marks, look at the cell DIRECTLY above the current cell to find the value to copy.
"""

# Example template to add if examples are provided
EXAMPLE_TEMPLATE = """
Here are some examples of text entries and their expected JSON output:

Example Text Showing Ditto Mark Usage:
{example_records}

Expected JSON output (note how ditto marks are resolved):
{example_json_output}
"""

def get_image_prompt_parts(schema, examples=None):
    """
    Generate prompt parts for image processing.
    
    Args:
        schema: The schema to use for extraction (will be JSON formatted)
        examples: Optional dictionary with example_records and example_json_output
        
    Returns:
        List of prompt parts
    """
    import json
    
    # Format the schema as JSON 
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
    
    # Start with system prompt and user prompt with the schema filled in
    prompt_parts = [
        SYSTEM_PROMPT,
        USER_PROMPT_TEMPLATE.format(schema=schema_json)
    ]
    
    # Add examples if provided
    if examples and 'example_records' in examples and 'example_json_output' in examples:
        example_text = EXAMPLE_TEMPLATE.format(
            example_records=examples['example_records'],
            example_json_output=examples['example_json_output']
        )
        prompt_parts[1] += example_text
    
    # Add the additional instructions to the user prompt
    prompt_parts[1] += ADDITIONAL_INSTRUCTIONS
    
    return prompt_parts