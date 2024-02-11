import piexif

def debug_update_exif(image_path):
    try:
        exif_dict = piexif.load(image_path)
        if 0 not in exif_dict:
            exif_dict[0] = {}
        exif_dict[0][piexif.ImageIFD.ImageDescription] = b"Debug caption"
        
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, image_path)
        print("EXIF update successful.")
    except KeyError as e:
        print(f"KeyError encountered: {e}")
    except Exception as e:
        print(f"General error encountered: {e}")

# Test the function with a known image path
debug_update_exif('path_to_your_image.jpg')
