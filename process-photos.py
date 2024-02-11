import json
from datetime import datetime
from PIL import Image, ImageDraw, ImageOps, ExifTags
import logging
from pathlib import Path
import piexif
import os
import time
import shutil
from iptcinfo3 import IPTCInfo

# ANSI escape codes for text styling
STYLING = {
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
            message = STYLING["GREEN"] + message + STYLING["RESET"]
        elif record.levelno == logging.ERROR:
            message = STYLING["RED"] + message + STYLING["RESET"]
        elif "Finished processing" in record.msg:  # Identify the summary message
            message = STYLING["BLUE"] + STYLING["BOLD"] + message + STYLING["RESET"]
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
combined_files_count = 0
skipped_files_count = 0

# Static IPTC tags
source_app = "BeReal app"
processing_tool = "github/bereal-gdpr-photo-toolkit"
keywords = ["BeReal"]

# Define lists to hold the paths of images to be combined
primary_images = []
secondary_images = []

# Define paths using pathlib
photo_folder = Path('Photos/post/')
output_folder = Path('Photos/post/__processed')
output_folder_combined = Path('Photos/post/__combined')
output_folder.mkdir(parents=True, exist_ok=True)  # Create the output folder if it doesn't exist

# Print the paths
print(STYLING["BOLD"] + "\nThe following paths are set for the input and output files:" + STYLING["RESET"])
print(f"Photo folder: {photo_folder}")
print(f"Output folder for singular images: {output_folder}")
print(f"Output folder for combined images: {output_folder_combined}")
#print("\nDeduplication is active. No files will be overwritten or deleted.")
print("")

# Function to count number of input files
def count_files_in_folder(folder_path):
    folder = Path(folder_path)
    file_count = len(list(folder.glob('*.webp')))
    return file_count

number_of_files = count_files_in_folder(photo_folder)
print(f"Number of WebP-files in {photo_folder}: {number_of_files}")

# Settings
## Initial choice for accessing advanced settings
print(STYLING["BOLD"] + "\nDo you want to access advanced settings or run with default settings?" + STYLING["RESET"])
print("Default settings are:\n"
"1. Copied images are converted from WebP to JPEG\n"
"2. Converted images' filenames do not contain the original filename\n"
"3. Combined images are created on top of converted, singular images")
advanced_settings = input("\nEnter " + STYLING["BOLD"] + "'yes'" + STYLING["RESET"] + "for advanced settings or press any key to continue with default settings: ").strip().lower()

if advanced_settings != 'yes':
    print("Continuing with default settings.\n")

## Default responses
convert_to_jpeg = 'yes'
keep_original_filename = 'no'
create_combined_images = 'yes'

## Proceed with advanced settings if chosen
if advanced_settings == 'yes':
    # User choice for converting to JPEG
    convert_to_jpeg = None
    while convert_to_jpeg not in ['yes', 'no']:
        convert_to_jpeg = input(STYLING["BOLD"] + "\n1. Do you want to convert images from WebP to JPEG? (yes/no): " + STYLING["RESET"]).strip().lower()
        if convert_to_jpeg == 'no':
            print("Your images will not be converted. No additional metadata will be added.")
        if convert_to_jpeg not in ['yes', 'no']:
            logging.error("Invalid input. Please enter 'yes' or 'no'.")

    # User choice for keeping original filename
    print(STYLING["BOLD"] + "\n2. There are two options for how output files can be named" + STYLING["RESET"] + "\n"
    "Option 1: YYYY-MM-DDTHH-MM-SS_primary/secondary_original-filename.jpeg\n"
    "Option 2: YYYY-MM-DDTHH-MM-SS_primary/secondary.jpeg\n"
    "This will only influence the naming scheme of singular images.")
    keep_original_filename = None
    while keep_original_filename not in ['yes', 'no']:
        keep_original_filename = input(STYLING["BOLD"] + "Do you want to keep the original filename in the renamed file? (yes/no): " + STYLING["RESET"]).strip().lower()
        if keep_original_filename not in ['yes', 'no']:
            logging.error("Invalid input. Please enter 'yes' or 'no'.")

    # User choice for creating combined images
    create_combined_images = None
    while create_combined_images not in ['yes', 'no']:
        create_combined_images = input(STYLING["BOLD"] + "\n3. Do you want to create combined images like the original BeReal memories? (yes/no): " + STYLING["RESET"]).strip().lower()
        if create_combined_images not in ['yes', 'no']:
            logging.error("Invalid input. Please enter 'yes' or 'no'.")

if convert_to_jpeg == 'no' and create_combined_images == 'no':
    print("You chose not to convert images nor do you want to output combined images.\n"
    "The script will therefore only copy images to a new folder and rename them according to your choice without adding metadata or creating new files.\n"
    "Script will continue to run in 5 seconds.")
    #time.sleep(10)

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

# Helper function to convert latitude and longitude to EXIF-friendly format
def _convert_to_degrees(value):
    """Convert decimal latitude / longitude to degrees, minutes, seconds (DMS)"""
    d = int(value)
    m = int((value - d) * 60)
    s = (value - d - m/60) * 3600.00

    # Convert to tuples of (numerator, denominator)
    d = (d, 1)
    m = (m, 1)
    s = (int(s * 100), 100)  # Assuming 2 decimal places for seconds for precision

    return (d, m, s)

# Function to update EXIF data
def update_exif(image_path, datetime_original, location=None, caption=None):
    try:
        exif_dict = piexif.load(image_path.as_posix())

        # Ensure the '0th' and 'Exif' directories are initialized
        if '0th' not in exif_dict:
            exif_dict['0th'] = {}
        if 'Exif' not in exif_dict:
            exif_dict['Exif'] = {}

        # For debugging: Load and log the updated EXIF data
        #logging.info(f"Original EXIF data for {image_path}: {exif_dict}")

        # Update datetime original
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = datetime_original.strftime("%Y:%m:%d %H:%M:%S")
        datetime_print = datetime_original.strftime("%Y:%m:%d %H:%M:%S")
        logging.info(f"Found datetime: {datetime_print}")
        logging.info(f"Added capture date and time.")

        # Update GPS information if location is provided
        if location and 'latitude' in location and 'longitude' in location:
            logging.info(f"Found location: {location}")
            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: 'N' if location['latitude'] >= 0 else 'S',
                piexif.GPSIFD.GPSLatitude: _convert_to_degrees(abs(location['latitude'])),
                piexif.GPSIFD.GPSLongitudeRef: 'E' if location['longitude'] >= 0 else 'W',
                piexif.GPSIFD.GPSLongitude: _convert_to_degrees(abs(location['longitude'])),
            }
            exif_dict['GPS'] = gps_ifd
            logging.info(f"Added GPS location: {gps_ifd}")

        # Transfer caption as title in ImageDescription
        if caption:
            logging.info(f"Found caption: {caption}")
            #exif_dict[piexif.ImageIFD.ImageDescription] = caption.encode('utf-8')
            exif_dict['0th'][piexif.ImageIFD.ImageDescription] = caption.encode('utf-8')
            logging.info(f"Updated title with caption.")

        
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path.as_posix())
        logging.info(f"Updated EXIF data for {image_path}.")

        # For debugging: Load and log the updated EXIF data
        #updated_exif_dict = piexif.load(image_path.as_posix())
        #logging.info(f"Updated EXIF data for {image_path}: {updated_exif_dict}")
        
    except Exception as e:
        logging.error(f"Failed to update EXIF data for {image_path}: {e}")

