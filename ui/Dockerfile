FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN pip install --no-cache-dir streamlit==1.38.0 requests==2.32.3
COPY ui /app

CMD ["bash", "-lc", "streamlit run /app/streamlit_app.py --server.port ${PORT} --server.address 0.0.0.0"]
