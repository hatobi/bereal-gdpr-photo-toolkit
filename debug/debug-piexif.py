import piexif

def update_image_description(image_path, description):
    try:
        # Attempt to load existing EXIF data from the image
        exif_dict = piexif.load(image_path)

        # Ensure the '0th' directory is initialized
        if '0th' not in exif_dict:
            exif_dict['0th'] = {}

        # Update the ImageDescription field
        exif_dict['0th'][piexif.ImageIFD.ImageDescription] = description.encode('utf-8')

        # Dump the updated EXIF data to bytes and insert back into the image
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path)

        # Log success
        print(f"Updated image description for {image_path}.")
    except Exception as e:
        # Log any errors encountered during the process
        print(f"Failed to update image description for {image_path}: {e}")

# Specify the path to your image and the description to add
image_path = 'path-to-image.jpg'  # Update this to the actual image path
description = "Test caption"

# Call the function with your image and desired description
update_image_description(image_path, description)

# Verify the update by reloading and printing the EXIF data
try:
    exif_dict = piexif.load(image_path)
    image_description = exif_dict['0th'].get(piexif.ImageIFD.ImageDescription, b'').decode('utf-8')
    print(f"Image description: {image_description}")
except Exception as e:
    print(f"Error reading EXIF data: {e}")
