import os
import json
import sys
import subprocess
from slugify import slugify
from datetime import datetime
import requests
from download import Session, Download

# --- CONFIG ---
YT_DLP_PATH = "/usr/local/bin/yt-dlp"
TEMP_DIR = "/tmp/yt-downloads"
ZING_PROXY_TOKEN = os.getenv("ZING_PROXY_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

def get_proxy_from_zingproxy():
    try:
        res = requests.get('https://api.zingproxy.com/proxy/dan-cu-viet-nam/running',
                           headers={'Authorization': f'Bearer {ZING_PROXY_TOKEN}'})
        proxy = res.json().get('proxies', [])[0]
        return f"http://{proxy['username']}:{proxy['password']}@{proxy['hostIp']}:{proxy['portHttp']}"
    except:
        return None

def upload_to_wasabi(filepath, filename):
    # Dummy - replace with boto3 or real upload
    return f"https://s3.ap-southeast-1.wasabisys.com/merrychill/{filename}"

def download_audio_job(download_id, search_keyword):
    # proxy = get_proxy_from_zingproxy()
    os.makedirs(TEMP_DIR, exist_ok=True)
    expected_file = None

    try:
        search_cmd = [
            YT_DLP_PATH, '--no-check-certificate', '--default-search', 'ytmusic',
            '--skip-download', '--dump-json', f'ytsearch1:{search_keyword} official audio'
        ]
        print('zo here123456 download_audio_job', file=sys.stderr)
        result = subprocess.run(search_cmd, capture_output=True, text=True, check=True, timeout=180)
        video = json.loads(result.stdout)
        video_url = video.get('webpage_url')
        title = video.get('title')
        slug = slugify(title)
        output_path = os.path.join(TEMP_DIR, f'{slug}.%(ext)s')
        expected_file = os.path.join(TEMP_DIR, f'{slug}.mp3')

        if os.path.exists(expected_file):
            os.remove(expected_file)

        download_cmd = [
            YT_DLP_PATH, '--no-check-certificate', '--audio-format', 'mp3',
            '--extract-audio', '-o', output_path, video_url
        ]
        subprocess.run(download_cmd, capture_output=True, text=True, check=True, timeout=600)

        if not os.path.exists(expected_file):
            raise Exception("File not found after download")

        file_name = f"{slug}_{download_id}.mp3"
        public_url = upload_to_wasabi(expected_file, file_name)

        print('zo here123 download_audio_job', file=sys.stderr)
        print(public_url, file=sys.stderr)
        with Session() as session:
            download = session.query(Download).filter_by(download_id=download_id).first()
            if download:
                download.status = 'completed'
                download.file_name = file_name
                download.file_path = public_url
                download.updated_at = datetime.utcnow()
                session.commit()
            print('check download hehe', file=sys.stderr)
            print(download, file=sys.stderr)
            print(download.status, file=sys.stderr)
            print(download.file_name, file=sys.stderr)

    except Exception:
        with Session() as session:
            download = session.query(Download).filter_by(download_id=download_id).first()
            if download:
                download.status = 'failed'
                session.commit()
        raise
    # finally:
        # if expected_file and os.path.exists(expected_file):
        #     os.remove(expected_file)
