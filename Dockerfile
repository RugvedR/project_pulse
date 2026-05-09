# Step 1: Use an official, stable Python "slim" image.
# "slim" is industry-standard because it is small and secure (fewer vulnerabilities).
FROM python:3.11-slim

# Step 2: Set environment variables to optimize Python for containers.
# Prevents Python from writing .pyc files (keeps the image clean)
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures logs are sent straight to the terminal (no buffering)
ENV PYTHONUNBUFFERED=1

# Step 3: Set the working directory inside the container.
WORKDIR /app

# Step 4: Install OS-level dependencies.
# We need 'gcc' and 'libpq-dev' because our database library (psycopg2) 
# needs to compile some C code to talk to PostgreSQL.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Step 5: Copy ONLY the requirements first.
# This is a "PRO TIP." Docker caches this step. 
# If you change your code but NOT your requirements, 
# Docker will skip the slow 'pip install' step next time you build!
COPY requirements.txt .

# Step 6: Install Python dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Step 7: Copy the rest of your application code.
COPY . .

# Step 8: The "Entry Point" — what to do when the container starts.
# By default, we want to run the Telegram Bot driver.
CMD ["python", "main.py"]
