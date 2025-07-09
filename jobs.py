import os
import json
import glob
import re
import sys
import subprocess
from slugify import slugify
from datetime import datetime
import requests
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import time

# --- SQLALCHEMY SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL")
Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class Download(Base):
    __tablename__ = 'downloads'
    download_id = Column(String(64), primary_key=True)
    url = Column(String(255))
    status = Column(String(32))
    file_name = Column(String(255))
    file_path = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow)

# --- CONFIG ---
YT_DLP_PATH = "/usr/local/bin/yt-dlp"
TEMP_DIR = "/tmp/yt-downloads"
ZING_PROXY_TOKEN = os.getenv("ZING_PROXY_TOKEN")
DEFAULT_PROXY = "http://cZs0lhungn:v7u6FLJ2@103.125.189.149:8159"


def get_proxy_from_zingproxy():
    try:
        res = requests.get(
                'https://api.zingproxy.com/proxy/dan-cu-viet-nam/running',
                headers={'Authorization': f'Bearer {ZING_PROXY_TOKEN}'}
        )
        proxies = res.json().get('proxies', [])
        if proxies:
            #proxy = proxies[0]
            #return f"http://{proxy['username']}:{proxy['password']}@{proxy['hostIp']}:{proxy['portHttp']}"
            return DEFAULT_PROXY
        else:
            return DEFAULT_PROXY

    except Exception as e:
        # Log lỗi nếu cần: print(f"Proxy fetch error: {e}")
        print(f"Unexpected error: {e}")
        return DEFAULT_PROXY

def upload_to_wasabi(filepath, filename):
    # Dummy - replace with boto3 or real upload
    WASABI_ACCESS_KEY = os.getenv("WASABI_ACCESS_KEY")
    WASABI_SECRET_KEY = os.getenv("WASABI_SECRET_KEY")
    WASABI_BUCKET = os.getenv("WASABI_BUCKET")
    WASABI_REGION = "ap-southeast-1"

    # if not os.path.exists(filepath):
    #     print(f"ERROR: File not found: {filepath}", file=sys.stderr)
    #     raise FileNotFoundError(f"The file was not found: {filepath}")

    # Check file size and permissions
    try:
        file_size = os.path.getsize(filepath)
        print(f"File size: {file_size} bytes", file=sys.stderr)
        if file_size == 0:
            print("WARNING: File is empty", file=sys.stderr)
    except OSError as e:
        print(f"ERROR: Cannot access file {filepath}: {e}", file=sys.stderr)
        raise

    try:
        s3 = boto3.client(
            's3',
            endpoint_url=f'https://s3.{WASABI_REGION}.wasabisys.com',  # Correct endpoint for Wasabi
            aws_access_key_id=WASABI_ACCESS_KEY,
            aws_secret_access_key=WASABI_SECRET_KEY,
        )

        # s3.upload_file(filepath, WASABI_BUCKET, filename)
        # s3.upload_file(filepath, WASABI_BUCKET, filename, ExtraArgs={ 'ContentType': 'audio/mpeg', 'ACL': 'public-read' })

        # Upload file using put_object with necessary arguments
        print("Uploading to Wasabi S3...", file=sys.stderr)

        with open(filepath, 'rb') as data:
            s3.put_object(
                Body=data,
                Bucket=WASABI_BUCKET,
                Key=filename,
                ACL='public-read',  # If you want the file to be public
                ContentType='audio/mpeg',  # Specify the content type
            )
        # s3.put_object(Body=filepath, Bucket=WASABI_BUCKET, Key=filename, ACL='public-read')

        print('check upload_to_wasabi s3', file=sys.stderr)

        print(f"Successfully uploaded {filename} to Wasabi", file=sys.stderr)

        return f"https://s3.ap-southeast-1.wasabisys.com/{WASABI_BUCKET}/{filename}"
    except FileNotFoundError:
        print("The file was not found:", filepath, file=sys.stderr)
        raise
    except NoCredentialsError:
        print("Wasabi credentials not available", file=sys.stderr)
        raise
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"ERROR: AWS Client Error - {error_code}: {error_message}", file=sys.stderr)

        # Handle specific error cases
        if error_code == 'NoSuchBucket':
            print(f"ERROR: Bucket '{WASABI_BUCKET}' does not exist", file=sys.stderr)
        elif error_code == 'AccessDenied':
            print("ERROR: Access denied - check your credentials and bucket permissions", file=sys.stderr)
        elif error_code == 'InvalidAccessKeyId':
            print("ERROR: Invalid access key ID", file=sys.stderr)
        elif error_code == 'SignatureDoesNotMatch':
            print("ERROR: Invalid secret access key", file=sys.stderr)
        raise
    except Exception as e:
        print(f"ERROR: Unexpected error during upload: {type(e).__name__}: {e}", file=sys.stderr)
        raise


def download_audio_job(download_id, search_keyword, url):
    proxy = get_proxy_from_zingproxy()
    os.makedirs(TEMP_DIR, exist_ok=True)
    expected_file = None
    API_ENDPOINT = os.getenv("API_ENDPOINT")
    try:

        video_url = url
        title = download_id
        slug = slugify(title)
        output_path = os.path.join(TEMP_DIR, f'{slug}.%(ext)s')

        download_cmd = [
            YT_DLP_PATH,
            '--proxy', proxy,
            '--no-check-certificate',
            '--no-continue',
            '--socket-timeout', '60',
            '--retries', '2',
            '--fragment-retries', '3',
            '--concurrent-fragments', '8',
            '--downloader', 'aria2c',
            '--downloader-args', 'aria2c:"-x 16 -s 16 -k 1M"',
            '--no-playlist',
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', '0',
            '--no-warnings',
            '-o', output_path,
            video_url
        ]
        subprocess.run(download_cmd, capture_output=True, text=True, check=True, timeout=600)

        matching_files = glob.glob(os.path.join(TEMP_DIR, f'{slug}.*'))
        for file in matching_files:
            if re.search(r'\.(webm|m4a|opus|mp3)$', file):
                expected_file = file
                break

        if not expected_file or not os.path.exists(expected_file):
            raise Exception("Không tìm thấy file sau khi tải.")

        file_name = f"{slug}_{download_id}.mp3"
        # Tạo URL cục bộ tạm thời trước khi upload

        # if not os.path.exists(expected_file):
        #     raise Exception("File not found after download")

        start_upload = time.time()
        print(f"[⏫] Bắt đầu upload {file_name} lên Wasabi...")

        public_url = upload_to_wasabi(expected_file, file_name)

        upload_duration = time.time() - start_upload
        print(f"[✅] Upload hoàn tất sau {upload_duration:.2f} giây. Public URL: {public_url}")

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
        if expected_file and os.path.exists(expected_file):
            os.remove(expected_file)
