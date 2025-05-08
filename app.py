#!/usr/bin/env python3
"""
Data Extraction Application for Structured Data
----------------------------------------------
This application uses Google's Generative AI to extract structured data from images and text files.
"""

import os
import sys
import logging
import mimetypes
import argparse
import multiprocessing
import time
from pathlib import Path
from datetime import datetime

# Import configuration
from config import (
    INPUT_PATH, OUTPUT_DIR, PROCESS_RECURSIVELY, 
    LOG_LLM_THINKING, CALCULATE_COST,
    ENABLE_PARALLEL, MAX_WORKERS, USD_TO_INR_RATE,
    ENABLE_CHECKPOINTING, CHECKPOINT_FILE, RESUME_FROM_CHECKPOINT
)

# Initialize logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("DataProcessor")

# Import our extractor
from extractors.military_records_extractor import MilitaryRecordsExtractor

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Extract structured data from images and text files using Google Generative AI.')
    
    # Input/output options
    parser.add_argument('--input', '-i', type=str, default=INPUT_PATH,
                        help='Input file or directory path')
    parser.add_argument('--output', '-o', type=str, default=OUTPUT_DIR,
                        help='Output directory for results')
    parser.add_argument('--recursive', '-r', action='store_true', default=PROCESS_RECURSIVELY,
                        help='Process directories recursively')
    
    # Parallel processing options
    parser.add_argument('--parallel', '-p', action='store_true', default=ENABLE_PARALLEL,
                        help='Enable parallel processing')
    parser.add_argument('--workers', '-w', type=int, default=MAX_WORKERS,
                        help=f'Number of worker processes (default from .env: {MAX_WORKERS if MAX_WORKERS > 0 else "auto-detect"})')
    
    # Checkpoint options
    parser.add_argument('--enable-checkpoint', action='store_true', default=ENABLE_CHECKPOINTING,
                        help='Enable checkpointing to track processed files')
    parser.add_argument('--checkpoint-file', type=str, default=CHECKPOINT_FILE,
                        help='Path to checkpoint file')
    parser.add_argument('--resume', action='store_true', default=RESUME_FROM_CHECKPOINT,
                        help='Resume processing from last checkpoint')
    
    # Debug options
    parser.add_argument('--log-thinking', action='store_true', default=LOG_LLM_THINKING,
                        help='Log LLM prompts and raw responses')
    parser.add_argument('--calculate-cost', action='store_true', default=CALCULATE_COST,
                        help='Calculate and log API cost estimates')
    
    return parser.parse_args()

def main():
    """Main function to run the extractor."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Override config with command line arguments
    input_path = args.input
    output_dir = args.output
    process_recursively = args.recursive
    parallel_processing = args.parallel
    max_workers = args.workers if args.workers > 0 else None  # Convert 0 to None for auto-detection
    log_thinking = args.log_thinking
    calculate_cost = args.calculate_cost
    
    # Get checkpoint settings from arguments
    enable_checkpoint = args.enable_checkpoint
    checkpoint_file = args.checkpoint_file
    resume_from_checkpoint = args.resume
    
    logger.info(f"Starting Data Processing Application")
    logger.info(f"Input: {input_path}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Recursive processing: {process_recursively}")
    logger.info(f"Parallel processing: {'Enabled' if parallel_processing else 'Disabled'}")
    if parallel_processing:
        logger.info(f"Worker processes: {max_workers if max_workers else 'Auto'}")
    logger.info(f"Log LLM Thinking (Prompt/Response): {log_thinking}")
    logger.info(f"Calculate Cost Estimate: {calculate_cost}")
    logger.info(f"USD to INR conversion rate: {USD_TO_INR_RATE}")
    
    # Log checkpoint configuration
    logger.info(f"Checkpointing: {'Enabled' if enable_checkpoint else 'Disabled'}")
    if enable_checkpoint:
        logger.info(f"Checkpoint file: {checkpoint_file}")
        logger.info(f"Resume from checkpoint: {'Yes' if resume_from_checkpoint else 'No'}")
        if resume_from_checkpoint:
            logger.info("RESUME MODE ACTIVE: Will skip previously processed files")
        else:
            logger.info("Starting fresh processing run (use --resume to continue from previous run)")

    try:
        # Initialize the appropriate extractor
        extractor = MilitaryRecordsExtractor(output_dir=output_dir)
        
        # Log the pricing being used if calculating cost
        if calculate_cost:
            pricing = extractor.llm_client.get_model_pricing()
            logger.info(f"Using Model: {extractor.llm_client.model_name} with estimated pricing (per 1M tokens):")
            logger.info(f"Input=${pricing.get('input_cost_per_million_tokens', 0):.2f}, Output=${pricing.get('output_cost_per_million_tokens', 0):.2f}")
            logger.warning("!!! Ensure these prices match current official Google Cloud/AI pricing !!!")

    except ValueError as e:
        logger.error(f"Failed to initialize extractor: {str(e)}")
        return 1
    except Exception as e:
        logger.exception(f"An unexpected error occurred during initialization: {str(e)}")
        return 1

    input_path = Path(input_path)
    if not input_path.exists():
        logger.error(f"Input path does not exist: {input_path}")
        return 1

    if input_path.is_file():
        # Set up metadata for single file processing
        extractor.run_metadata = {
            "total_files": 1,
            "successful_files": 0,
            "failed_files": 0,
            "model": extractor.llm_client.model_name,
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "single_file_mode": True,
            "filename": input_path.name
        }
        
        start_time = time.time()
        logger.info(f"Processing single file: {input_path}")
        
        # Process the file
        result = extractor.process_file(input_path)
        
        # Calculate processing time
        end_time = time.time()
        processing_time = end_time - start_time
        extractor.run_metadata["end_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        extractor.run_metadata["processing_time_seconds"] = processing_time
        
        # Log total cost for the single file run
        if calculate_cost:
            logger.info(f"--- Total Estimated Cost for Single File Run ---")
            logger.info(f"Total estimated cost: ${extractor.total_cost:.6f}")
            logger.warning("REMINDER: Verify official Google pricing for accuracy.")
            logger.info(f"-----------------------------------------------")
        
        # Generate report if file was processed successfully
        if result is not None:
            report_path = extractor.generate_run_report()
            if report_path:
                logger.info(f"Generated report: {report_path}")

    elif input_path.is_dir():
        logger.info(f"Processing directory: {input_path} {'recursively' if process_recursively else ''}")
        extractor.process_directory(
            input_path,
            recursive=process_recursively,
            parallel=parallel_processing,
            max_workers=max_workers
        )
        # Total cost for directory is logged within process_directory
    else:
        logger.error(f"Input path is neither a file nor a directory: {input_path}")
        return 1

    logger.info("Processing run finished.")
    final_df = extractor.output_manager.get_combined_dataframe()
    logger.info(f"Total records extracted across all successful files: {len(final_df)}")

    return 0


if __name__ == "__main__":
    mimetypes.init()
    exit_code = main()
    exit(exit_code)