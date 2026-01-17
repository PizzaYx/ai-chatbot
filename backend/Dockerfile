# 使用官方 Python 3.12 轻量镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量 (防止生成 .pyc，实时日志)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 安装系统依赖 (Postgres 驱动 + PDF 解析)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc libpq-dev \
       poppler-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装 (利用 Docker 缓存层)
COPY pyproject.toml /app/
RUN pip install --upgrade pip && \
    pip install .

# 复制项目代码
COPY . /app/

# 暴露端口 (Django 默认端口)
EXPOSE 8000

# 启动命令 (开发模式用 runserver，生产建议用 gunicorn)
# 这里为了 NAS 方便调试，我们先用 runserver 0.0.0.0:8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
