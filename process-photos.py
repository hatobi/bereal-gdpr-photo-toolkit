import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageOps
import logging
from pathlib import Path
import piexif
import os
import time
import shutil

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

# Settings
## Initial choice for accessing advanced settings
print(COLORS["BOLD"] + "Do you want to access advanced settings or run with default settings?" + COLORS["RESET"])
print("Default settings are:\n"
"1. Copied images are converted from WebP to JPEG\n"
"2. Converted images' filenames contain the original filename\n"
"3. Merged images are created on top of converted, singular images")
advanced_settings = input("Enter " + COLORS["BOLD"] + "'yes'" + COLORS["RESET"] + "for advanced settings or "  + COLORS["BOLD"] + "'no'" + COLORS["RESET"] + " to use default settings: " + COLORS["RESET"]).strip().lower()

## Default responses
convert_to_jpeg = 'yes'
keep_original_filename = 'yes'
create_merged_images = 'yes'

## Proceed with advanced settings if chosen
if advanced_settings == 'yes':
    # User choice for converting to JPEG
    convert_to_jpeg = None
    while convert_to_jpeg not in ['yes', 'no']:
        convert_to_jpeg = input(COLORS["BOLD"] + "\n1. Do you want to convert images from WebP to JPEG? (yes/no): " + COLORS["RESET"]).strip().lower()
        if convert_to_jpeg == 'no':
            print("Your images will not be converted. No additional metadata will be added.")
        if convert_to_jpeg not in ['yes', 'no']:
            logging.error("Invalid input. Please enter 'yes' or 'no'.")

    # User choice for keeping original filename
    print(COLORS["BOLD"] + "\n2. There are two options for how output files can be named" + COLORS["RESET"] + "\n"
    "Option 1: YYYY-MM-DDTHH-MM-SS_primary/secondary_original-filename.jpeg\n"
    "Option 2: YYYY-MM-DDTHH-MM-SS_primary/secondary.jpeg\n"
    "This will only influence the naming scheme of singular images.")
    keep_original_filename = None
    while keep_original_filename not in ['yes', 'no']:
        keep_original_filename = input(COLORS["BOLD"] + "Do you want to keep the original filename in the renamed file? (yes/no): " + COLORS["RESET"]).strip().lower()
        if keep_original_filename not in ['yes', 'no']:
            logging.error("Invalid input. Please enter 'yes' or 'no'.")

    # User choice for creating merged images
    create_merged_images = None
    while create_merged_images not in ['yes', 'no']:
        create_merged_images = input(COLORS["BOLD"] + "\n3. Do you want to create merged images like the original BeReal memories? (yes/no): " + COLORS["RESET"]).strip().lower()
        if create_merged_images not in ['yes', 'no']:
            logging.error("Invalid input. Please enter 'yes' or 'no'.")

if convert_to_jpeg == 'no' and create_merged_images == 'no':
    print("You chose not to convert images nor do you want to output merged images.\n"
    "The script will therefore only copy images to a new folder and rename them according to your choice without adding metadata or creating new files.\n"
    "Script will continue to run in 5 seconds.")
    #time.sleep(10)

# Initialize counters
processed_files_count = 0
converted_files_count = 0
merged_files_count = 0
skipped_files_count = 0

# Define paths using pathlib
photo_folder = Path('Photos/post/')
output_folder = Path('Photos/post/__processed')
output_folder_merged = Path('Photos/post/__merged')
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

