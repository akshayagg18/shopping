FROM python:3.12-slim-bookworm

RUN useradd --uid 1000 --no-create-home --home-dir /scratch app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY src/ /app/src/
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
CMD ["/app/run.sh"]