# Function to update IPTC information
def update_iptc(image_path, caption):
    try:
        # Load the IPTC data from the image
        info = IPTCInfo(image_path, force=True)  # Use force=True to create IPTC data if it doesn't exist
        
        # Check for errors (known issue with iptcinfo3 creating _markers attribute error)
        if not hasattr(info, '_markers'):
            info._markers = []
        
        # Update the "Caption-Abstract" field
        if caption:
            info['caption/abstract'] = caption
            logging.info(f"Caption added to converted image.")

        # Add static IPTC tags and keywords
        info['source'] = source_app
        info['originating program'] = processing_tool

        # Save the changes back to the image
        info.save_as(image_path)
        logging.info(f"Updated IPTC Caption-Abstract for {image_path}")
    except Exception as e:
        logging.error(f"Failed to update IPTC Caption-Abstract for {image_path}: {e}")


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

def combine_images_with_resizing(primary_path, secondary_path):
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

# Function to clean up backup files left behind by iptcinfo3
def remove_backup_files(directory):
    # List all files in the given directory
    for filename in os.listdir(directory):
        # Check if the filename ends with '~'
        if filename.endswith('~'):
            # Construct the full path to the file
            file_path = os.path.join(directory, filename)
            try:
                # Remove the file
                os.remove(file_path)
                print(f"Removed backup file: {file_path}")
            except Exception as e:
                print(f"Failed to remove backup file {file_path}: {e}")

