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

# ---------- Simple HTML frontend as a template string ----------
INDEX_HTML = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>YHUN73R DOWNLOAD MANAGER</title>
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
    
    * {
      box-sizing: border-box;
    }
    
    body {
      font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      max-width: 900px;
      margin: 40px auto;
      padding: 0 20px;
      background-color: #f5f5f5;
      color: var(--dark);
      line-height: 1.6;
    }
    
    .container {
      background-color: white;
      border-radius: 12px;
      box-shadow: var(--shadow);
      padding: 30px;
      margin-bottom: 30px;
    }
    
    h1 {
      color: var(--primary);
      margin-top: 0;
      margin-bottom: 8px;
      font-size: 2.2rem;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    

    
    h1::after {
      content: "▶";
      color: white;
      position: absolute;
      font-size: 14px;
      margin-left: -30px;
    }
    
    .muted {
      color: var(--gray);
      font-size: 0.95rem;
      margin-bottom: 30px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
    }
    
    .form-group {
      margin-bottom: 24px;
    }
    
    label {
      display: block;
      margin-bottom: 8px;
      font-weight: 500;
      color: var(--dark);
    }
    
    input[type="text"] {
      width: 100%;
      padding: 12px 16px;
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 1rem;
      transition: all 0.2s;
    }
    
    input[type="text"]:focus {
      outline: none;
      border-color: var(--secondary);
      box-shadow: 0 0 0 2px rgba(6, 95, 212, 0.2);
    }
    
    select {
      width: 100%;
      padding: 12px 16px;
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 1rem;
      background-color: white;
      cursor: pointer;
      appearance: none;
      background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
      background-repeat: no-repeat;
      background-position: right 12px center;
      background-size: 16px;
    }
    
    select:focus {
      outline: none;
      border-color: var(--secondary);
      box-shadow: 0 0 0 2px rgba(6, 95, 212, 0.2);
    }
    
    .row {
      display: flex;
      gap: 12px;
      margin-top: 24px;
    }
    
    button {
      padding: 12px 24px;
      border: none;
      border-radius: 8px;
      font-size: 1rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    
    #fetch-btn {
      background-color: white;
      color: var(--secondary);
      border: 1px solid var(--secondary);
    }
    
    #fetch-btn:hover {
      background-color: rgba(6, 95, 212, 0.05);
    }
    
    #download-btn {
      background-color: var(--primary);
      color: white;
    }
    
    #download-btn:hover {
      background-color: var(--primary-dark);
    }
    
    #status {
      margin-top: 20px;
      padding: 16px;
      border-radius: 8px;
      font-size: 0.95rem;
      min-height: 54px;
    }
    
    .status-info {
      background-color: rgba(6, 95, 212, 0.1);
      color: var(--secondary);
      border-left: 4px solid var(--secondary);
    }
    
    .status-success {
      background-color: rgba(52, 168, 83, 0.1);
      color: #0d652d;
      border-left: 4px solid #34a853;
    }
    
    .status-error {
      background-color: rgba(234, 67, 53, 0.1);
      color: #c5221f;
      border-left: 4px solid #ea4335;
    }
    
    .hidden {
      display: none;
    }
    
    @media (max-width: 600px) {
      .row {
        flex-direction: column;
      }
      
      .container {
        padding: 20px;
      }
      
      h1 {
        font-size: 1.8rem;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>HUN73R DOWNLOAD MANAGER</h1>
    <p class="muted">Paste a link, choose <strong>MP3</strong> (audio) or <strong>MP4</strong> (video). If MP4, pick a resolution offered for that video. Files are temporarily stored on the server and then sent to your browser for download.</p>

    <form id="download-form" method="POST" action="/download">
      <div class="form-group">
        <label for="url">YouTube URL</label>
        <input id="url" name="url" type="text" placeholder="https://www.youtube.com/watch?v=..." required>
      </div>

      <div class="form-group">
        <label for="format">Format</label>
        <select id="format" name="format">
          <option value="mp4">MP4 (video)</option>
          <option value="mp3">MP3 (audio)</option>
        </select>
      </div>

      <div id="mp4-options" class="form-group">
        <label for="resolution">Resolution (will be populated from the video)</label>
        <select id="resolution" name="resolution">
          <option value="best">Best available</option>
        </select>
      </div>

      <div class="row">
        <button id="fetch-btn" type="button">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 6V9L16 5L12 1V4C7.58 4 4 7.58 4 12C4 13.57 4.46 15.03 5.3 16.26L6.7 14.86C6.05 13.89 5.66 12.74 5.66 11.5C5.66 8.42 8.09 6 11.17 6H12ZM18.7 7.74L17.3 9.14C17.95 10.11 18.34 11.26 18.34 12.5C18.34 15.58 15.91 18 12.83 18H12V15L8 19L12 23V20C16.42 20 20 16.42 20 12C20 10.43 19.54 8.97 18.7 7.74Z" fill="currentColor"/>
          </svg>
          Fetch available qualities
        </button>
        <button id="download-btn" type="submit">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M19 9H15V3H9V9H5L12 16L19 9ZM5 18V20H19V18H5Z" fill="currentColor"/>
          </svg>
          Download
        </button>
      </div>
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
  if(formatSelect.value === 'mp3') mp4Options.style.display = 'none';
  else mp4Options.style.display = 'block';
});

