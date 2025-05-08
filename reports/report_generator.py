#!/usr/bin/env python3
"""
Report Generator for Data Extraction Results
-------------------------------------------
Generates comprehensive Markdown reports with cost analysis, token usage,
and record extraction statistics from image and text files.
"""

import os
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

import pandas as pd

# Import configuration
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import OUTPUT_DIR, USD_TO_INR_RATE, MODEL_PRICING, DEFAULT_MODEL

# Configure logging
logger = logging.getLogger("ReportGenerator")

class ReportGenerator:
    """Generates comprehensive reports for image and text processing results."""

    def __init__(self, output_dir: Union[str, Path] = OUTPUT_DIR):
        """
        Initialize the report generator.
        
        Args:
            output_dir: Directory where reports will be saved (defaults to config.OUTPUT_DIR)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = self.output_dir / "reports"
        self.report_dir.mkdir(exist_ok=True)
        
    def generate_report(self, 
                       record_data: Union[List[Dict], pd.DataFrame],
                       usage_data: Dict[str, Any],
                       run_metadata: Dict[str, Any] = None,
                       file_status: Dict[str, List[str]] = None) -> Path:
        """
        Generate a comprehensive Markdown report.
        
        Args:
            record_data: Extracted records as list of dicts or DataFrame
            usage_data: Token usage and cost data
            run_metadata: Additional metadata about the processing run
            file_status: Dictionary tracking the status of each processed file
            
        Returns:
            Path to the generated report file
        """
        if run_metadata is None:
            run_metadata = {}
            
        # Default empty file status if not provided
        if file_status is None:
            file_status = {"successful": [], "failed": [], "skipped": [], "in_progress": set()}
            
        # Convert record_data to DataFrame if it's a list
        if isinstance(record_data, list):
            df = pd.DataFrame(record_data)
        else:
            df = record_data
            
        # Generate timestamp for the report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.report_dir / f"data_extraction_report_{timestamp}.md"
        
        # Extract key metrics
        total_records = len(df)
        total_files = run_metadata.get("total_files", "N/A")
        successful_files = run_metadata.get("successful_files", "N/A")
        failed_files = run_metadata.get("failed_files", "N/A")
        processing_time = run_metadata.get("processing_time_seconds", "N/A")
        
        # Extract token usage and cost
        total_input_tokens = usage_data.get("total_input_tokens", 0)
        total_output_tokens = usage_data.get("total_output_tokens", 0)
        total_thinking_tokens = usage_data.get("total_thinking_tokens", 0)
        total_tokens = usage_data.get("total_tokens", total_input_tokens + total_output_tokens + total_thinking_tokens)
        total_cost_usd = usage_data.get("total_cost_usd", 0.0)
        
        # Calculate derived metrics
        tokens_per_record = total_tokens / total_records if total_records > 0 else 0
        cost_per_record_usd = total_cost_usd / total_records if total_records > 0 else 0
        total_cost_inr = total_cost_usd * USD_TO_INR_RATE
        cost_per_record_inr = cost_per_record_usd * USD_TO_INR_RATE
        
        # Format processing time
        if isinstance(processing_time, (int, float)):
            hours = int(processing_time // 3600)
            minutes = int((processing_time % 3600) // 60)
            seconds = int(processing_time % 60)
            formatted_time = f"{hours}h {minutes}m {seconds}s"
        else:
            formatted_time = str(processing_time)
        
        # Generate report content
        report_content = f"""# Data Extraction Report

## Summary

- **Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **Model Used**: {run_metadata.get("model", DEFAULT_MODEL)}
- **Total Records Extracted**: {total_records:,}
- **Files Processed**: {successful_files:,} successful / {failed_files:,} failed / {total_files:,} total
- **Processing Time**: {formatted_time}

## Token Usage

- **Input Tokens**: {total_input_tokens:,}
- **Output Tokens**: {total_output_tokens:,}
- **Thinking Tokens**: {total_thinking_tokens:,}
- **Total Tokens**: {total_tokens:,}
- **Tokens per Record**: {tokens_per_record:.2f}

## Cost Analysis

- **Cost in USD**: ${total_cost_usd:.4f}
- **Cost per Record (USD)**: ${cost_per_record_usd:.6f}
- **Current USD to INR Rate**: ₹{USD_TO_INR_RATE:.2f}
- **Cost in INR**: ₹{total_cost_inr:.4f}
- **Cost per Record (INR)**: ₹{cost_per_record_inr:.6f}

## File Processing Status

