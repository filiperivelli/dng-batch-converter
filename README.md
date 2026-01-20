# Batch DNG Converter

A robust Python automation script for converting RAW images (CR2, CR3) to DNG format using the **Adobe DNG Converter** command-line interface.

## Features
- **Lossy Compression & Fast Load:** Reduces file size while maintaining flexibility.
- **Fail-Safe:** If conversion fails (e.g., AI/Depth Map errors), it automatically copies the original RAW file to the destination.
- **Collision Handling:** Automatically renames files (`file_1.dng`) to prevent overwriting.
- **Localized Logging:** Creates a detailed log file inside every processed folder.

## Requirements
- Python 3.6+
- [Adobe DNG Converter](https://helpx.adobe.com/camera-raw/digital-negative.html) installed.

## Usage
1. Create a `folders.txt` file listing the paths you want to process:
   ```text
   C:\Photos\Trip_2024
   C:\Photos\Wedding_Shoot
