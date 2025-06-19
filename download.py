import os
import re
import sys
import requests
from flask import Flask, request, jsonify
from redis import Redis
from rq import Queue
from jobs import Session, Download, download_audio_job

# --- CONFIG ---
YT_DLP_PATH = "/usr/local/bin/yt-dlp"
TEMP_DIR = "/tmp/yt-downloads"
ZING_PROXY_TOKEN = os.getenv("ZING_PROXY_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")


# --- FLASK APP ---
app = Flask(__name__)
# q = Queue(connection=Redis())
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
q = Queue(connection=Redis.from_url(redis_url))

# --- UTILS ---
def get_spotify_track_info(spotify_url):
    match = re.search(r'track/([a-zA-Z0-9]+)', spotify_url)
    if not match:
        return None

    track_id = match.group(1)
    token_res = requests.post('https://accounts.spotify.com/api/token',
                              data={'grant_type': 'client_credentials'},
                              auth=('a9696c09751941f9a9d116dc42cb8f53', '45af6d795c144d7883bef909c62419be'))
    token = token_res.json().get('access_token')
    res = requests.get(f'https://api.spotify.com/v1/tracks/{track_id}',
                       headers={'Authorization': f'Bearer {token}'})
    print(res, file=sys.stderr)
    return res.json() if res.ok else None

# def get_proxy_from_zingproxy():
#     try:
#         res = requests.get('https://api.zingproxy.com/proxy/dan-cu-viet-nam/running',
#                            headers={'Authorization': f'Bearer {ZING_PROXY_TOKEN}'})
#         proxy = res.json().get('proxies', [])[0]
#         return f"http://{proxy['username']}:{proxy['password']}@{proxy['hostIp']}:{proxy['portHttp']}"
#     except:
#         return None

def upload_to_wasabi(filepath, filename):
    # Dummy - replace with boto3 or real upload
    return f"https://your-wasabi-url.com/{filename}"

# --- DOWNLOAD JOB ---
# def download_audio_job(download_id, search_keyword):
#     print('zo here123 download_audio_job', file=sys.stderr)
#     proxy = get_proxy_from_zingproxy()
#     os.makedirs(TEMP_DIR, exist_ok=True)
#
#     try:
#         search_cmd = [
#             YT_DLP_PATH, '--proxy', proxy, '--no-check-certificate', '--default-search', 'ytmusic',
#             '--skip-download', '--dump-json', f'ytsearch1:{search_keyword} official audio'
#         ]
#
#         print('zo here123', file=sys.stderr)
#         result = subprocess.run(search_cmd, capture_output=True, text=True, check=True, timeout=180)
#
#         print('result', file=sys.stderr)
#         print(result.stdout, file=sys.stderr)
#         video = json.loads(result.stdout)
#         video_url = video.get('webpage_url')
#         title = video.get('title')
#         slug = slugify(title)
#         output_path = os.path.join(TEMP_DIR, f'{slug}.%(ext)s')
#         expected_file = os.path.join(TEMP_DIR, f'{slug}.mp3')
#
#         if os.path.exists(expected_file):
#             os.remove(expected_file)
#
#         download_cmd = [
#             YT_DLP_PATH, '--proxy', proxy, '--no-check-certificate', '--audio-format', 'mp3',
#             '--extract-audio', '-o', output_path, video_url
#         ]
#         subprocess.run(download_cmd, capture_output=True, text=True, check=True, timeout=600)
#
#         if not os.path.exists(expected_file):
#             raise Exception("File not found after download")
#
#         file_name = f"{slug}_{download_id}.mp3"
#         public_url = upload_to_wasabi(expected_file, file_name)
#
#         with Session() as session:
#             download = session.query(Download).filter_by(download_id=download_id).first()
#             if download:
#                 download.status = 'completed'
#                 download.file_name = file_name
#                 download.file_path = public_url
#                 download.updated_at = datetime.utcnow()
#                 session.commit()
#
#     except Exception as e:
#         with Session() as session:
#             download = session.query(Download).filter_by(download_id=download_id).first()
#             if download:
#                 download.status = 'failed'
#                 session.commit()
#         raise
#     finally:
#         if os.path.exists(expected_file):
#             os.remove(expected_file)

# --- ROUTE ---
@app.route('/api/download', methods=['POST'])
def download():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'Missing URL'}), 400

    track_info = get_spotify_track_info(url)
    if not track_info:
        return jsonify({'error': 'Invalid Spotify URL'}), 400

    keyword = f"{track_info['name']} {track_info['artists'][0]['name']}"
    download_id = track_info['id']

    with Session() as session:
        # print('check session', file=sys.stderr)
        # print(session, file=sys.stderr)
        downloadMusic = session.query(Download).filter_by(download_id=download_id).first()
        # print('check download', file=sys.stderr)
        # print(download, file=sys.stderr)
        if not downloadMusic:
            downloadMusic = Download(download_id=download_id, url=url, status='pending')
            session.add(downloadMusic)
            session.commit()
            q.enqueue(download_audio_job, download_id, keyword)

        print('download_id', file=sys.stderr)
        print(downloadMusic.status, file=sys.stderr)
        print(downloadMusic, file=sys.stderr)
        print(downloadMusic.file_path, file=sys.stderr)
        if downloadMusic.status == 'completed':
            return jsonify({
                'status': 'completed',
                'download_id': download_id,
                'file': downloadMusic.file_path
            })
        elif downloadMusic.status == 'failed':
            return jsonify({
                'status': 'failed',
                'download_id': download_id,
                'message': 'Download failed.'
            })
        else:
            return jsonify({
                'status': 'processing',
                'download_id': download_id,
                'message': 'Đang xử lý, vui lòng thử lại sau.'
            })

@app.route('/')
def index():
    return 'hello world'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