fetchBtn.addEventListener('click', async ()=>{
  const url = urlInput.value.trim();
  if(!url) { 
    statusDiv.innerText = 'Please enter a YouTube URL';
    statusDiv.className = 'status-error';
    return; 
  }
  
  statusDiv.innerText = 'Fetching available formats...';
  statusDiv.className = 'status-info';
  
  try{
    const resp = await fetch('/formats?url=' + encodeURIComponent(url));
    if(!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    
    // populate resolution select
    resolutionSelect.innerHTML = '';
    const best = document.createElement('option'); 
    best.value='best'; 
    best.text='Best available'; 
    resolutionSelect.appendChild(best);
    
    data.resolutions.forEach(r=>{
      const opt = document.createElement('option'); 
      opt.value = String(r); 
      opt.text = String(r) + 'p';
      resolutionSelect.appendChild(opt);
    });
    
    statusDiv.innerText = `Found ${data.resolutions.length} video resolutions. Select your preferred quality and click Download.`;
    statusDiv.className = 'status-success';
  } catch(err){
    statusDiv.innerText = 'Error: ' + err.message;
    statusDiv.className = 'status-error';
  }
});

// optional: show a status message when the form is submitted
const form = document.getElementById('download-form');
form.addEventListener('submit', ()=>{
  statusDiv.innerText = 'Preparing download — this may take a while depending on video size and conversion.';
  statusDiv.className = 'status-info';
});
</script>
</body>
</html>
'''

# ---------- Helpers ----------

def extract_video_resolutions(url, timeout=20):
    """Return a sorted list of available video heights (integers) for the given YouTube URL."""
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        # reduce the amount of network time by limiting extractors cache (if needed)
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise RuntimeError(f'Failed to extract video info: {e}')

    heights = set()
    formats = info.get('formats', [])
    for f in formats:
        # height may be None for audio-only streams
        h = f.get('height')
        if h:
            heights.add(int(h))
    # return sorted descending (higher first)
    return sorted(heights, reverse=True)


def download_video_to_temp(url, want_format='mp4', resolution='best'):
    """
    Downloads the video/audio into a temporary folder and returns the path to the resulting file.
    The caller is responsible for ensuring the returned file is cleaned up; however this helper
    will name files inside a TemporaryDirectory which can be removed easily.
    Returns (tempdir_path, filepath)
    """
    tempdir = tempfile.mkdtemp(prefix='yt_dl_')
    # safe outtmpl
    outtmpl = os.path.join(tempdir, '%(title).200s.%(ext)s')

    # Build yt-dlp options
    if want_format == 'mp3':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        }
    else:  # mp4/video
        # construct format selector — try to select video with requested height + best audio
        if resolution == 'best':
            format_selector = 'bestvideo+bestaudio/best'
        else:
            # limit height by <=requested and merge with best audio
            # this will choose the best video stream with height <= requested
            format_selector = f"bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]"
        ydl_opts = {
            'format': format_selector,
            'merge_output_format': 'mp4',
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # yt-dlp may produce multiple files (video+audio merged), but typically one file
            # Determine filename
            filename = ydl.prepare_filename(info)
            # if postprocessor changed extension (e.g., mp3 conversion), adjust
            if want_format == 'mp3':
                base = os.path.splitext(filename)[0]
                filename = base + '.mp3'
    except Exception as e:
        # cleanup on failure
        try:
            shutil.rmtree(tempdir)
        except Exception:
            pass
        raise RuntimeError(f'Download/conversion failed: {e}')

    # Ensure file exists
    if not os.path.exists(filename):
        # try to find any file in tempdir and return the first match
        files = list(pathlib.Path(tempdir).glob('*'))
        if files:
            filename = str(files[0])
        else:
            shutil.rmtree(tempdir)
            raise RuntimeError('No output file was produced')

    return tempdir, filename


# ---------- Routes ----------

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)


@app.route('/formats')
def formats():
    url = request.args.get('url')
    if not url:
        return 'Missing url parameter', 400
    try:
        resolutions = extract_video_resolutions(url)
    except Exception as e:
        return str(e), 400
    return jsonify({'resolutions': resolutions})


@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    fmt = request.form.get('format', 'mp4')
    resolution = request.form.get('resolution', 'best')

    if not url:
        abort(400, 'Missing url')

    # sanitize format
    if fmt not in ('mp3', 'mp4'):
        abort(400, 'Invalid format')

    # If resolution provided as string numeric, convert
    if resolution != 'best':
        try:
            resolution = int(resolution)
        except Exception:
            resolution = 'best'

    try:
        tempdir, filepath = download_video_to_temp(url, want_format=fmt, resolution=resolution)
    except Exception as e:
        return f'Error during download: {e}', 500

    # Send file as attachment. We will schedule cleanup of the tempdir after sending.
    # Flask's send_file will stream the file contents.
    try:
        # Use absolute path
        abs_path = os.path.abspath(filepath)
        # Create a background thread to remove tempdir after a short delay, ensuring send_file has started
        def cleanup_later(dirpath, delay=30):
            # wait to allow the response to be served
            time.sleep(delay)
            try:
                shutil.rmtree(dirpath)
            except Exception:
                pass
        threading.Thread(target=cleanup_later, args=(tempdir, 15), daemon=True).start()

        return send_file(abs_path, as_attachment=True)
    except Exception as e:
        # cleanup immediately on failure
        try:
            shutil.rmtree(tempdir)
        except Exception:
            pass
        return f'Failed to send file: {e}', 500


if __name__ == '__main__':
    app.run(debug=True)
