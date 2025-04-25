
FROM python:3.9

WORKDIR /app


COPY requirements.txt requirements.txt

# Install system dependencies and Python dependencies
# Install gcc and other build tools for compiling packages like netifaces
RUN pip install --no-cache-dir --upgrade -r requirements.txt


COPY ./src /apps
# COPY . .
# COPY ./src /app/src

# Expose FastAPI port
EXPOSE 8000


CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
# CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000"]

# Use Gunicorn with Uvicorn workers for production
# CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000"]