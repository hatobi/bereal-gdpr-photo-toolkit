# bereal-gdpr-photo-toolkit
When requesting your data from BeReal, you receive a ZIP with all photos in WebP format. These images don't contain metadata like when the image was taken. This information is contained in a JSON-file. This script automates the process of converting the images to JPEG as well as renaming and updating the EXIF data based on the JSON file.

# Prerequisites
## Request your data
Request your data according to Article 15 GDPR by using the in app chat. You can generate a template using [datarequests.org](https://www.datarequests.org/generator/).

## Install Python libraries
To run this script, you'll need Python installed on your system along with the following libraries:

- Pillow (PIL Fork)
- piexif

You can install these libraries using pip:

```
pip install Pillow piexif
```


# Running the Script
Before running the script, make sure you have the required files. Place the script in the same directory as the JSON file named posts.json.

To run the script, navigate to the directory containing the script:

```
cd path_to_unzipped_folder
```

Then execute it with Python:

```
python process-photos.py
```


# Data Requirement
The script processes images based on data provided in a JSON file obtained from BeReal. The JSON file should follow this format:

```
[
  {
    "primary": {
      "path": "/path/to/primary/image.webp",
      "other": "data"
    },
    "secondary": {
      "path": "/path/to/secondary/image.webp",
      "other": "data"
    },
    "takenAt": "YYYY-MM-DDTHH:MM:SS.sssZ",
    "other": "data"
  },
  ...
]
```