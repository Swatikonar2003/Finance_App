# Finance_App
A simple Django-based Finance Application to track transactions, manage categories, and view reports. This application uses JWT for authentication and integrates with PostgreSQL for data storage. It also provides an interactive API with Swagger and Redoc documentation.

Features
User Authentication: Signup, login, email verification.
Transaction Management: Add, update, and categorize transactions.
Category Management: Define categories for transactions.
Reports: View transaction categories and their percentage contribution.
Admin Panel: Manage users, categories, and transactions.
API Documentation: Swagger and Redoc UI for API documentation.
Tech Stack
Django 5.x
PostgreSQL (as the database)
Gunicorn (WSGI server)
Docker (for containerization)
Nginx (reverse proxy)
Django REST Framework (for the API)
JWT (for authentication)
Docker Compose (for managing services)
Prerequisites
Before getting started, make sure you have the following installed:

Docker (for running services in containers)
Docker Compose (for orchestrating multi-container environments)
Python 3.10 (for development purposes, if you are not using Docker)
Environment Variables
The project uses a .env file to manage environment variables. You should include the following variables in your .env file:

SECRET_KEY=<your-secret-key>
DEBUG=True
ALLOWED_HOSTS=localhost, 127.0.0.1
DB_NAME=finance_db
DB_USER=finance_user
DB_PASSWORD=<your-db-password>
DB_HOST=db
DB_PORT=5432
EMAIL_HOST_USER=<your-email>
EMAIL_HOST_PASSWORD=<your-email-password>
Setup and Installation
1. Clone the repository
git clone https://github.com/yourusername/financeApp.git
cd financeApp
2. Create a virtual environment (Optional but recommended)
python3 -m venv venv
source venv/bin/activate  # For Linux/Mac
venv\Scripts\activate     # For Windows
3. Install dependencies
Ensure that requirements.txt is up to date, and install the necessary Python packages:

pip install -r requirements.txt
4. Set up Docker containers
If you're using Docker, you can run the application using Docker Compose.

Build and start the containers:
docker-compose up --build
This command will:

Build the Docker images for the application (app), PostgreSQL (db), and Nginx.

Start the containers and create a development environment with PostgreSQL, Django, and Nginx.

Run the containers in detached mode:

docker-compose up -d
To stop the containers:
docker-compose down
5. Apply migrations
Once the containers are up and running, apply the migrations to set up the database schema:

docker-compose exec app python manage.py collectstatic
docker-compose exec app python manage.py makemigrations
6. Create a superuser (for admin panel access)
To access the Django Admin panel, you need to create a superuser account:

docker-compose exec app python manage.py createsuperuser
Follow the prompts to create a superuser.

7. Access the application
Admin Panel: http://localhost/admin/
API Documentation (Swagger UI): http://localhost/api/docs/
API Documentation (Redoc): http://localhost/api/redoc/
App API Endpoints: /api/ for authenticated API access.
Docker Architecture
This project is containerized using Docker with the following services:

App: The Django application running with Gunicorn.
Database: PostgreSQL 14 for storing data.
Nginx: A reverse proxy for serving the app and static files.
Docker Compose Services
app: The Django app, which also handles migrations and starts the Gunicorn server.
db: PostgreSQL 14 database with a health check to ensure the database is ready before starting the app.
nginx: A reverse proxy that handles static files and forwards requests to the Django application.
API Documentation
Authentication
Login: POST /auth/login/

Endpoint to log in and receive JWT tokens.
Response: JWT tokens (access token and refresh token).
Signup: POST /auth/signup/

Endpoint to sign up a new user.
Body: username, password, email, etc.
Response: User created confirmation.
Verify Email: GET /auth/verify-email/

Endpoint to verify the user's email address.
Response: Email verification status.
Token
Create Token: POST /token/

Endpoint to get JWT tokens by providing credentials (username and password).
Body: username, password.
Response: JWT access token and refresh token.
Refresh Token: POST /token/refresh/

Endpoint to refresh the access token using a valid refresh token.
Body: refresh token.
Response: New access token.
Transactions
Get all transactions: GET /app/transactions/

Endpoint to get a list of all transactions.
Response: List of transactions, including transaction type, amount, and category.
Create a new transaction: POST /app/transactions/

Endpoint to create a new transaction.
Body: user, category, amount, transaction_type.
Response: Newly created transaction object.
Get transaction data by category with percentages: GET /app/transactions/category-percentage/

Endpoint to retrieve transaction data grouped by categories and their percentage contributions.
Response: List of categories with their transaction percentage.
Categories
Get all categories: GET /app/categories/

Endpoint to get a list of all categories.
Response: List of categories (e.g., Food, Entertainment).
Create a new category: POST /app/categories/

Endpoint to create a new category for transactions.
Body: name, created_by (User ID).
Response: Newly created category object.
User Balance
Get user balance: GET /app/balance/
Endpoint to get the current balance of a user, calculated from transactions.
Response: Current balance (sum of all credits and debits).
Common Docker Commands
Build the Docker Image
docker-compose build
View Logs
docker-compose logs
View Running Containers
docker ps
Troubleshooting
Database Connection Errors: If you see connection errors, ensure the database service (db) is running correctly, and try restarting the services using:

docker-compose restart
Migrations not applying: Ensure the database container is fully started before running migrations. You can also try manually running migrations:

docker-compose exec app python manage.py migrate
Contributing
Contributions are welcome! To contribute to this project:

Fork the repository.
Create a new branch (git checkout -b feature/your-feature).
Commit your changes (git commit -am 'Add your feature').
Push to your branch (git push origin feature/your-feature).
Open a Pull Request.
Contact
For any questions or suggestions, feel free to contact me at swatikonar2003@gmail.com.

Key Sections in the README:
Project Title and Overview: An introduction to what the project does and its core features.
Tech Stack: The main technologies and frameworks used to build the project.
Prerequisites: Instructions on what you need to have installed on your machine before running the project.
Setup and Installation: Detailed steps for setting up and running the project locally, both with and without Docker.
Docker Architecture: A breakdown of the Docker services used in the project.
API Documentation: A section describing the key API endpoints, their methods, and use cases.
Common Docker Commands: Useful Docker commands for managing the project containers.
Troubleshooting: Instructions for solving common issues.
Contributing: Guidelines for contributing to the project.
License: The project's license information.
Contact Information: An email for questions and suggestions.
This structure ensures that your README is clear, easy to navigate, and contains all necessary details for setting up, using, and contributing to the project. It's formatted in a way that's easy to read on GitHub.
