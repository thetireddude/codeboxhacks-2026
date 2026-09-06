import os


# Flask-SocketIO's in-process connection registry requires one worker. Threads
# provide concurrency while Redis owns durable matchmaking/game state.
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
worker_class = "gthread"
workers = 1
threads = int(os.getenv("WEB_THREADS", "100"))
timeout = int(os.getenv("WEB_TIMEOUT_SECONDS", "90"))
accesslog = "-"
errorlog = "-"
capture_output = True