def merge_images_with_resizing(primary_path, secondary_path):
    # Parameters for rounded corners, outline and position
    corner_radius = 60
    outline_size = 7
    position = (55, 55)

    # Load primary and secondary images
    primary_image = Image.open(primary_path)
    secondary_image = Image.open(secondary_path)

    # Resize the secondary image using LANCZOS resampling for better quality
    scaling_factor = 1/3.33333333  
    width, height = secondary_image.size
    new_width = int(width * scaling_factor)
    new_height = int(height * scaling_factor)
    resized_secondary_image = secondary_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Ensure secondary image has an alpha channel for transparency
    if resized_secondary_image.mode != 'RGBA':
        resized_secondary_image = resized_secondary_image.convert('RGBA')

    # Create mask for rounded corners
    mask = Image.new('L', (new_width, new_height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, new_width, new_height), corner_radius, fill=255)

    # Apply the rounded corners mask to the secondary image
    resized_secondary_image.putalpha(mask)

    # Create a new blank image with the size of the primary image
    combined_image = Image.new("RGB", primary_image.size)
    combined_image.paste(primary_image, (0, 0))    

    # Draw the black outline with rounded corners directly on the combined image
    outline_layer = Image.new('RGBA', combined_image.size, (0, 0, 0, 0))  # Transparent layer for drawing the outline
    draw = ImageDraw.Draw(outline_layer)
    outline_box = [position[0] - outline_size, position[1] - outline_size, position[0] + new_width + outline_size, position[1] + new_height + outline_size]
    draw.rounded_rectangle(outline_box, corner_radius + outline_size, fill=(0, 0, 0, 255))

    # Merge the outline layer with the combined image
    combined_image.paste(outline_layer, (0, 0), outline_layer)

    # Paste the secondary image onto the combined image using its alpha channel as the mask
    combined_image.paste(resized_secondary_image, position, resized_secondary_image)

    return combined_image

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
            # Check if conversion to JPEG is enabled by the user
            if convert_to_jpeg == 'yes':
                # Convert WebP to JPEG if necessary
                converted_path, converted = convert_webp_to_jpg(path)
                if converted_path is None:
                    skipped_files_count += 1
                    continue  # Skip this file if conversion failed
                if converted:
                    converted_files_count += 1

            # Adjust filename based on user's choice
            time_str = taken_at.strftime("%Y-%m-%dT%H-%M-%S")  # ISO standard format with '-' instead of ':' for time
            if convert_to_jpeg == 'yes':
                if keep_original_filename == 'yes':
                    new_filename = f"{time_str}_{role}_{converted_path.name}"
                else:
                    new_filename = f"{time_str}_{role}"
            else:
                if keep_original_filename == 'yes':
                    new_filename = f"{time_str}_{role}_{converted_path.name}.webp"
                else:
                    new_filename = f"{time_str}_{role}.webp"
            
            new_path = output_folder / new_filename
            new_path = get_unique_filename(new_path)  # Ensure the filename is unique
            
            if convert_to_jpeg == 'yes' and converted:
                converted_path.rename(new_path)  # Move and rename the file
                update_exif(new_path, taken_at)  # Update EXIF data if conversion took place
            else:
                shutil.copy2(path, new_path) # Copy to new path

            # Create merged images if user chose 'yes'
            if create_merged_images == 'yes':
                #Create output folder if it doesn't exist
                output_folder_merged.mkdir(parents=True, exist_ok=True)

                # Construct the new file name for the combined image
                combined_filename = taken_at.strftime("%Y-%m-%dT%H-%M-%S") + "_combined_" + os.path.basename(primary_path)
                combined_image = merge_images_with_resizing(primary_path, secondary_path)
        
                # Save the combined image
                #combined_image.save(os.path.join(output_folder_merged, combined_filename))
                
                combined_image_path = output_folder_merged / (combined_filename)
                combined_image.save(combined_image_path)
                merged_files_count += 1

                if convert_to_jpeg == 'yes':
                    # Convert WebP to JPEG if necessary
                    converted_path, converted = convert_webp_to_jpg(combined_image_path)
                    if converted_path is None:
                        logging.error(f"Failed to convert merged image to JPEG: {combined_image_path}")
                    else:
                        if converted:
                            logging.info(f"Converted merged image to JPEG: {converted_path}")

            logging.info(f"Processed {role} image: {new_path}")
            processed_files_count += 1
    
    except Exception as e:
        logging.error(f"Error processing entry {entry}: {e}")

# Summary
logging.info(f"Finished processing. Total files processed: {processed_files_count}. Files converted: {converted_files_count}. Files skipped: {skipped_files_count}.")