# Load the JSON file
try:
    with open('posts.json', encoding="utf8") as f:
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
        location = entry.get('location')  # This will be None if 'location' is not present
        caption = entry.get('caption')  # This will be None if 'caption' is not present

        
        for path, role in [(primary_path, 'primary'), (secondary_path, 'secondary')]:
            logging.info(f"Found image: {path}")
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
            original_filename_without_extension = Path(path).stem  # Extract original filename without extension
            
            if convert_to_jpeg == 'yes':
                if keep_original_filename == 'yes':
                    new_filename = f"{time_str}_{role}_{converted_path.name}"
                else:
                    new_filename = f"{time_str}_{role}.jpg"
            else:
                if keep_original_filename == 'yes':
                    new_filename = f"{time_str}_{role}_{original_filename_without_extension}.webp"
                else:
                    new_filename = f"{time_str}_{role}.webp"
            
            new_path = output_folder / new_filename
            new_path = get_unique_filename(new_path)  # Ensure the filename is unique
            
            if convert_to_jpeg == 'yes' and converted:
                converted_path.rename(new_path)  # Move and rename the file

                # Update EXIF and IPTC data
                update_exif(new_path, taken_at, location, caption)                
                logging.info(f"EXIF data added to converted image.")

                image_path_str = str(new_path)
                update_iptc(image_path_str, caption)
            else:
                shutil.copy2(path, new_path) # Copy to new path

            if role == 'primary':
                primary_images.append({
                    'path': new_path,
                    'taken_at': taken_at,
                    'location': location,
                    'caption': caption
                })
            else:
                secondary_images.append(new_path)

            logging.info(f"Sucessfully processed {role} image.")
            processed_files_count += 1
            print("")
    except Exception as e:
        logging.error(f"Error processing entry {entry}: {e}")

# Create combined images if user chose 'yes'
if create_combined_images == 'yes':
    #Create output folder if it doesn't exist
    output_folder_combined.mkdir(parents=True, exist_ok=True)

    for primary_path, secondary_path in zip(primary_images, secondary_images):
        # Extract metadata from one of the images for consistency
        #taken_at = datetime.strptime(timestamp, "%Y-%m-%dT%H-%M-%S")
        primary_new_path = primary_path['path']
        primary_taken_at = primary_path['taken_at']
        primary_location = primary_path['location']
        primary_caption = primary_path['caption']

        timestamp = primary_new_path.stem.split('_')[0]

        # Construct the new file name for the combined image
        combined_filename = f"{timestamp}_combined.webp"
        combined_image = combine_images_with_resizing(primary_new_path, secondary_path)
        
        combined_image_path = output_folder_combined / (combined_filename)
        combined_image.save(combined_image_path, 'JPEG')
        combined_files_count += 1

        logging.info(f"Combined image saved: {combined_image_path}")

        update_exif(combined_image_path, primary_taken_at, primary_location, primary_caption)
        logging.info(f"Metadata added to combined image.")

        image_path_str = str(combined_image_path)
        update_iptc(image_path_str, primary_caption)

        if convert_to_jpeg == 'yes':
            # Convert WebP to JPEG if necessary
            converted_path, converted = convert_webp_to_jpg(combined_image_path)
            update_exif(converted_path, primary_taken_at, primary_location, primary_caption)
            logging.info(f"Metadata added to converted image.")
            image_path_str = str(combined_image_path)
            update_iptc(image_path_str, primary_caption)

            if converted_path is None:
                logging.error(f"Failed to convert combined image to JPEG: {combined_image_path}")
        print("")

# Clean up backup files
print(STYLING['BOLD'] + "Removing backup files left behind by iptcinfo3" + STYLING["RESET"])
remove_backup_files(output_folder)
remove_backup_files(output_folder_combined)
print("")

# Summary
logging.info(f"Finished processing.\nNumber of input-files: {number_of_files}\nTotal files processed: {processed_files_count}\nFiles converted: {converted_files_count}\nFiles skipped: {skipped_files_count}\nFiles combined: {combined_files_count}")