FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY migrations migrations
COPY alembic.ini start.py ./
COPY web web
RUN useradd --create-home appuser && mkdir -p /app/.data/covers && chown -R appuser:appuser /app/.data
USER appuser
ENV HOST=0.0.0.0
ENV PORT=8000
EXPOSE 8000
CMD ["python","start.py"]
