import logging
from moviepy.editor import *
import matplotlib.pyplot as plt
import pytesseract
import unicodedata
import getopt, sys
from PIL import Image, ImageOps
from textdistance import levenshtein

OUTPUT_PATH = './output/'
output_file_name = 'output'


# TODO: detect uavs and advacned uavs
# TODO: detect gulag
# TODO: coequipier a terre, detect death and buy back at shop
# TODO: duplicated clips pendant les séries d'elimination

def init_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler()
        ]
    )


class WZAutoEditor(object):
    _clips = []
    _frame_actions = []
    _output_name = 'output'
    _players = []

    _end_clip_extra_time = 3
    _pre_clip_extra_time = 8

    def generate_video(self):
        self._parse_options_load_clips()
        for clip in self._clips:
            logging.info("Clip loaded, with a duration of: " + str(clip.duration))
            self._frame_actions.append(self._extract_kill_seconds(clip))
        clip_durations = self._compute_clip_durations()
        final_clip = self._render_video(clip_durations)
        final_clip.write_videofile(OUTPUT_PATH + output_file_name + ".mp4",
                                   codec='libx264',
                                   audio_codec='aac',
                                   temp_audiofile=OUTPUT_PATH + output_file_name + '.m4a',
                                   remove_temp=True,
                                   threads=16,
                                   logger=None
                                   )
        logging.info('Done.')

    def _parse_options_load_clips(self):
        global output_file_name
        if len(sys.argv) < 2:
            logging.error('Please precise file path.')
            logging.info('python3 main.py {file_path} -s {?start_time} -e {?end_time}')
            sys.exit(-1)

        clips = []
        file_paths = sys.argv[1].split(',')
        for path in file_paths:
            logging.info("Loading file from " + path)
            clips.append(VideoFileClip(path))

        arguments = getopt.getopt(sys.argv[2:], 's:e:o:p:')[0]
        start_times = None
        end_times = None

        # Parse options
        if len(arguments) > 0:
            for key, val in arguments:
                if key == '-s':
                    start_times = [int(number) for number in val.split(',')]
                elif key == '-e':
                    end_times = [int(number) for number in val.split(',')]
                elif key == '-o':
                    self._output_name = val
                elif key == '-p':
                    self._players = val.split(',')

        # Truncate clips
        final_clips = []
        for index, clip in enumerate(clips):
            if len(start_times) > index:
                start_time = start_times[index]
            else:
                start_time = None

            if len(end_times) > index:
                end_time = end_times[index]
            else:
                end_time = None

            if start_time and end_time:
                logging.info(
                    'Starting clip ' + str(index) + ' at second ' + str(start_time) + ' and ending it a second ' + str(
                        end_time))
                final_clips.append(clip.subclip(start_time, end_time))
            elif start_time[index]:
                logging.info('Starting clip at second ' + str(start_time))
                final_clips.append(clip.subclip(start_time, clip.duration))
            elif end_time:
                logging.info('Ending clip at second ' + str(start_time))
                final_clips.append(clip.subclip(0, end_time))
        del clips

        self._clips = final_clips

        if len(self._players) < len(self._clips):
            raise Exception('Please specify the user name of players in each clip using the option -p {player1},{player2}')
        return self

    def _extract_feed(self, img_data):
        # Crop image, black and white and invert to read black text
        cropped_img = img_data[100:140, 1470:1740]
        im = Image.fromarray(cropped_img).convert('L')
        im = ImageOps.invert(im)
        return im

    def _show_frame(self, img_data):
        plt.imshow(img_data)
        plt.show()

    def _text_read_is_kill(self, text):
        # Clean Text
        text = text.strip()
        text = ''.join((c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn'))

        if not text:
            return False

        # Check for different ATH labels
        if levenshtein('Ennemi abattu', text) < 6:
            return True
        for kill_count in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]:
            if levenshtein('Serie de ' + str(kill_count) + ' eliminationts) !', text) < 6:
                return True
        return False

    def _extract_kill_seconds(self, clip):
        frame_actions = {}
        for i in range(round(clip.duration)):

            for modif in [-0.4, -0.2, 0, 0.2, 0.4]:
                frame = clip.get_frame(i + modif)
                feed = self._extract_feed(frame)
                feedtext = pytesseract.image_to_string(feed)

                if self._text_read_is_kill(feedtext):
                    logging.info('Found a kill at second ' + str(i))
                    frame_actions[i] = 'kill'
                    break

            if i % 60 == 0:
                logging.info('Processing frame at second ' + str(i))

        return frame_actions

    def _compute_clip_durations(self):

        logging.info('Generating clip timestamps')
        all_clips_times = []
        pre_clip_extra_time = self._pre_clip_extra_time
        end_clip_extra_time = self._end_clip_extra_timez

        for index, clip in enumerate(self._clips):
            clips_times = []
            action_times = list(self._frame_actions[index].keys())
            current_clip = []
            for i in range(len(action_times)):
                current_time = action_times[i]
                if len(current_clip) == 0:
                    # Create new clip
                    current_clip.append(current_time)
                elif current_clip[-1] + (pre_clip_extra_time + end_clip_extra_time) >= current_time:
                    # Merge clips less than 20 sec aparts
                    current_clip.append(current_time)
                else:
                    # Save clip with 10 sec before and 5 sec after
                    clips_times.append([max(0, current_clip[0] - pre_clip_extra_time),
                                        min(current_clip[-1] + end_clip_extra_time, clip.duration)])
                    current_clip = [current_time]

            all_clips_times.append(clips_times)

        # Now for each videos we have x timelines of clips, we need to cut between them. Steps;
        # 1. serialize to get one sequence of subclips [clip_index, start_time, end_time]
        # 2. Find all overlaps
        # 3. Choose the best candidates(smaller overtime)
        # 4. add to final clip, compute overtime, add remaining sub_clips to queue (if len>5) (sort by start time)
        final_clip_times = []
        clips_queue = []
        for index, clip_times in enumerate(all_clips_times):
            for clip_time in clip_times:
                clips_queue.append([index, clip_time[0], clip_time[1]])

        clips_queue.sort(key=lambda x: x[1])
        # for index, clip in enumerate(clips_queue):
        #     # find overlapping clip
        #     overlapping_clips = [c for c in clips_queue if (c[1] <= clip[2] and c[1] >= clip[1]) or (c[2] >= clip[1] and c[1] <= clip[1])]
        #     overlapping_clips = [c for c in overlapping_clips if not (c[0] == clip[0] and c[1] == clip[1] and c[2] == clip[2])]
        #     print(clip, overlapping_clips)
        #
        #     if len(overlapping_clips) == 0:
        #         final_clip_times.append(clip)
        #     else:
        #         for overlap_clip in overlapping_clips:
        #
        #         pass

        # shorten overlapping clips
        for index, clip in enumerate(clips_queue):
            if index + 1 >= len(clips_queue):
                continue

            # When Overlap, reduce kill intro to 3
            if clip[2] < clips_queue[index + 1][1]:
                clip[2] = clip[2] - 1
                clips_queue[index + 1][1] = clips_queue[index + 1][1] + 5

        # take first 20 seconds
        if clips_queue[0][1] < 20:
            logging.info('Extending initial clip from start')
            clips_queue[0][1] = 0
        else:
            logging.info('Adding initial clip')
            clips_queue.insert(0, [clips_queue[0][0], 0, 20])

        # take last 35 seconds
        total_duration = self._clips[clips_queue[-1][0]].duration
        if clips_queue[-1][2] > total_duration - 35:
            logging.info('Extending final clip')
            clips_queue[-1][2] = total_duration
        else:
            logging.info('Adding final clip')
            clips_queue.append([clips_queue[-1][0], total_duration - 35, total_duration])

        return clips_queue

    def _render_video(self, clip_times):
        logging.info('Generating final video')
        final_clips = []
        for clip_time in clip_times:
            final_clips.append(self._clips[clip_time[0]].subclip(clip_time[1], clip_time[2]))
        return concatenate_videoclips(final_clips)


init_logging()
editor = WZAutoEditor()
editor.generate_video()
