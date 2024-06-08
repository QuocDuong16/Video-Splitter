from flask import Flask, render_template, request, jsonify, send_from_directory
from threading import Thread
from flask_socketio import SocketIO
import os
from proglog import ProgressBarLogger
from moviepy.editor import VideoFileClip
import shutil  # Thêm thư viện shutil để thực hiện xóa thư mục và nội dung bên trong

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
        for (parameter, value) in changes.items():
            print ('Parameter %s is now %s' % (parameter, value))
    
    def bars_callback(self, bar, attr, value, old_value=None):
        percentage = (value / self.bars[bar]['total']) * 100
        if bar == 't' and attr == 'index':
            socketio.emit('update_progress', {'progress': percentage})
        print(bar, attr, percentage)

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

        # Sau khi tách video xong, tự động tải xuống thư mục OUTPUT_FOLDER
        shutil.make_archive(OUTPUT_FOLDER, 'zip', OUTPUT_FOLDER)

    except Exception as e:
        print(f"Error in split_video_task: {e}")
        socketio.emit('update_progress', {'error': str(e)})
    finally:
        # Xóa tất cả các tệp đã tạo trong thư mục TEMP_FOLDER
        for filename in os.listdir(TEMP_FOLDER):
            file_path = os.path.join(TEMP_FOLDER, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")

        # Xóa tất cả các tệp bên trong thư mục OUTPUT_FOLDER
        for filename in os.listdir(OUTPUT_FOLDER):
            file_path = os.path.join(OUTPUT_FOLDER, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")


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

        return jsonify({'success': True})

    return render_template('index.html')

# Thêm route để tải xuống thư mục OUTPUT_FOLDER
@app.route('/download', methods=['GET'])
def download():
    return send_from_directory(directory=OUTPUT_FOLDER, filename='output_videos.zip', as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
