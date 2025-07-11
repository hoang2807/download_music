#!/usr/bin/env python3
import os
from redis import Redis
from rq import Worker, Queue

# Kết nối Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_conn = Redis.from_url(redis_url)

# Tạo queue
queue = Queue(connection=redis_conn)

if __name__ == '__main__':
    # Khởi chạy worker
    worker = Worker(
        [queue],
        connection=redis_conn,
        # Thêm timeout cho worker
        job_timeout=1800,  # 30 phút timeout cho mỗi job
        result_ttl=3600,  # Giữ kết quả trong 1 giờ
        failure_ttl=86400  # Giữ lỗi trong 24 giờ
    )

    print(f"Worker {worker.name} started...")
    worker.work()