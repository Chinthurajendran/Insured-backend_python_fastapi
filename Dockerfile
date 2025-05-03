
FROM python:3.9

WORKDIR /app


COPY requirements.txt requirements.txt

# Install system dependencies and Python dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt


COPY ./src /apps



CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
