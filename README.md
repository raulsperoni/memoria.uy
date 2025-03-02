# Memoria.uy

A Django application for [brief description of your project].

## Table of Contents
- [Local Development](#local-development)
  - [Prerequisites](#prerequisites)
  - [Setup](#setup)
  - [Running Django Commands](#running-django-commands)
  - [Working with Tailwind CSS](#working-with-tailwind-css)
  - [Testing](#testing)
- [Docker Development](#docker-development)
- [Deployment](#deployment)
  - [GitHub Setup](#github-setup)
  - [DigitalOcean VPS Setup](#digitalocean-vps-setup)
  - [Deployment Process](#deployment-process)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)

## Local Development

### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/docs/#installation)
- Node.js and npm (for Tailwind CSS)
- Redis (for Celery)

### Setup

1. Clone the repository:
   ```sh
   git clone https://github.com/yourusername/memoria.uy.git
   cd memoria.uy
   ```

2. Install Python dependencies with Poetry:
   ```sh
   poetry install
   ```

3. Create a `.env` file based on `.env.example`:
   ```sh
   cp .env.example .env
   ```
   Then edit the `.env` file with your specific configuration.

4. Apply migrations:
   ```sh
   poetry run python manage.py migrate
   ```

5. Create a superuser:
   ```sh
   poetry run python manage.py createsuperuser
   ```

6. Install Tailwind CSS dependencies:
   ```sh
   make -f Makefile.local tailwind-install
   ```

7. Start the development server:
   ```sh
   make -f Makefile.local dev
   ```
   This will start both the Django server and Tailwind CSS watcher.

### Running Django Commands

To run Django commands using Poetry, follow these steps:

1. **Activate the Poetry Shell**:
    ```sh
    poetry shell
    ```

2. **Run Django Commands**:
    Once you are inside the Poetry shell, you can run Django commands as usual. For example:
    ```sh
    python manage.py migrate
    python manage.py runserver
    python manage.py createsuperuser
    ```

3. **Directly Run Commands with Poetry**:
    Alternatively, you can run Django commands directly without activating the shell:
    ```sh
    poetry run python manage.py migrate
    poetry run python manage.py runserver
    poetry run python manage.py createsuperuser
    ```

4. **Run Celery Worker**:
    To run the Celery worker using Poetry, you can use the following command:
    ```sh
    poetry run celery -A memoria worker --loglevel=info
    ```

### Working with Tailwind CSS

This project uses [django-tailwind](https://django-tailwind.readthedocs.io/) for integrating Tailwind CSS with Django. The Tailwind configuration is in the `theme` app.

#### Using Make Commands

We've added several make commands to simplify working with Tailwind CSS:

##### For Local Development (Makefile.local)

```sh
# Install Tailwind CSS dependencies
make -f Makefile.local tailwind-install

# Start the Tailwind CSS development server
make -f Makefile.local tailwind-start

# Build Tailwind CSS for production
make -f Makefile.local tailwind-build

# Watch for changes in Tailwind CSS files
make -f Makefile.local tailwind-watch

# Start both Django server and Tailwind CSS (in separate terminals)
make -f Makefile.local dev
```

#### Tailwind CSS Configuration

The Tailwind CSS configuration is located in:
- `theme/static_src/tailwind.config.js` - Main configuration file
- `theme/static_src/src/styles.css` - CSS file with Tailwind directives and custom styles

#### Development Workflow

1. Start the Django development server: `make -f Makefile.local runserver`
2. In a separate terminal, start the Tailwind CSS watcher: `make -f Makefile.local tailwind-start`
3. Make changes to your HTML templates using Tailwind CSS classes
4. For custom styles or Tailwind configuration changes, edit the files in the `theme` app

### Testing

This project uses pytest for testing. To run the tests:

```sh
# Run all tests
poetry run pytest
# or
make -f Makefile.local test

# Run tests with coverage report
poetry run pytest --cov=.
# or
make -f Makefile.local test-cov

# Run specific test file
poetry run pytest core/tests/test_basic.py

# Run tests with verbose output
poetry run pytest -v

# Run tests matching a specific name pattern
poetry run pytest -k "test_homepage"

# Run tests with specific markers
poetry run pytest -m "django_db"
```

#### Writing Tests

Test files should be placed in the `tests` directory of each app and follow the naming convention `test_*.py` or `*_test.py`.

Example test file structure:

```python
import pytest
from django.urls import reverse

# Use the django_db marker for tests that need database access
@pytest.mark.django_db
def test_my_view():
    # Test code here
    pass

# Group related tests in classes
@pytest.mark.django_db
class TestUserFeatures:
    # Use fixtures for test setup
    @pytest.fixture
    def user_data(self):
        return {'username': 'testuser', 'password': 'password123'}
    
    def test_user_registration(self, client, user_data):
        # Test registration
        pass
```

#### Fixtures

Common fixtures are defined in `conftest.py` at the project root and are available to all tests. These include:

- `client`: A Django test client
- `admin_client`: A Django test client logged in as an admin user
- `user`: A regular user instance
- `authenticated_client`: A Django test client logged in as a regular user

You can define additional fixtures in test files or in app-specific `conftest.py` files.

## Docker Development

This project includes Docker configuration for development and production.

1. Make sure you have Docker and Docker Compose installed.

2. Build and start the containers:
   ```sh
   docker-compose up -d --build
   ```

3. Run migrations:
   ```sh
   docker-compose exec web python manage.py migrate
   ```

4. Create a superuser:
   ```sh
   docker-compose exec web python manage.py createsuperuser
   ```

5. Access the application at http://localhost:8000

### Docker Make Commands

```sh
# Install Tailwind CSS dependencies
make tailwind-install

# Start the Tailwind CSS development server
make tailwind-start

# Build Tailwind CSS for production
make tailwind-build

# Watch for changes in Tailwind CSS files
make tailwind-watch
```

## Deployment

### GitHub Setup

1. Create a new GitHub repository:
   ```sh
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/memoria.uy.git
   git push -u origin main
   ```

### DigitalOcean VPS Setup

1. Create a new Droplet on DigitalOcean (recommended: Ubuntu 22.04 LTS).

2. Set up SSH access to your Droplet.

3. Install Docker and Docker Compose on your Droplet:
   ```sh
   # Update package lists
   sudo apt update
   
   # Install required packages
   sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
   
   # Add Docker's official GPG key
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
   
   # Add Docker repository
   sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
   
   # Update package lists again
   sudo apt update
   
   # Install Docker
   sudo apt install -y docker-ce
   
   # Add your user to the docker group
   sudo usermod -aG docker ${USER}
   
   # Install Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/download/v2.18.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

4. Set up a domain name pointing to your DigitalOcean Droplet's IP address.

5. Install Certbot for SSL:
   ```sh
   sudo apt install -y certbot
   ```

6. Generate SSL certificates:
   ```sh
   sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
   ```

7. Copy the certificates to your Nginx SSL directory:
   ```sh
   sudo mkdir -p /path/to/your/project/nginx/ssl
   sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /path/to/your/project/nginx/ssl/cert.pem
   sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /path/to/your/project/nginx/ssl/key.pem
   ```

### Deployment Process

1. Clone your repository on the DigitalOcean Droplet:
   ```sh
   git clone https://github.com/yourusername/memoria.uy.git
   cd memoria.uy
   ```

2. Create a `.env` file with production settings:
   ```sh
   cp .env.example .env
   # Edit the .env file with your production settings
   ```

3. Update the Nginx configuration in `nginx/conf.d` with your domain name.

4. Build and start the Docker containers:
   ```sh
   docker-compose up -d --build
   ```

5. Run migrations and create a superuser:
   ```sh
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   ```

6. Build Tailwind CSS for production:
   ```sh
   docker-compose exec web make tailwind-build
   ```

7. Set up automatic deployment (optional):
   - Create a deployment script
   - Set up GitHub Actions for CI/CD

## Environment Variables

See `.env.example` for a list of required environment variables.

## Project Structure

- `core/` - Main application code
- `memoria/` - Django project settings
- `theme/` - Tailwind CSS configuration
- `nginx/` - Nginx configuration
- `docker-compose.yml` - Docker Compose configuration
- `Dockerfile` - Docker configuration
- `Makefile` - Make commands for Docker
- `Makefile.local` - Make commands for local development