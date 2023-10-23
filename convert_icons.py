import os
from PIL import Image
import base64

# Define the directory containing the PNG icons
directory = "weather-icons/"

# Initialize an empty dictionary to store the encoded icons
icon_dict = {}

# Loop through each file in the directory
for filename in os.listdir(directory):
    if filename.endswith(".png"):
        # Open the PNG file with PIL
        img = Image.open(os.path.join(directory, filename))

        # Convert the image to a byte array
        img_bytes = img.tobytes()

        # Encode the byte array as base64
        encoded_img = base64.b64encode(img_bytes).decode("utf-8")

        # Add the encoded image to the dictionary with the filename as the key
        icon_dict[filename] = encoded_img

# Print the dictionary
print(icon_dict)