FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV EXPERIMENT_DB_PATH=/app/experiments.db
RUN python seed.py

EXPOSE 5000
CMD ["python", "app.py"]
