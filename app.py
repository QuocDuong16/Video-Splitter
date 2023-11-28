from flask import Flask, render_template, request, jsonify
from threading import Thread
from flask_socketio import SocketIO
import os
from proglog import ProgressBarLogger
from moviepy.editor import VideoFileClip

app = Flask(__name__)
socketio = SocketIO(app)

# Create folder
TEMP_FOLDER = os.path.join(os.path.dirname(__file__), 'temp_files')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), 'output_videos')

if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

class MyBarLogger(ProgressBarLogger):
    
    def callback(self, **changes):
        # Every time the logger message is updated, this function is called with
        # the `changes` dictionary of the form `parameter: new value`.
        for (parameter, value) in changes.items():
            print ('Parameter %s is now %s' % (parameter, value))
    
    def bars_callback(self, bar, attr, value, old_value=None):
        # Every time the logger progress is updated, this function is called        
        percentage = (value / self.bars[bar]['total']) * 100
        if bar == 't' and attr == 'index':
            socketio.emit('update_progress', {'progress': percentage})
        print(bar,attr,percentage)

# function split video
def split_video_task(temp_filepath, output_prefix, num_parts):
    try:
        print("split_video_task is called")
        output_filepath = os.path.join(OUTPUT_FOLDER, f'{output_prefix}_part_{{}}.mp4')
        clip = VideoFileClip(temp_filepath)
        duration = clip.duration
        part_duration = duration / num_parts

        for i in range(num_parts):
            socketio.emit('update_progress', {'title': f"Part {i + 1}"})
            start_time = i * part_duration
            end_time = (i + 1) * part_duration
            part_output_filepath = output_filepath.format(i + 1)

            logger = MyBarLogger()

            subclip = clip.subclip(start_time, end_time)
            subclip.write_videofile(part_output_filepath, codec="libx264", audio_codec="aac", logger=logger)
            

            socketio.emit('update_progress', {'progress': (i + 1) / num_parts})

        clip.close()
        socketio.emit('update_progress', {'progress': 1.0})
    except Exception as e:
        print(f"Error in split_video_task: {e}")
        socketio.emit('update_progress', {'error': str(e)})
    finally:
        os.remove(temp_filepath)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        input_file = request.files['input_file']
        output_prefix = request.form['output_prefix']
        num_parts = int(request.form['num_parts'])

        temp_filepath = os.path.join(TEMP_FOLDER, 'temp_input.mp4')
        input_file.save(temp_filepath)

        # Start a new thread to split the video
        thread = Thread(target=split_video_task, args=(temp_filepath, output_prefix, num_parts))
        thread.start()

        # Wait thread
        thread.join()
        return jsonify({'success': True})

    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True)
