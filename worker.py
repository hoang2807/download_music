#!/usr/bin/env python
import os
from redis import Redis
from rq import Worker, Queue, Connection

# Thiết lập kết nối Redis
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_conn = Redis.from_url(redis_url)

if __name__ == '__main__':
    with Connection(redis_conn):
        worker = Worker(['default'], connection=redis_conn)
        print('Starting RQ worker...')
        worker.work()