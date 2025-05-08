import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Union

import pandas as pd

# Configure logging
logger = logging.getLogger("ImageProcessor")

class OutputManager:
    """Manages the output files and dataframes."""

    def __init__(self, output_dir: Union[str, Path]):
        """
        Initialize the output manager.
        
        Args:
            output_dir: Directory where output files will be saved
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.all_data = []

    def save_to_excel(self, data: List[Dict], filename: str) -> Optional[Path]:
        """
        Save extracted records to an Excel file.
        
        Args:
            data: List of dictionaries containing the extracted data
            filename: Base filename to save to
            
        Returns:
            Path to the created Excel file, or None if creation failed
        """
        if not data:
            logger.warning(f"No data provided to save for {filename}. Skipping Excel creation.")
            return None
        try:
            df = pd.DataFrame(data)
        except Exception as e:
            logger.error(f"Failed to create DataFrame for {filename}: {str(e)}")
            logger.debug(f"Data that caused error: {data}")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = Path(filename).stem
        output_path = self.output_dir / f"{base_name}_{timestamp}.xlsx"

        try:
            df.to_excel(output_path, index=False, engine='openpyxl')
            logger.info(f"Saved output ({len(data)} records) to: {output_path}")
            self.all_data.extend(data)
            return output_path
        except Exception as e:
            logger.error(f"Failed to save Excel file {output_path}: {str(e)}")
            return None

    def get_combined_dataframe(self) -> pd.DataFrame:
        """
        Get a DataFrame containing all processed data.
        
        Returns:
            DataFrame with all extracted records
        """
        if not self.all_data:
            return pd.DataFrame()
        try:
            return pd.DataFrame(self.all_data)
        except Exception as e:
            logger.error(f"Failed to create combined DataFrame: {str(e)}")
            logger.debug(f"Combined data that caused error (first 10 items): {self.all_data[:10]}")
            return pd.DataFrame()

    def save_combined_dataframe(self, filename: str = "combined_output") -> Optional[Path]:
        """
        Save all collected data to a single Excel file.
        
        Args:
            filename: Base name for the output file
            
        Returns:
            Path to the created Excel file, or None if creation failed
        """
        if not self.all_data:
            logger.warning("No combined data to save.")
            return None

        df = self.get_combined_dataframe()
        if df.empty and self.all_data:
            logger.error("Combined DataFrame is empty despite having collected data. Cannot save.")
            return None
        elif df.empty:
            logger.info("Combined DataFrame is empty (no data collected). Skipping save.")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"{filename}_{timestamp}.xlsx"

        try:
            df.to_excel(output_path, index=False, engine='openpyxl')
            logger.info(f"Saved combined output ({len(self.all_data)} records) to: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to save combined Excel file {output_path}: {str(e)}")
            return None