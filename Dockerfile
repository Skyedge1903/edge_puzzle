FROM python:3.12.10-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dépendances système minimales + supervisor
RUN apt-get update \
    && apt-get install -y --no-install-recommends supervisor \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install gunicorn

# Code applicatif
COPY . .

# Config Supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Sécurité : utilisateur non-root
RUN useradd -m appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8050

# Lancement unique : Supervisor gère tout
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
