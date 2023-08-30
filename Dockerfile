FROM python:alpine3.18

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rescue_snapshot.py .

CMD ["python", "rescue_snapshot.py"]