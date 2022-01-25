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


def extract_kill_seconds(clip):
    frame_actions = {}
    for i in range(0, round(clip.duration)):

        for modif in [-0.4, -0.2, 0, 0.2, 0.4]:
            frame = clip.get_frame(i + modif)
            feed = extract_feed(frame)
            feedtext = pytesseract.image_to_string(feed).strip()

            if feedtext and levenshtein('Ennemi abattu', feedtext) < 6:
                logging.info('Found a kill at frame ' + str(i))
                frame_actions[i] = 'kill'
                break

    return frame_actions


def compute_clip_durations(clip, frame_actions):
    logging.info('Generating clip timestamps')
    clips_times = []
    action_times = list(frame_actions.keys())

    current_clip = []
    for i in range(len(action_times)):
        current_time = action_times[i]
        if len(current_clip) == 0:
            current_clip.append(current_time)
        # Merge clips less than 15 sec aparts
        elif current_clip[-1] + 15 >= current_time:
            current_clip.append(current_time)
        else:
            clips_times.append([max(0, current_clip[0] - 10), min(current_clip[-1] + 5, clip.duration)])
            current_clip = [current_time]

    # take first 30 seconds
    if clips_times[0][0] < 20:
        logging.info('Extending initial clip from start')
        clips_times[0][0] = 0
    else:
        logging.info('Adding initial clip')
        clips_times.insert(0, [0, 20])

    # take last minute
    if clips_times[-1][1] < clip.duration - 45:
        logging.info('Extending final clip')
        clips_times[-1][1] = clip.duration
    else:
        logging.info('Adding final clip')
        clips_times.append([clip.duration - 45, clip.duration])

    return clips_times


def generate_video(clip, clip_times):
    logging.info('Generating final video')
    clips = [clip.subclip(clip_time[0], clip_time[1]) for clip_time in clip_times]
    return concatenate_videoclips(clips)


frame_actions = extract_kill_seconds(clip)
clip_durations = compute_clip_durations(clip, frame_actions)
final_clip = generate_video(clip, clip_durations)
final_clip.write_videofile(OUTPUT_PATH + "output_withsound.mp4",
                           codec='libx264',
                           audio_codec='aac',
                           temp_audiofile='temp-audio.m4a',
                           remove_temp=True
                           )

logging.info('Done.')
