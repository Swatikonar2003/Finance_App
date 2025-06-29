# Use an official Python runtime
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install pip requirements
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project files
COPY . /app/

# Expose port
EXPOSE 8000

# Run migrations automatically and then start the app
CMD ["sh", "-c", "python manage.py migrate && gunicorn financeApp.wsgi:application --bind 0.0.0.0:8000"]
