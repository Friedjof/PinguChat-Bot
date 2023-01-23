FROM python:3.10

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip3 install --upgrade pip && \
    pip3 install -r requirements.txt

# Copy project files
COPY . .

# Run the command to start the app
CMD ["python3", "main.py"]
