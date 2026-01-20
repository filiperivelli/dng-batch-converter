#!/usr/bin/env python3
"""
Adobe DNG Converter Batch Automation Script.

This script reads a list of directories from a text file, iterates through them,
and converts RAW images (CR2, CR3) to DNG format using the Adobe DNG Converter CLI.
It features:
- Lossy compression and Fast Load Data embedding.
- Automatic fallback: Copies original RAW file if conversion fails.
- Anti-collision naming: Auto-renames files to avoid overwriting.
- localized logging: Saves logs inside the destination folder.

Author: [Your Name/GitHub Username]
License: MIT (or your preferred license)
"""

import os
import sys
import subprocess
import platform
import logging
import shutil
from pathlib import Path
import argparse
from typing import List, Tuple, Optional

# --- Configuration Constants ---
# Supported RAW extensions (case-insensitive)
SUPPORTED_EXTENSIONS = {'.cr2', '.cr3'}

# Adobe DNG Converter arguments
# -lossy: Enable lossy compression (smaller file size)
# -fl: Embed Fast Load data for Lightroom performance
ADOBE_ARGS = ["-lossy", "-fl"]

# Name of the output folder and log file
OUTPUT_DIR_NAME = "DNG"
LOG_FILENAME = "conversion_log.txt"

def setup_logger(dest_folder: Path) -> bool:
    """
    Configures the logging system to write to a file INSIDE the destination folder.
    """
    log_file_path = dest_folder / LOG_FILENAME
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear previous handlers to avoid mixing logs between different folders
    if logger.hasHandlers():
        logger.handlers.clear()

    # Format: Date Time - Level - Message
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    try:
        # File Handler (Writes to the DNG folder)
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8', mode='w')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not create log file in {dest_folder}: {e}")
        return False

    # Console Handler (Prints to screen)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return True

