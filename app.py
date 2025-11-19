import os
from flask import Flask, request, send_file, render_template_string
import yt_dlp
import tempfile

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>YT Downloader</title>
</head>
<body>
    <h2>YouTube Downloader (MP3 / MP4)</h2>
    <form method="POST">
        <input type="text" name="url" placeholder="Enter YouTube URL" size="50" required><br><br>

        <label>Select Format:</label>
        <select name="format">
            <option value="mp4">MP4 (Video)</option>
            <option value="mp3">MP3 (Audio)</option>
        </select><br><br>

        <label>Video Quality (MP4 only):</label>
        <select name="quality">
            <option value="best">Best</option>
            <option value="720">720p</option>
            <option value="480">480p</option>
            <option value="360">360p</option>
        </select><br><br>

        <button type="submit">Download</button>
    </form>
</body>
</html>
"""


def download_with_options(url, fmt, quality):
    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

    extractor_settings = {
        "youtubetab": {"skip": ["webpage"]},
        "youtube": {
            "player_skip": ["webpage", "configs"],
            "visitor_data": ["Cgtsd3ZzSU1XRlUtbyjv4biBCg=="],
            "client": ["android", "web"],
        }
    }

    if fmt == "mp3":
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "extractor_args": extractor_settings,
        }

    else:  # MP4
        if quality == "best":
            fmt_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
        else:
            fmt_str = f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/mp4"

        ydl_opts = {
            "format": fmt_str,
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "extractor_args": extractor_settings,
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        return filepath


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        fmt = request.form['format']
        quality = request.form.get('quality', 'best')

        filepath = download_with_options(url, fmt, quality)
        return send_file(filepath, as_attachment=True)

    return render_template_string(HTML_PAGE)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
