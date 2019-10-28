from os import getenv
import multiprocessing

bind = f":{getenv('GUNICORN_PORT', 9000)}"
workers = multiprocessing.cpu_count() * 2 + 1
threads = multiprocessing.cpu_count()
