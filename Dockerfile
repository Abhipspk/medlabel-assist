FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 HF_HOME=/models PIP_NO_CACHE_DIR=1
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN grep -viE '^(torch|pywin32|pypiwin32)' requirements.txt > /tmp/req.txt \
 && pip install -r /tmp/req.txt \
 && pip show uvicorn fastapi > /dev/null
COPY src ./src
EXPOSE 8000
CMD ["uvicorn", "api:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
