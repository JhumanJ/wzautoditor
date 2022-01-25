import logging
from moviepy.editor import *
import matplotlib.pyplot as plt
import pytesseract
from PIL import Image, ImageEnhance, ImageOps
from textdistance import levenshtein

FILE_PATH = '/Users/jhumanj/Desktop/rush.mp4'
OUTPUT_PATH = './output/'

def init_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler()
        ]
    )

def extract_feed(img_data):
    # Crop image, black and white and invert to read black text
    cropped_img = img_data[100:140, 1470:1740]
    im = Image.fromarray(cropped_img).convert('L')
    im = ImageOps.invert(im)
    return im


def show_frame(img_data):
    plt.imshow(img_data)
    plt.show()


# Setup logger
init_logging()

clip = VideoFileClip(FILE_PATH)

logging.info("Clip loaded, with a duration of: " + str(clip.duration))


def extract_kill_seconds(clip, plane_ended_second=1200, kills_at_plane_end=0):
    for i in range(plane_ended_second, round(clip.duration)):
        logging.info('Frame ' + str(i))

        for modif in [-0.4, -0.2, 0, 0.2, 0.4]:
            frame = clip.get_frame(i + modif)
            feed = extract_feed(frame)
            feedtext = pytesseract.image_to_string(feed).strip()

            if feedtext and levenshtein('Ennemi abattu', feedtext) < 6:
                logging.info('Found a kill!')


    return

kill_seconds = extract_kill_seconds(clip)

# result.write_videofile(OUTPUT_PATH + "output_1.mp4")
logging.info('Done.')
