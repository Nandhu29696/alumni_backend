FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0
COPY . .
EXPOSE 8000
CMD ["gunicorn", "alumni_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
