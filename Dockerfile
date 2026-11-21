# Build stage; official runner builds with network access.
FROM python:3.12-slim-bookworm AS compiler
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY src/solver.cpp /build/solver.cpp
RUN g++ -std=c++20 -O3 -DNDEBUG -pipe -pthread -o /build/shopping_core /build/solver.cpp

FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir 'duckdb==1.4.2'
WORKDIR /app
COPY --from=compiler /build/shopping_core /app/shopping_core
COPY src/export_parquet.py /app/src/export_parquet.py
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["/app/run.sh"]
