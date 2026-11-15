FROM python:3.12-slim
WORKDIR /app
ENV TZ=Asia/Shanghai PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
COPY app.py tracker.py config.py net.py p115.py drivemby.py search.py routes.py localtorrent.py p115upload.py ./
COPY static ./static
EXPOSE 8099
CMD ["python", "app.py"]
