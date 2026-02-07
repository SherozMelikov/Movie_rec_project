# Use the official Python image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy your FastAPI app folder into container
COPY app ./app

# Run Uvicorn, using the Railway $PORT environment variable
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

