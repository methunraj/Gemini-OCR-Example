import logging
import mimetypes
from pathlib import Path
from typing import List, Dict, Union, Any

# Configure logging
logger = logging.getLogger("DataProcessor")

class InputHandler:
    """Handles different types of input files for processing."""

    @staticmethod
    def read_file(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Read an image or text file and prepare it for LLM processing.

        Args:
            file_path: Path to the input file (image or txt)

        Returns:
            Dict containing file content, filename, and mime type
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.suffix.lower()
        supported_image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
        
        if ext in supported_image_extensions:
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type or not mime_type.startswith('image/'):
                logger.warning(f"Could not reliably determine MIME type for {file_path.name}. Defaulting to image/jpeg.")
                mime_type = 'image/jpeg'

            with open(file_path, 'rb') as f:
                image_data = f.read()

            return {
                "type": "image",
                "content": image_data,
                "filename": file_path.name,
                "mime_type": mime_type
            }
        elif ext == '.txt':
            # Handle text files (OCR output)
            logger.info(f"Processing text file: {file_path.name}")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
                
                return {
                    "type": "text",
                    "content": text_content,
                    "filename": file_path.name,
                    "mime_type": "text/plain"
                }
            except UnicodeDecodeError:
                # Try alternative encodings if UTF-8 fails
                try:
                    with open(file_path, 'r', encoding='cp1251') as f:  # Try Windows Cyrillic
                        text_content = f.read()
                    logger.info(f"File {file_path.name} decoded using Windows-1251 encoding")
                    return {
                        "type": "text",
                        "content": text_content,
                        "filename": file_path.name,
                        "mime_type": "text/plain"
                    }
                except:
                    logger.error(f"Failed to decode text file {file_path.name} with multiple encodings")
                    raise ValueError(f"Could not decode text file: {file_path}")
        else:
            raise ValueError(f"Unsupported file type: {ext}. Only image files ({', '.join(supported_image_extensions)}) and .txt files are supported.")

    @staticmethod
    def get_files_from_directory(directory_path: Union[str, Path],
                                recursive: bool = False) -> List[Path]:
        """
        Get all valid image or text files from a directory.

        Args:
            directory_path: Directory to scan for files
            recursive: Whether to scan subdirectories

        Returns:
            List of file paths
        """
        directory_path = Path(directory_path)
        if not directory_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory_path}")

        supported_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.txt']
        pattern = "**/*" if recursive else "*"
        files = [
            f for f in directory_path.glob(pattern)
            if f.is_file() and f.suffix.lower() in supported_extensions
        ]
        if not files:
            logger.warning(f"No supported files found in {directory_path}{' recursively' if recursive else ''}.")

        return files