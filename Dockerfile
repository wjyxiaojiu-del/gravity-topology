FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 暴露端口
EXPOSE 8050

# 启动 Flask 应用（gunicorn 生产模式）
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8050", "--workers", "2", "--timeout", "120"]
