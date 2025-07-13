import os
import re

import boto3
import requests
from botocore.config import Config
from flask import Flask, request, jsonify
from redis import Redis
from rq import Queue, Worker
from rq.job import Job
from rq.registry import FailedJobRegistry, FinishedJobRegistry, StartedJobRegistry

from jobs import Session, Download, download_audio_job
from worker import redis_conn

# --- CONFIG ---
YT_DLP_PATH = "/usr/local/bin/yt-dlp"
TEMP_DIR = "/tmp/yt-downloads"
ZING_PROXY_TOKEN = os.getenv("ZING_PROXY_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")


# --- FLASK APP ---
app = Flask(__name__)
# q = Queue(connection=Redis())
q = Queue(
    connection=redis_conn,
    default_timeout=1800,  # 30 phút timeout
    result_ttl=3600,       # Giữ kết quả trong 1 giờ
    failure_ttl=86400      # Giữ lỗi trong 24 giờ
)

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

    return res.json() if res.ok else None

# --- QUEUE MONITORING FUNCTIONS ---
def get_queue_stats():
    """Lấy thống kê tổng quan về queue"""
    workers = Worker.all(connection=redis_conn)
    active_workers = [worker for worker in workers if worker.get_state() == 'busy']

    stats = {
        'total_jobs': len(q),
        'pending_jobs': len(q),
        'workers': len(workers),
        'active_workers': len(active_workers),
        'failed_jobs': len(FailedJobRegistry(connection=redis_conn)),
        'finished_jobs': len(FinishedJobRegistry(connection=redis_conn)),
        'started_jobs': len(StartedJobRegistry(connection=redis_conn))
    }
    return stats

def get_job_details(job_id):
    """Lấy chi tiết của một job cụ thể"""
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        return {
            'id': job.id,
            'status': job.get_status(),
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'ended_at': job.ended_at.isoformat() if job.ended_at else None,
            'result': str(job.result) if job.result else None,
            'exc_info': job.exc_info if job.exc_info else None,
            'meta': job.meta,
            'timeout': job.timeout,
            'func_name': job.func_name
        }
    except Exception as e:
        return {'error': str(e)}


def get_failed_jobs():
    """Lấy danh sách các job đã thất bại"""
    failed_registry = FailedJobRegistry(connection=redis_conn)
    failed_jobs = []

    for job_id in failed_registry.get_job_ids():
        job_details = get_job_details(job_id)
        failed_jobs.append(job_details)

    return failed_jobs


def get_finished_jobs():
    """Lấy danh sách các job đã hoàn thành"""
    finished_registry = FinishedJobRegistry(connection=redis_conn)
    finished_jobs = []

    for job_id in finished_registry.get_job_ids():
        job_details = get_job_details(job_id)
        finished_jobs.append(job_details)

    return finished_jobs


def get_pending_jobs():
    """Lấy danh sách các job đang chờ"""
    pending_jobs = []

    for job in q.jobs:
        job_details = get_job_details(job.id)
        pending_jobs.append(job_details)

    return pending_jobs


def get_started_jobs():
    """Lấy danh sách các job đang chạy"""
    started_registry = StartedJobRegistry(connection=redis_conn)
    started_jobs = []

    for job_id in started_registry.get_job_ids():
        job_details = get_job_details(job_id)
        started_jobs.append(job_details)

    return started_jobs


# --- MONITORING ROUTES ---
@app.route('/api/queue/stats', methods=['GET'])
def queue_stats():
    """API endpoint để lấy thống kê queue"""
    try:
        stats = get_queue_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/queue/jobs', methods=['GET'])
