FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home app
COPY --chown=app:app config ./config
COPY --chown=app:app lms ./lms
COPY --chown=app:app manage.py .
USER 10001
EXPOSE 8017
CMD ["gunicorn","config.wsgi:application","--bind","0.0.0.0:8017","--workers","3","--threads","2","--timeout","240","--access-logfile","-","--access-logformat","%(h)s %(m)s %(U)s %(s)s %(L)s","--error-logfile","-"]
