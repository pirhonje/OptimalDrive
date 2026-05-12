FROM python:3.11-slim

WORKDIR /source

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chmod=755 . .

# Get the development environment variable from the environment
ENV DEVELOPMENT=${DEVELOPMENT:-false}

EXPOSE 8888

# If development is true, run with dev_runner.py, otherwise run with main.py
CMD ["bash", "run.sh"]
