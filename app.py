"""
YouTube Downloader Web App (single-file Flask app)

Features:
- User pastes a YouTube URL
- Choose MP3 or MP4
- If MP4 chosen, choose a resolution (e.g. 360, 720, 1080) based on available formats
- Server downloads the requested file into a temporary directory and sends it to the user's browser
- Temporary files are cleaned up automatically

Notes & requirements:
- Python 3.8+
- pip install flask yt-dlp
- ffmpeg must be installed on the server if converting to mp3 (yt-dlp uses ffmpeg)

Run:
    python yt_downloader_app.py

Then open: http://127.0.0.1:5000

LEGAL: Only download content you own or have permission to download. Follow YouTube's Terms of Service and copyright law.
"""

from flask import Flask, request, render_template_string, jsonify, send_file, abort
import yt_dlp
import tempfile
import shutil
import os
import pathlib
import threading
import time

app = Flask(__name__)

# ---------- Simple HTML frontend ----------
INDEX_HTML = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>HUN73R DOWNLOAD MANAGER</title>
  <style>
    :root {
      --primary: #ff0000;
      --primary-dark: #cc0000;
      --secondary: #065fd4;
      --dark: #202124;
      --light: #f8f9fa;
      --gray: #5f6368;
      --border: #dadce0;
      --shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    }
    body {
      font-family: 'Segoe UI', Roboto, Arial, sans-serif;
      max-width: 900px;
      margin: 40px auto;
      padding: 0 20px;
      background-color: #f5f5f5;
      color: var(--dark);
    }
    .container {
      background-color: white;
      border-radius: 12px;
      box-shadow: var(--shadow);
      padding: 30px;
      margin-bottom: 30px;
    }
    h1 { color: var(--primary); }
    .muted {
      color: var(--gray);
      margin-bottom: 30px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
    }
    input, select {
      width: 100%; padding: 12px; margin: 8px 0;
      border: 1px solid var(--border); border-radius: 8px;
    }
    button {
      padding: 12px; border-radius: 8px; cursor: pointer; border: none;
    }
    #fetch-btn { background: white; border: 1px solid var(--secondary); color: var(--secondary); }
    #download-btn { background: var(--primary); color: white; }
    #status { margin-top: 20px; padding: 12px; border-radius: 8px; }
    .status-info { background: rgba(6,95,212,0.1); }
    .status-success { background: rgba(52,168,83,0.1); }
    .status-error { background: rgba(234,67,53,0.1); }
  </style>
</head>
<body>
  <div class="container">
    <h1>HUN73R DOWNLOAD MANAGER</h1>
    <p class="muted">Paste a link, choose <strong>MP3</strong> or <strong>MP4</strong>. Pick a resolution, then download.</p>

    <form id="download-form" method="POST" action="/download">
      <label>YouTube URL</label>
      <input id="url" name="url" type="text" placeholder="https://www.youtube.com/watch?v=...">

      <label>Format</label>
      <select id="format" name="format">
        <option value="mp4">MP4</option>
        <option value="mp3">MP3</option>
      </select>

      <div id="mp4-options">
        <label>Resolution</label>
        <select id="resolution" name="resolution">
          <option value="best">Best</option>
        </select>
      </div>

      <button id="fetch-btn" type="button">Fetch available qualities</button>
      <button id="download-btn" type="submit">Download</button>
    </form>

    <div id="status" class="status-info"></div>
  </div>

<script>
const urlInput = document.getElementById('url');
const fetchBtn = document.getElementById('fetch-btn');
const formatSelect = document.getElementById('format');
const mp4Options = document.getElementById('mp4-options');
const resolutionSelect = document.getElementById('resolution');
const statusDiv = document.getElementById('status');

formatSelect.addEventListener('change', ()=>{
  mp4Options.style.display = (formatSelect.value === 'mp3') ? 'none' : 'block';
});

fetchBtn.addEventListener('click', async ()=>{
  const url = urlInput.value.trim();
  if(!url){ statusDiv.innerText="Enter URL"; statusDiv.className="status-error"; return; }

  statusDiv.innerText="Fetching...";
  statusDiv.className="status-info";

  try{
    const resp = await fetch('/formats?url=' + encodeURIComponent(url));
    if(!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();

    resolutionSelect.innerHTML = '<option value="best">Best</option>';
    data.resolutions.forEach(r=>{
      const opt=document.createElement('option');
      opt.value=r; opt.text=r+"p";
      resolutionSelect.appendChild(opt);
    });

    statusDiv.innerText="Qualities loaded.";
    statusDiv.className="status-success";

  }catch(err){
    statusDiv.innerText="Error: "+err.message;
    statusDiv.className="status-error";
  }
});
</script>
</body>
</html>
'''

# ---------- Helpers with extractor_args ----------

EXTRACTOR_ARGS = {
    'youtubetab': {
        'skip': ['webpage']
    },
    'youtube': {
        'player_skip': ['webpage', 'configs'],
        'visitor_data': ['Cgtsd3ZzSU1XRlUtbyjv4biBCg=='],
        'client': ['android', 'web']
    }
}


def extract_video_resolutions(url):
    """Return available video heights."""
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': EXTRACTOR_ARGS
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise RuntimeError(f'Failed to extract video info: {e}')

    heights = []
    for f in info.get('formats', []):
        if f.get('height'): heights.append(int(f['height']))
    return sorted(set(heights), reverse=True)


def download_video_to_temp(url, want_format='mp4', resolution='best'):
    tempdir = tempfile.mkdtemp(prefix='yt_dl_')
    outtmpl = os.path.join(tempdir, '%(title).200s.%(ext)s')

    if want_format == 'mp3':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': EXTRACTOR_ARGS,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        }
    else:
        if resolution == 'best':
            format_selector = 'bestvideo+bestaudio/best'
        else:
            format_selector = f"bestvideo[height<={resolution}]+bestaudio"

        ydl_opts = {
            'format': format_selector,
            'merge_output_format': 'mp4',
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': EXTRACTOR_ARGS
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if want_format == 'mp3':
                filename = os.path.splitext(filename)[0] + '.mp3'
    except Exception as e:
        shutil.rmtree(tempdir)
        raise RuntimeError(f'Download failed: {e}')

    if not os.path.exists(filename):
        files = list(pathlib.Path(tempdir).glob('*'))
        if not files:
            shutil.rmtree(tempdir)
            raise RuntimeError('No output file produced')
        filename = str(files[0])

    return tempdir, filename


# ---------- Routes ----------

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)


@app.route('/formats')
def formats():
    url = request.args.get('url')
    if not url:
        return 'Missing url', 400
    try:
        resolutions = extract_video_resolutions(url)
        return jsonify({'resolutions': resolutions})
    except Exception as e:
        return str(e), 400


@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    fmt = request.form.get('format')
    resolution = request.form.get('resolution', 'best')

    if not url:
        abort(400, 'Missing URL')

    if fmt not in ('mp3', 'mp4'):
        abort(400, 'Invalid format')

    if resolution != 'best':
        try: resolution = int(resolution)
        except: resolution = 'best'

    try:
        tempdir, filepath = download_video_to_temp(url, want_format=fmt, resolution=resolution)
    except Exception as e:
        return f'Error: {e}', 500

    abs_path = os.path.abspath(filepath)

    def cleanup_later(dirpath):
        time.sleep(15)
        shutil.rmtree(dirpath, ignore_errors=True)

    threading.Thread(target=cleanup_later, args=(tempdir,), daemon=True).start()

    return send_file(abs_path, as_attachment=True)


# ---------- Run server ----------

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    app.run(host='0.0.0.0', port=port, debug=True)
