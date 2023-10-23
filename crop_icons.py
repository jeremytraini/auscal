# Importing Image class from PIL module
from PIL import Image
import glob

names = glob.glob("weather-icons-night/*")

for name in names:
    # Opens a image in RGB mode
    im = Image.open(name)
    
    # Size of the image in pixels (size of original image)
    # (This is not mandatory)
    width, height = im.size
    
    # Setting the points for cropped image
    left = width/2
    top = 0
    right = width
    bottom = height
    
    # Cropped image of above dimension
    # (It will not change original image)
    im1 = im.crop((left, top, right, bottom))
    
    # Shows the image in image viewer
    im1.save(name)
