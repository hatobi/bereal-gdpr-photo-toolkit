from iptcinfo3 import IPTCInfo

# Load the image's IPTC data
info = IPTCInfo('/path/to/image.jpg')

# Set the "Caption-Abstract" tag
info['caption/abstract'] = 'Your caption here'

# Save changes
info.save()
