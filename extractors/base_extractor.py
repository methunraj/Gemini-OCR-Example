import logging
import json
import time
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Union, Optional, Any, Tuple, Set
import concurrent.futures
import multiprocessing

import pandas as pd

# Import from our modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import (
    CALCULATE_COST, LOG_LLM_THINKING, 
    ENABLE_CHECKPOINTING, CHECKPOINT_FILE, RESUME_FROM_CHECKPOINT
)
from handlers.input_handler import InputHandler
from clients.llm_client import LLMClient
from managers.output_manager import OutputManager
from reports.report_generator import ReportGenerator

# Configure logging
logger = logging.getLogger("DataProcessor")

class BaseExtractor:
    """Base class for extracting structured data from images using Google AI."""

    def __init__(self,
                output_dir: Union[str, Path] = "./output",
                schema: Dict = None,
                examples: Dict = None):
        """
        Initialize the base extractor.

        Args:
            output_dir: Directory for output files
            schema: Schema for data extraction (must be provided by subclass if None)
            examples: Dictionary containing example_records and example_json_output for few-shot learning
        """
        if schema is None:
            raise ValueError("Schema must be provided either directly or by a subclass")
            
        self.llm_client = LLMClient()
        self.output_manager = OutputManager(output_dir=output_dir)
        self.report_generator = ReportGenerator(output_dir=output_dir)
        self.schema = schema
        self.examples = examples
        self.total_cost = 0.0  # Initialize total cost accumulator
        self.usage_metadata_list = []  # Store usage metadata for reporting
        self.run_metadata = {
            "total_files": 0,
            "successful_files": 0,
            "failed_files": 0,
            "model": self.llm_client.model_name,
            "start_time": None,
            "end_time": None,
            "processing_time_seconds": 0
        }
        self.processed_files: Set[str] = set()  # Track processed files for checkpointing
        
        # Detailed file tracking for reporting
        self.file_status = {
            "successful": [],      # Files that were successfully processed
            "failed": [],          # Files that failed during processing
            "skipped": [],         # Files that were skipped (already processed)
            "in_progress": set(),  # Files currently being processed
        }

    def _calculate_and_log_cost(self, usage_metadata: Optional[Dict], filename: str) -> float:
        """
        Calculates and logs the cost for a single API call.
        
        Args:
            usage_metadata: Metadata from the API response containing token counts
            filename: Name of the processed file for logging purposes
            
        Returns:
            Estimated cost of the API call
        """
        if not CALCULATE_COST or not usage_metadata:
            if CALCULATE_COST and not usage_metadata:
                logger.warning(f"Cannot calculate cost for {filename}: Usage metadata missing.")
            return 0.0  # Return 0 cost if not calculating or no data

        try:
            pricing = self.llm_client.get_model_pricing()
            input_tokens = usage_metadata.get("prompt_token_count", 0)
            output_tokens = usage_metadata.get("candidates_token_count", 0)
            thinking_enabled = usage_metadata.get("thinking_enabled", False)
            thinking_tokens_used = usage_metadata.get("thinking_tokens_used", 0)
            total_tokens = usage_metadata.get("total_token_count", 0)

            # Calculate costs based on token usage and pricing
            input_cost = (input_tokens / 1_000_000) * pricing.get("input_cost_per_million_tokens", 0)
            output_cost = (output_tokens / 1_000_000) * pricing.get("output_cost_per_million_tokens", 0)
            
            # Calculate thinking cost using actual tokens used (not just the budget)
            thinking_cost = 0.0
            if thinking_enabled and thinking_tokens_used > 0:
                thinking_cost = (thinking_tokens_used / 1_000_000) * pricing.get("thinking_cost_per_million_tokens", 0)
            
            total_call_cost = input_cost + output_cost + thinking_cost

            # Log detailed cost breakdown
            logger.info(f"Cost estimation for {filename}:")
            logger.info(f"  Input Tokens : {input_tokens:<7} | Output Tokens: {output_tokens:<7}")
            if thinking_enabled:
                thinking_budget_exceeded = usage_metadata.get("thinking_budget_exceeded", False)
                if thinking_budget_exceeded:
                    logger.warning(f"  Thinking Tokens: {thinking_tokens_used:<7} (EXCEEDS budget of {usage_metadata.get('thinking_budget', 0)})")
                    logger.warning(f"  This is normal behavior - thinking_budget is a target, not a strict limit")
                else:
                    logger.info(f"  Thinking Tokens: {thinking_tokens_used:<7} (within budget of {usage_metadata.get('thinking_budget', 0)})")
                    
                logger.info(f"  Calculation: total_token_count ({total_tokens}) - prompt_token_count ({input_tokens}) - candidates_token_count ({output_tokens}) = thinking_tokens ({thinking_tokens_used})")
            logger.info(f"  Total Tokens: {total_tokens}")
                
            logger.info(f"  Input Cost   : ${input_cost:<9.6f} | Output Cost  : ${output_cost:<9.6f}")
            if thinking_enabled:
                logger.info(f"  Thinking Cost: ${thinking_cost:<9.6f} (based on actual {thinking_tokens_used} tokens used)")
            logger.info(f"  Total Est Cost: ${total_call_cost:<9.6f}")
            logger.info("  (Note: Costs are estimates based on configured pricing. Verify official Google pricing.)")
            

            # Store metadata for reporting
            if usage_metadata:
                self.usage_metadata_list.append(usage_metadata)

            return total_call_cost

        except Exception as e:
            logger.error(f"Error calculating cost for {filename}: {str(e)}")
            return 0.0

    def _save_checkpoint(self):
        """
        Save the current state of processed files to a checkpoint file.
        """
        if ENABLE_CHECKPOINTING:
            try:
                with open(CHECKPOINT_FILE, "w") as f:
                    json.dump(list(self.processed_files), f)
                logger.info(f"Checkpoint saved to {CHECKPOINT_FILE}.")
            except Exception as e:
                logger.error(f"Failed to save checkpoint: {str(e)}")

    def _load_checkpoint(self):
        """
        Load the state of processed files from a checkpoint file.
        """
        if RESUME_FROM_CHECKPOINT and os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, "r") as f:
                    self.processed_files = set(json.load(f))
                logger.info(f"Checkpoint loaded from {CHECKPOINT_FILE}.")
            except Exception as e:
                logger.error(f"Failed to load checkpoint: {str(e)}")

    def process_file(self, file_path: Union[str, Path]) -> Optional[List[Dict]]:
        """
        Process a single image or text file using Google Generative AI.

        Args:
            file_path: Path to input file (image or txt)

        Returns:
            Extracted records as a list of dicts, or None if processing failed.
        """
        logger.info(f"Processing file: {file_path}")
        call_cost = 0.0  # Cost for this specific file
        records = None  # Initialize records to None
        
        # Update run metadata
        self.run_metadata["total_files"] += 1

        try:
            file_data = InputHandler.read_file(file_path)
            if not file_data:
                self.run_metadata["failed_files"] += 1
                self.file_status["failed"].append(str(file_path))
                return None
                
            # Process file based on file type
            if file_data["type"] == "image":
                # Process image using LLM
                llm_response = self.llm_client.process_image(
                    image_data=file_data["content"],
                    mime_type=file_data["mime_type"],
                    schema=self.schema,
                    examples=self.examples,
                    log_thinking=LOG_LLM_THINKING
                )
            elif file_data["type"] == "text":
                # Process text using LLM
                llm_response = self.llm_client.process_text(
                    text_data=file_data["content"],
                    schema=self.schema,
                    examples=self.examples,
                    log_thinking=LOG_LLM_THINKING
                )
            else:
                logger.error(f"Unsupported file type: {file_data['type']}")
                self.run_metadata["failed_files"] += 1
                self.file_status["failed"].append(str(file_path))
                return None

            # Check for processing errors reported by LLMClient
            if llm_response.get("error"):
                logger.error(f"LLM processing failed for {file_path.name}: {llm_response['error']}")
                # Calculate cost even on failure if usage data exists (e.g., blocked request)
                call_cost = self._calculate_and_log_cost(llm_response.get("usage_metadata"), file_path.name)
                self.total_cost += call_cost
                self.run_metadata["failed_files"] += 1
                self.file_status["failed"].append(str(file_path))
                return None  # Indicate failure

            response_text = llm_response.get("text")
            usage_metadata = llm_response.get("usage_metadata")

            # Calculate and log cost for this call
            call_cost = self._calculate_and_log_cost(usage_metadata, file_path.name)
            self.total_cost += call_cost  # Accumulate total cost

            # Parse and validate JSON response
            records = self.llm_client.validate_json_output(response_text)

            logger.info(f"Successfully extracted {len(records)} records from {file_path}")
            self.run_metadata["successful_files"] += 1
            self.file_status["successful"].append(str(file_path))

            # Save records from this file
            self.output_manager.save_to_excel(records, file_data["filename"])

            # Add file to processed files set for checkpointing
            self.processed_files.add(str(file_path))
            self._save_checkpoint()

            return records

        except FileNotFoundError as e:
            logger.error(f"File not found error during processing {file_path}: {str(e)}")
            self.run_metadata["failed_files"] += 1
            self.file_status["failed"].append(str(file_path))
            return None
        except ValueError as e:  # Catches unsupported file types from InputHandler
            logger.error(f"Value error during processing {file_path}: {str(e)}")
            self.run_metadata["failed_files"] += 1
            self.file_status["failed"].append(str(file_path))
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for file {file_path}.")
            self.run_metadata["failed_files"] += 1
            self.file_status["failed"].append(str(file_path))
            # Cost already calculated and logged before this point if API call succeeded
            return None
        except TypeError as e:
            logger.error(f"Type error during processing {file_path} (likely post-JSON parsing): {str(e)}")
            self.run_metadata["failed_files"] += 1
            self.file_status["failed"].append(str(file_path))
            return None
        except Exception as e:
            logger.exception(f"An unexpected error occurred processing file {file_path}: {str(e)}")
            self.run_metadata["failed_files"] += 1
            self.file_status["failed"].append(str(file_path))
            # Try to calculate cost if usage_metadata was potentially retrieved before exception
            if 'usage_metadata' in locals() and usage_metadata:
                call_cost = self._calculate_and_log_cost(usage_metadata, file_path.name)
                self.total_cost += call_cost
            return None

    def process_directory(self, directory_path: Union[str, Path],
                        recursive: bool = False,
                        parallel: bool = False,
                        max_workers: int = None) -> pd.DataFrame:
        """
        Process all supported files (images and text) in a directory.

        Args:
            directory_path: Directory containing input files
            recursive: Whether to process subdirectories
            parallel: Whether to process files in parallel
            max_workers: Maximum number of worker processes (None = auto-determine)

        Returns:
            Combined DataFrame of all successfully processed files.
        """
        logger.info(f"Processing directory: {directory_path}")
        logger.info(f"Parallel processing: {'Enabled' if parallel else 'Disabled'}")
        self.total_cost = 0.0  # Reset total cost for the directory run
        self.usage_metadata_list = []  # Reset usage metadata list
        
        # Reset and start tracking run metadata
        self.run_metadata = {
            "total_files": 0,
            "successful_files": 0,
            "failed_files": 0,
            "model": self.llm_client.model_name,
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "recursive_processing": recursive,
            "parallel_processing": parallel,
            "max_workers": max_workers if parallel else "N/A"
        }
        
        start_time = time.time()

        try:
            files = InputHandler.get_files_from_directory(directory_path, recursive)
        except NotADirectoryError as e:
            logger.error(str(e))
            return pd.DataFrame()

        if not files:
            logger.warning(f"No supported files found in {directory_path}. Exiting directory processing.")
            return pd.DataFrame()

        logger.info(f"Found {len(files)} files to process.")

        # Load checkpoint if enabled
        self._load_checkpoint()

        successful_files = 0
        failed_files = 0
        
        if parallel:
            # Determine sensible number of workers if not specified
            if max_workers is None:
                max_workers = min(multiprocessing.cpu_count(), len(files))
                logger.info(f"Auto-detected {max_workers} worker processes")
            
            results = []
            # Process files in parallel using ProcessPoolExecutor
            with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
                # Initialize individual extractors for each worker to avoid conflicts
                futures = []
                
                # We can't directly process with self in multiple processes since it's not picklable
                # Instead, submit individual file processing jobs
                # Initialize aspects that need to be in each process
                for i, file_path in enumerate(files):
                    if str(file_path) in self.processed_files:
                        logger.info(f"Skipping already processed file: {file_path.name}")
                        self.file_status["skipped"].append(str(file_path))
                        continue

                    logger.info(f"Submitting file {i+1}/{len(files)}: {file_path.name}")
                    
                    # We need to use a wrapper function for process_file 
                    # since we can't pickle the 'self' object for parallel processing
                    futures.append((file_path, executor.submit(
                        self._process_file_wrapper, 
                        file_path,
                        self.schema,
                        self.examples,
                    )))
                
                # Collect results as they complete
                for file_path, future in futures:
                    try:
                        result, file_cost, status, usage_metadata = future.result()
                        if status == "success":
                            successful_files += 1
                            logger.info(f"Successfully processed: {file_path.name}")
                            self.run_metadata["successful_files"] += 1
                            self.file_status["successful"].append(str(file_path))
                            
                            if result:
                                # We need to save results outside the worker process
                                self.output_manager.save_to_excel(result, file_path.name)
                                results.extend(result)
                        else:
                            failed_files += 1
                            self.run_metadata["failed_files"] += 1
                            self.file_status["failed"].append(str(file_path))
                            logger.error(f"Failed to process: {file_path.name}")
                        
                        # Add cost from this file to total
                        if file_cost > 0:
                            self.total_cost += file_cost
                        
                        # Update total files counter
                        self.run_metadata["total_files"] += 1
                            
                        # Collect usage metadata for reporting
                        if usage_metadata:
                            logger.info(f"Collected token usage for {file_path.name}: {usage_metadata.get("prompt_token_count", 0)} input, {usage_metadata.get("candidates_token_count", 0)} output tokens")
                            self.usage_metadata_list.append(usage_metadata)
                            
                    except Exception as e:
                        failed_files += 1
                        self.run_metadata["failed_files"] += 1
                        self.run_metadata["total_files"] += 1
                        self.file_status["failed"].append(str(file_path))
                        logger.error(f"Exception in parallel processing for {file_path.name}: {str(e)}")
        else:
            # Sequential processing (original behavior)
            for i, file_path in enumerate(files):
                if str(file_path) in self.processed_files:
                    logger.info(f"Skipping already processed file: {file_path.name}")
                    self.file_status["skipped"].append(str(file_path))
                    continue

                logger.info(f"--- Processing file {i+1}/{len(files)}: {file_path.name} ---")
                result = self.process_file(file_path)
                if result is not None:
                    successful_files += 1
                else:
                    failed_files += 1
                logger.info(f"--- Finished processing file {i+1}/{len(files)} ---")

        # Calculate total processing time
        end_time = time.time()
        processing_time = end_time - start_time
        self.run_metadata["end_time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.run_metadata["processing_time_seconds"] = processing_time
                
        logger.info(f"Directory processing summary: {successful_files} files processed successfully, {failed_files} files failed.")

        # Log total estimated cost
        if CALCULATE_COST:
            logger.info(f"--- Total Estimated Cost for Directory Run ---")
            logger.info(f"Total accumulated estimated cost: ${self.total_cost:.6f}")
            logger.info(f"(Based on configured pricing: {self.llm_client.get_model_pricing()})")
            logger.warning("REMINDER: Verify official Google pricing for accuracy.")
            logger.info(f"----------------------------------------------")
            
            # Log collected token usage metadata
            total_input_tokens = sum(meta.get("prompt_token_count", 0) for meta in self.usage_metadata_list)
            total_output_tokens = sum(meta.get("candidates_token_count", 0) for meta in self.usage_metadata_list)
            total_thinking_tokens = sum(meta.get("thinking_budget", 0) if meta.get("thinking_enabled", False) else 0 for meta in self.usage_metadata_list)
            total_tokens = total_input_tokens + total_output_tokens + total_thinking_tokens
            logger.info(f"Total token usage for this run: {total_input_tokens:,} input + {total_output_tokens:,} output + {total_thinking_tokens:,} thinking = {total_tokens:,} total tokens")

        # Save combined output from all successfully processed files
        self.output_manager.save_combined_dataframe()
        
        # Generate a report
        self.generate_run_report()

        return self.output_manager.get_combined_dataframe()
        
    @staticmethod
    def _process_file_wrapper(file_path, schema, examples):
        """
        Wrapper function for parallel processing of files.
        This creates independent resources per process.
        
        Args:
            file_path: Path to the file to process
            schema: Schema to use for processing
            examples: Examples to use for processing
            
        Returns:
            Tuple containing (results, cost, status, usage_metadata)
        """
        try:
            from handlers.input_handler import InputHandler
            from clients.llm_client import LLMClient
            from config import LOG_LLM_THINKING, ENABLE_CHECKPOINTING, CHECKPOINT_FILE
            import json

            logger = logging.getLogger("DataProcessor.Worker")

            llm_client = LLMClient()  # Create a new client for each worker
            file_cost = 0
            usage_metadata = None
            
            try:
                # Read file
                file_data = InputHandler.read_file(file_path)
                if not file_data:
                    return None, 0, "failed", None
                
                # Process based on file type
                if file_data["type"] == "image":
                    # Process image
                    llm_response = llm_client.process_image(
                        image_data=file_data["content"],
                        mime_type=file_data["mime_type"],
                        schema=schema,
                        examples=examples,
                        log_thinking=LOG_LLM_THINKING
                    )
                elif file_data["type"] == "text":
                    # Process text
                    llm_response = llm_client.process_text(
                        text_data=file_data["content"],
                        schema=schema,
                        examples=examples,
                        log_thinking=LOG_LLM_THINKING
                    )
                else:
                    logger.error(f"Unsupported file type: {file_data['type']}")
                    return None, 0, "failed", None
                
                # Check for errors
                if llm_response.get("error"):
                    logger.error(f"LLM processing failed for {file_path.name}: {llm_response['error']}")
                    # Even for failed requests, we might have usage metadata (like for rate limits)
                    return None, 0, "failed", llm_response.get("usage_metadata")
                
                # Get the cost if available (not calculating here to avoid duplicate logging)
                usage_metadata = llm_response.get("usage_metadata")
                if usage_metadata:
                    pricing = llm_client.get_model_pricing()
                    input_tokens = usage_metadata.get("prompt_token_count", 0)
                    output_tokens = usage_metadata.get("candidates_token_count", 0)
                    thinking_enabled = usage_metadata.get("thinking_enabled", False)
                    thinking_tokens_used = usage_metadata.get("thinking_tokens_used", 0) if thinking_enabled else 0
                    
                    # Calculate costs using pricing from model
                    input_cost = (input_tokens / 1_000_000) * pricing.get("input_cost_per_million_tokens", 0)
                    output_cost = (output_tokens / 1_000_000) * pricing.get("output_cost_per_million_tokens", 0)
                    thinking_cost = (thinking_tokens_used / 1_000_000) * pricing.get("thinking_cost_per_million_tokens", 0) if thinking_enabled else 0
                    
                    file_cost = input_cost + output_cost + thinking_cost
                
                # Parse response
                records = llm_client.validate_json_output(llm_response.get("text", ""))
                
                # Update checkpoint for this file - needed for parallel processing
                if ENABLE_CHECKPOINTING:
                    try:
                        # We need a separate lock for each worker process
                        import fcntl
                        
                        # Get existing processed files
                        processed_files = []
                        try:
                            if os.path.exists(CHECKPOINT_FILE):
                                with open(CHECKPOINT_FILE, "r") as f:
                                    # Use file locking to prevent race conditions
                                    fcntl.flock(f, fcntl.LOCK_EX)
                                    processed_files = json.load(f)
                                    fcntl.flock(f, fcntl.LOCK_UN)
                        except Exception as e:
                            logger.error(f"Error reading checkpoint file: {str(e)}")
                            processed_files = []

                        # Add this file to the processed list
                        if str(file_path) not in processed_files:
                            processed_files.append(str(file_path))
                            
                        # Write updated checkpoint file
                        with open(CHECKPOINT_FILE, "w") as f:
                            # Lock the file during write
                            fcntl.flock(f, fcntl.LOCK_EX)
                            json.dump(processed_files, f)
                            fcntl.flock(f, fcntl.LOCK_UN)
                        
                    except Exception as e:
                        logger.error(f"Error updating checkpoint file in worker process: {str(e)}")
                
                return records, file_cost, "success", usage_metadata
                
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                return None, file_cost, "failed", usage_metadata
                
        except Exception as main_e:
            # Catch-all for any serious errors
            print(f"Critical error in worker process: {str(main_e)}")
            return None, 0, "failed", None

    def generate_run_report(self) -> Optional[Path]:
        """
        Generate a comprehensive report of the processing run.
        
        Returns:
            Path to the generated report file, or None if generation failed
        """
        try:
            # Get all data for reporting
            df = self.output_manager.get_combined_dataframe()
            
            if df.empty:
                logger.warning("No data available for report generation.")
                return None
                
            # Collect usage data
            usage_data = ReportGenerator.collect_usage_data(self.usage_metadata_list)
            
            # Generate the report
            report_path = self.report_generator.generate_report(
                record_data=df,
                usage_data=usage_data,
                run_metadata=self.run_metadata,
                file_status=self.file_status
            )
            
            # Log file processing summary
            logger.info(f"File processing summary:")
            logger.info(f"  Successfully processed: {len(self.file_status['successful'])} files")
            logger.info(f"  Failed to process: {len(self.file_status['failed'])} files")
            logger.info(f"  Skipped (already processed): {len(self.file_status['skipped'])} files")
            logger.info(f"Generated comprehensive report at: {report_path}")
            
            return report_path
            
        except Exception as e:
            logger.error(f"Failed to generate report: {str(e)}")
            return None