- **Successfully Processed Files**: {len(file_status.get('successful', []))}
- **Failed Files**: {len(file_status.get('failed', []))}
- **Skipped Files**: {len(file_status.get('skipped', []))} (already processed in previous runs)

"""
        # Add detailed file lists if not too lengthy
        successful_files_list = file_status.get('successful', [])
        failed_files_list = file_status.get('failed', [])
        skipped_files_list = file_status.get('skipped', [])
        
        # Only show the full list if there are a reasonable number of files
        if len(successful_files_list) + len(failed_files_list) + len(skipped_files_list) <= 100:
            # Add successful files
            if successful_files_list:
                report_content += "\n### Successfully Processed Files\n\n"
                for i, file_path in enumerate(successful_files_list):
                    report_content += f"{i+1}. {os.path.basename(file_path)}\n"
            
            # Add failed files
            if failed_files_list:
                report_content += "\n### Failed Files\n\n"
                for i, file_path in enumerate(failed_files_list):
                    report_content += f"{i+1}. {os.path.basename(file_path)}\n"
            
            # Add skipped files (if resuming)
            if skipped_files_list:
                report_content += "\n### Skipped Files (Already Processed)\n\n"
                for i, file_path in enumerate(skipped_files_list):
                    report_content += f"{i+1}. {os.path.basename(file_path)}\n"
        else:
            report_content += "\n(Too many files to list individually in the report)\n"

        report_content += "\n## Processing Details\n\n| Parameter | Value |\n|-----------|-------|\n"
                
        # Add processing details
        for key, value in run_metadata.items():
            # Skip keys already covered in the summary
            if key not in ["model", "total_files", "successful_files", "failed_files", "processing_time_seconds"]:
                report_content += f"| {key} | {value} |\n"
                
        # Write report to file
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
            
        logger.info(f"Generated report: {report_path}")
        return report_path
    
    @staticmethod
    def collect_usage_data(usage_metadata_list: List[Dict]) -> Dict[str, Any]:
        """
        Collects and summarizes token usage data from a list of usage metadata dicts.
        
        Args:
            usage_metadata_list: List of usage metadata dictionaries from API calls
            
        Returns:
            Dictionary with aggregated usage data and cost calculations
        """
        # Initialize counters
        total_input_tokens = 0
        total_output_tokens = 0
        total_thinking_tokens = 0
        total_cost_usd = 0.0
        
        # Get pricing information
        model_pricing = MODEL_PRICING.get(DEFAULT_MODEL, MODEL_PRICING["DEFAULT"])
        input_cost_per_million = model_pricing.get("input_cost_per_million_tokens", 0)
        output_cost_per_million = model_pricing.get("output_cost_per_million_tokens", 0)
        thinking_cost_per_million = model_pricing.get("thinking_cost_per_million_tokens", 0)
        
        # Process each metadata entry
        for metadata in usage_metadata_list:
            if not metadata:
                continue
                
            # Add token counts
            input_tokens = metadata.get("prompt_token_count", 0)
            output_tokens = metadata.get("candidates_token_count", 0)
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            
            # Add thinking tokens if enabled - use actual tokens used instead of budget
            thinking_enabled = metadata.get("thinking_enabled", False)
            thinking_tokens_used = metadata.get("thinking_tokens_used", 0)
            if thinking_enabled and thinking_tokens_used > 0:
                total_thinking_tokens += thinking_tokens_used
            
            # Calculate cost
            input_cost = (input_tokens / 1_000_000) * input_cost_per_million
            output_cost = (output_tokens / 1_000_000) * output_cost_per_million
            
            # Calculate thinking cost if thinking is enabled - use actual tokens used
            thinking_cost = 0.0
            if thinking_enabled and thinking_tokens_used > 0:
                thinking_cost = (thinking_tokens_used / 1_000_000) * thinking_cost_per_million
                
            # Add all costs (input, output, and thinking)
            total_cost_usd += (input_cost + output_cost + thinking_cost)
        
        return {
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_thinking_tokens": total_thinking_tokens,
            "total_tokens": total_input_tokens + total_output_tokens + total_thinking_tokens,
            "total_cost_usd": total_cost_usd,
            "pricing_per_million": {
                "input": input_cost_per_million,
                "output": output_cost_per_million,
                "thinking": thinking_cost_per_million
            },
            "usd_to_inr_rate": USD_TO_INR_RATE
        }


# Example usage (for documentation purposes only)
if __name__ == "__main__":
    print("This module is intended to be imported, not run directly.")
    print("Example usage:")
    print("from reports.report_generator import ReportGenerator")
    print("report_gen = ReportGenerator()")
    print("report_path = report_gen.generate_report(records, usage_data, run_metadata)")