def list_jobs():
    """API endpoint để lấy danh sách tất cả jobs theo trạng thái"""
    try:
        status = request.args.get('status', 'all')

        if status == 'failed':
            jobs = get_failed_jobs()
        elif status == 'finished':
            jobs = get_finished_jobs()
        elif status == 'pending':
            jobs = get_pending_jobs()
        elif status == 'started':
            jobs = get_started_jobs()
        else:
            # Lấy tất cả jobs
            jobs = {
                'failed': get_failed_jobs(),
                'finished': get_finished_jobs(),
                'pending': get_pending_jobs(),
                'started': get_started_jobs()
            }

        return jsonify(jobs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/queue/job/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """API endpoint để lấy trạng thái của một job cụ thể"""
    try:
        job_details = get_job_details(job_id)
        return jsonify(job_details)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/queue/job/<job_id>/requeue', methods=['POST'])
def requeue_job(job_id):
    """API endpoint để requeue một job đã thất bại"""
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        if job.get_status() == 'failed':
            job.requeue()
            return jsonify({'message': f'Job {job_id} đã được requeue thành công'})
        else:
            return jsonify({'error': 'Job không ở trạng thái failed'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/queue/job/<job_id>/delete', methods=['DELETE'])
def delete_job(job_id):
    """API endpoint để xóa một job"""
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        job.delete()
        return jsonify({'message': f'Job {job_id} đã được xóa thành công'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/queue/clear', methods=['POST'])
def clear_queue():
    """API endpoint để clear queue"""
    try:
        queue_type = request.json.get('type', 'all')

        if queue_type == 'failed':
            failed_registry = FailedJobRegistry(connection=redis_conn)
            for job_id in failed_registry.get_job_ids():
                job = Job.fetch(job_id, connection=redis_conn)
                job.delete()
            return jsonify({'message': 'Đã xóa tất cả failed jobs'})
        elif queue_type == 'finished':
            finished_registry = FinishedJobRegistry(connection=redis_conn)
            for job_id in finished_registry.get_job_ids():
                job = Job.fetch(job_id, connection=redis_conn)
                job.delete()
            return jsonify({'message': 'Đã xóa tất cả finished jobs'})
        elif queue_type == 'pending':
            q.empty()
            return jsonify({'message': 'Đã xóa tất cả pending jobs'})
        else:
            return jsonify({'error': 'Invalid queue type'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- DASHBOARD ROUTE ---
@app.route('/dashboard')
def dashboard():
    """Simple HTML dashboard để monitor queue"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Queue Monitor Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .stats { display: flex; gap: 20px; margin-bottom: 20px; }
            .stat-box { border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
            .job-list { margin-top: 20px; }
            .job-item { border: 1px solid #eee; padding: 10px; margin: 5px 0; border-radius: 3px; }
            .failed { border-left: 4px solid #ff4444; }
            .finished { border-left: 4px solid #44ff44; }
            .pending { border-left: 4px solid #ffaa44; }
            .started { border-left: 4px solid #4444ff; }
            button { padding: 5px 10px; margin: 2px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>Queue Monitor Dashboard</h1>
        <div id="stats" class="stats"></div>
        <div>
            <button onclick="loadJobs('all')">All Jobs</button>
            <button onclick="loadJobs('pending')">Pending</button>
            <button onclick="loadJobs('started')">Started</button>
            <button onclick="loadJobs('finished')">Finished</button>
            <button onclick="loadJobs('failed')">Failed</button>
            <button onclick="loadStats()">Refresh Stats</button>
        </div>
        <div id="jobs" class="job-list"></div>

        <script>
            function loadStats() {
                fetch('/api/queue/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('stats').innerHTML = `
                            <div class="stat-box">
                                <h3>Total Jobs</h3>
                                <p>${data.total_jobs}</p>
                            </div>
                            <div class="stat-box">
                                <h3>Pending</h3>
                                <p>${data.pending_jobs}</p>
                            </div>
                            <div class="stat-box">
                                <h3>Started</h3>
                                <p>${data.started_jobs}</p>
                            </div>
                            <div class="stat-box">
                                <h3>Finished</h3>
                                <p>${data.finished_jobs}</p>
                            </div>
                            <div class="stat-box">
                                <h3>Failed</h3>
                                <p>${data.failed_jobs}</p>
                            </div>
                            <div class="stat-box">
                                <h3>Workers</h3>
                                <p>${data.workers}</p>
                            </div>
                        `;
                    });
            }

            function loadJobs(status) {
                fetch(`/api/queue/jobs?status=${status}`)
                    .then(response => response.json())
                    .then(data => {
                        let html = '';
                        if (status === 'all') {
                            ['pending', 'started', 'finished', 'failed'].forEach(s => {
                                if (data[s] && data[s].length > 0) {
                                    html += `<h3>${s.toUpperCase()}</h3>`;
                                    data[s].forEach(job => {
                                        html += createJobHtml(job, s);
                                    });
                                }
                            });
                        } else {
                            data.forEach(job => {
                                html += createJobHtml(job, status);
                            });
                        }
                        document.getElementById('jobs').innerHTML = html;
                    });
            }

            function createJobHtml(job, status) {
                return `
                    <div class="job-item ${status}">
                        <strong>Job ID:</strong> ${job.id}<br>
                        <strong>Status:</strong> ${job.status}<br>
                        <strong>Function:</strong> ${job.func_name}<br>
                        <strong>Created:</strong> ${job.created_at || 'N/A'}<br>
                        <strong>Started:</strong> ${job.started_at || 'N/A'}<br>
                        <strong>Ended:</strong> ${job.ended_at || 'N/A'}<br>
                        ${job.exc_info ? `<strong>Error:</strong> ${job.exc_info}<br>` : ''}
                        ${status === 'failed' ? `<button onclick="requeueJob('${job.id}')">Requeue</button>` : ''}
                        <button onclick="deleteJob('${job.id}')">Delete</button>
                    </div>
                `;
            }

            function requeueJob(jobId) {
                fetch(`/api/queue/job/${jobId}/requeue`, {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        alert(data.message || data.error);
                        loadJobs('failed');
                    });
            }

            function deleteJob(jobId) {
                if (confirm('Are you sure you want to delete this job?')) {
                    fetch(`/api/queue/job/${jobId}/delete`, {method: 'DELETE'})
                        .then(response => response.json())
                        .then(data => {
                            alert(data.message || data.error);
                            loadStats();
                        });
                }
            }

            // Load initial data
            loadStats();
            loadJobs('all');

            // Auto refresh every 30 seconds
            setInterval(() => {
                loadStats();
            }, 30000);
        </script>
    </body>
    </html>
    '''

# --- ROUTE ---
@app.route('/api/download', methods=['POST'])
def download():
    WASABI_ACCESS_KEY = os.getenv("WASABI_ACCESS_KEY")
    WASABI_SECRET_KEY = os.getenv("WASABI_SECRET_KEY")
    WASABI_BUCKET = os.getenv("WASABI_BUCKET")
    WASABI_REGION = "ap-southeast-1"
    url = request.json.get('url')
    name = request.json.get('name')
    artists = request.json.get('artists')
    id = request.json.get('id')
    if not url:
        return jsonify({'error': 'Missing URL'}), 400

    if not name:
        return jsonify({'error': 'Missing name'}), 400

    if not artists:
        return jsonify({'error': 'Missing artists'}), 400

    if not id:
        return jsonify({'error': 'Missing id'}), 400


    keyword = f"{name} {artists}"
    download_id = id
    temp_url = ''

    with Session() as session:
        downloadMusic = session.query(Download).filter_by(download_id=download_id).first()

        if not downloadMusic:
            downloadMusic = Download(download_id=download_id, url=url, status='pending')
            session.add(downloadMusic)
            session.commit()
            q.enqueue(download_audio_job, download_id, keyword, url)

        if downloadMusic.file_name:
            s3 = boto3.client(
                's3',
                region_name=WASABI_REGION,  # Thay theo vùng Wasabi của bạn
                endpoint_url=f'https://s3.{WASABI_REGION}.wasabisys.com',  # URL Wasabi
                aws_access_key_id=WASABI_ACCESS_KEY,
                aws_secret_access_key=WASABI_SECRET_KEY,
                config=Config(signature_version='s3v4')
            )

            temp_url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': WASABI_BUCKET,
                    'Key': downloadMusic.file_name
                },
                ExpiresIn=3600  # 60 phút
            )

        if downloadMusic.status == 'completed':
            return jsonify({
                'status': 'completed',
                'download_id': download_id,
                'file': temp_url
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
    app.run(host='0.0.0.0', port=5000, debug=False)
