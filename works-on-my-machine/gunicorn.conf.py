"""Gunicorn 설정 파일."""

import os

# Server socket
# Azure App Service는 PORT 환경변수(기본 8080)를 통해 포트를 지정
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Worker processes
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000

# Timeout
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "azure-security-analyzer"
