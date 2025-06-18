import os
import json
import subprocess
from slugify import slugify
from datetime import datetime
from .models import Session, Download
from .utils import get_proxy_from_zingproxy, upload_to_wasabi

YT_DLP_PATH = "/usr/local/bin/yt-dlp"
TEMP_DIR = "/tmp/yt-downloads"

def download_audio_job(download_id, search_keyword):
    proxy = get_proxy_from_zingproxy()
    os.makedirs(TEMP_DIR, exist_ok=True)

    try:
        search_cmd = [
            YT_DLP_PATH, '--proxy', proxy, '--no-check-certificate', '--default-search', 'ytmusic',
            '--skip-download', '--dump-json', f'ytsearch1:{search_keyword} official audio'
        ]
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
            YT_DLP_PATH, '--proxy', proxy, '--no-check-certificate', '--audio-format', 'mp3',
            '--extract-audio', '-o', output_path, video_url
        ]
        subprocess.run(download_cmd, capture_output=True, text=True, check=True, timeout=600)

        if not os.path.exists(expected_file):
            raise Exception("File not found after download")

        file_name = f"{slug}_{download_id}.mp3"
        public_url = upload_to_wasabi(expected_file, file_name)

        with Session() as session:
            download = session.query(Download).filter_by(download_id=download_id).first()
            if download:
                download.status = 'completed'
                download.file_name = file_name
                download.file_path = public_url
                download.updated_at = datetime.utcnow()
                session.commit()

    except Exception:
        with Session() as session:
            download = session.query(Download).filter_by(download_id=download_id).first()
            if download:
                download.status = 'failed'
                session.commit()
        raise
    finally:
        if os.path.exists(expected_file):
            os.remove(expected_file)
