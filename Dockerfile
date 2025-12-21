FROM python:3.9.19

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y supervisor

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install gunicorn

COPY . .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8050

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
