import json
from datetime import datetime
from PIL import Image
import logging
from pathlib import Path
import piexif

# ANSI escape codes for text styling
COLORS = {
    "GREEN": "\033[92m",
    "RED": "\033[91m",
    "BLUE": "\033[94m",
    "BOLD": "\033[1m",
    "RESET": "\033[0m",
}

#Setup log styling
class ColorFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        if record.levelno == logging.INFO and "Finished processing" not in record.msg:
            message = COLORS["GREEN"] + message + COLORS["RESET"]
        elif record.levelno == logging.ERROR:
            message = COLORS["RED"] + message + COLORS["RESET"]
        elif "Finished processing" in record.msg:  # Identify the summary message
            message = COLORS["BLUE"] + COLORS["BOLD"] + message + COLORS["RESET"]
        return message

# Setup basic logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Setup logging with styling
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
handler = logger.handlers[0]  # Get the default handler installed by basicConfig
handler.setFormatter(ColorFormatter('%(asctime)s - %(levelname)s - %(message)s'))

# Initialize counters
processed_files_count = 0
converted_files_count = 0
skipped_files_count = 0

# Define paths using pathlib
photo_folder = Path('Photos/post/')
output_folder = Path('Photos/post/__processed')
output_folder.mkdir(parents=True, exist_ok=True)  # Create the output folder if it doesn't exist

# Log the paths
logging.info(f"Photo folder: {photo_folder}")
logging.info(f"Output folder: {output_folder}")
logging.info("Deduplication active. No files will be overwritten or deleted.")

# Function to convert WEBP to JPEG
def convert_webp_to_jpg(image_path):
    if image_path.suffix.lower() == '.webp':
        jpg_path = image_path.with_suffix('.jpg')
        try:
            with Image.open(image_path) as img:
                img.convert('RGB').save(jpg_path, "JPEG", quality=80)
                logging.info(f"Converted {image_path} to JPEG.")
            return jpg_path, True
        except Exception as e:
            logging.error(f"Error converting {image_path} to JPEG: {e}")
            return None, False
    else:
        return image_path, False

# Function to update EXIF data
def update_exif(image_path, datetime_original):
    try:
        exif_dict = piexif.load(image_path.as_posix())
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = datetime_original.strftime("%Y:%m:%d %H:%M:%S")
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path.as_posix())
    except Exception as e:
        logging.error(f"Failed to update EXIF data for {image_path}: {e}")

# Function to handle deduplication
def get_unique_filename(path):
    if not path.exists():
        return path
    else:
        prefix = path.stem
        suffix = path.suffix
        counter = 1
        while path.exists():
            path = path.with_name(f"{prefix}_{counter}{suffix}")
            counter += 1
        return path

# Load the JSON file
try:
    with open('posts.json') as f:
        data = json.load(f)
except FileNotFoundError:
    logging.error("JSON file not found. Please check the path.")
    exit()

# Process files
for entry in data:
    try:
        # Extract only the filename from the path and then append it to the photo_folder path
        primary_filename = Path(entry['primary']['path']).name
        secondary_filename = Path(entry['secondary']['path']).name
        
        primary_path = photo_folder / primary_filename
        secondary_path = photo_folder / secondary_filename

        taken_at = datetime.strptime(entry['takenAt'], "%Y-%m-%dT%H:%M:%S.%fZ")
        
        for path, role in [(primary_path, 'primary'), (secondary_path, 'secondary')]:
            # Convert WebP to JPEG if necessary
            converted_path, converted = convert_webp_to_jpg(path)
            if converted_path is None:
                skipped_files_count += 1
                continue  # Skip this file if conversion failed
            if converted:
                converted_files_count += 1
            
            original_filename = converted_path.name
            new_filename = taken_at.strftime("%Y-%m-%d_") + f"{role}_" + original_filename
            new_path = output_folder / new_filename
            new_path = get_unique_filename(new_path)  # Ensure the filename is unique
            
            converted_path.rename(new_path)  # Move and rename the file
            update_exif(new_path, taken_at)  # Update EXIF data
            
            logging.info(f"Processed {role} image: {new_path}")
            processed_files_count += 1
    
    except Exception as e:
        logging.error(f"Error processing entry {entry}: {e}")

# Summary
logging.info(f"Finished processing. Total files processed: {processed_files_count}. Files converted: {converted_files_count}. Files skipped: {skipped_files_count}.")