def find_adobe_executable() -> str:
    """
    Locates the Adobe DNG Converter executable based on the OS.
    Checks environment variable 'ADOBE_DNG_PATH' first.
    """
    # 1. Check if user defined a custom path in Environment Variables
    env_path = os.environ.get("ADOBE_DNG_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return str(path)

    # 2. Check standard installation paths
    system_os = platform.system()
    if system_os == "Windows":
        path = Path(r"C:\Program Files\Adobe\Adobe DNG Converter\Adobe DNG Converter.exe")
    elif system_os == "Darwin": # macOS
        path = Path("/Applications/Adobe DNG Converter.app/Contents/MacOS/Adobe DNG Converter")
    else:
        sys.exit(f"Unsupported Operating System: {system_os}")

    if not path.exists():
        print(f"CRITICAL ERROR: Adobe DNG Converter not found at: {path}")
        print("Please install it or set the 'ADOBE_DNG_PATH' environment variable.")
        sys.exit(1)
        
    return str(path)

def generate_unique_path(dest_folder: Path, base_name: str, extension: str) -> Tuple[str, Path, int]:
    """
    Generates a unique filename to prevent overwriting existing files.
    Returns: (filename_string, full_path_object, duplicate_counter)
    """
    counter = 0
    if not extension.startswith('.'):
        extension = '.' + extension
        
    filename = f"{base_name}{extension}"
    file_path = dest_folder / filename

    while file_path.exists():
        counter += 1
        filename = f"{base_name}_{counter}{extension}"
        file_path = dest_folder / filename
    
    return filename, file_path, counter

def process_single_folder(source_path_str: str, adobe_exe: str) -> None:
    """
    Process a single directory: Convert RAWs to DNG or copy original on failure.
    """
    source_path = Path(source_path_str).resolve()
    
    if not source_path.exists() or not source_path.is_dir():
        print(f"SKIPPING: Invalid directory path: {source_path}")
        return

    # 1. Create Output Directory
    dest_path = source_path / OUTPUT_DIR_NAME
    try:
        dest_path.mkdir(exist_ok=True)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not create output directory at {source_path}. Error: {e}")
        return

    # 2. Setup Logging inside the output directory
    if not setup_logger(dest_path):
        return

    logging.info(f"Started processing. Log saved to: {dest_path}")
    
    # --- LOG THE COMMAND TEMPLATE (Requested Feature) ---
    command_template = f"{os.path.basename(adobe_exe)} {' '.join(ADOBE_ARGS)} -d \"{dest_path}\" -o [OUTPUT_NAME] [INPUT_FILE]"
    logging.info(f"Batch Conversion Command Template: {command_template}")
    # ----------------------------------------------------

    # 3. Find Files
    raw_files = [
        f for f in source_path.iterdir() 
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not raw_files:
        logging.warning("No supported RAW files found in this directory.")
        return

    logging.info(f"Found {len(raw_files)} RAW files to process.")

    stats = {'converted': 0, 'copied': 0, 'errors': 0}

    for i, raw_file in enumerate(raw_files, 1):
        # Prepare unique DNG output name
        dng_name, dng_path, idx = generate_unique_path(dest_path, raw_file.stem, ".dng")
        
        logging.info(f"[{i}/{len(raw_files)}] Processing: {raw_file.name}")
        
        if idx > 0:
            logging.warning(f"  -> Name collision detected. Saving as: {dng_name}")

        # Construct Command
        cmd = [
            adobe_exe,
            *ADOBE_ARGS,
            "-d", str(dest_path),
            "-o", dng_name,
            str(raw_file)
        ]

        try:
            # Execute Adobe DNG Converter
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Validation: Check if DNG was actually created
            if dng_path.exists():
                stats['converted'] += 1
            else:
                # --- FAILURE HANDLING: FALLBACK TO COPY ---
                error_msg = result.stderr
                logging.warning(f"  -> Conversion FAILED for {raw_file.name}.")
                
                # Filter out irrelevant GPU warnings from logs
                clean_errors = [line for line in error_msg.split('\n') if "GPU" not in line and line.strip()]
                if clean_errors:
                    logging.warning(f"     Adobe Error Details: {'; '.join(clean_errors)}")
                
                logging.info("  -> Attempting to COPY original file to output folder...")

                try:
                    # Generate unique name for the copy (in case the raw file already exists there)
                    copy_name, copy_dest, copy_idx = generate_unique_path(dest_path, raw_file.stem, raw_file.suffix)
                    
                    shutil.copy2(raw_file, copy_dest)
                    
                    if copy_idx > 0:
                        logging.info(f"  -> Original file copied with rename: {copy_name}")
                    else:
                        logging.info(f"  -> Original file copied successfully.")
                    
                    stats['copied'] += 1
                    
                except Exception as e_copy:
                    logging.error(f"  -> CRITICAL: Failed to convert AND failed to copy {raw_file.name}")
                    logging.error(f"     Copy Error: {e_copy}")
                    stats['errors'] += 1

        except Exception as e:
            logging.error(f"Fatal Python Error processing {raw_file.name}: {e}")
            stats['errors'] += 1

    logging.info("-" * 40)
    logging.info(f"SUMMARY: {stats['converted']} Converted (DNG) | {stats['copied']} Copied (Originals) | {stats['errors']} Total Failures")
    logging.info("=" * 40)

def main():
    parser = argparse.ArgumentParser(description="Batch converts RAW files to DNG using Adobe DNG Converter.")
    parser.add_argument("list_file", help="Path to the .txt file containing the list of directories to process.")
    args = parser.parse_args()
    
    list_path = Path(args.list_file)
    
    if not list_path.exists():
        print("Error: The provided list file does not exist.")
        sys.exit(1)

    adobe_exe = find_adobe_executable()
    
    print(f"Reading directory list from: {list_path.name}...\n")

    with open(list_path, 'r', encoding='utf-8') as f:
        folders = [line.strip() for line in f.readlines() if line.strip()]

    print(f"Total folders to process: {len(folders)}")
    print("-" * 30)

    for i, folder in enumerate(folders, 1):
        print(f"\n>>> Processing Folder {i}/{len(folders)}: {folder}")
        process_single_folder(folder, adobe_exe)

    print("\nBatch processing complete.")

if __name__ == "__main__":
    main()
