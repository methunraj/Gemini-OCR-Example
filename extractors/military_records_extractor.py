import logging
from pathlib import Path
from typing import Dict, Union

# Import base extractor
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from extractors.base_extractor import BaseExtractor
from schemas.military_schema import MILITARY_RECORD_SCHEMA, EXAMPLE_RECORDS, EXAMPLE_JSON_OUTPUT

# Configure logging
logger = logging.getLogger("DataProcessor")

class MilitaryRecordsExtractor(BaseExtractor):
    """Military records extractor class that extends the base extractor."""

    def __init__(self, output_dir: Union[str, Path] = "./output"):
        """
        Initialize the military records extractor with the appropriate schema and examples.
        
        Args:
            output_dir: Directory for output files
        """
        examples = {
            "example_records": EXAMPLE_RECORDS,
            "example_json_output": EXAMPLE_JSON_OUTPUT
        }
        
        logger.info("Initializing Military Records Extractor")
        super().__init__(
            output_dir=output_dir,
            schema=MILITARY_RECORD_SCHEMA,
            examples=examples
        )
        
    def __str__(self):
        """String representation of this extractor."""
        return "Military Records Extractor (Extracts military casualty records from historical documents)"