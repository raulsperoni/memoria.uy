# Running Django Commands with Poetry

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

Make sure you have all the necessary dependencies installed in your Poetry environment before running these commands.

# Working with Tailwind CSS

This project uses [django-tailwind](https://django-tailwind.readthedocs.io/) for integrating Tailwind CSS with Django. The Tailwind configuration is in the `theme` app.

## Using Make Commands

We've added several make commands to simplify working with Tailwind CSS:

### For Docker-based Development (Makefile)

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

### For Local Development (Makefile.local)

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

## Tailwind CSS Configuration

The Tailwind CSS configuration is located in:
- `theme/static_src/tailwind.config.js` - Main configuration file
- `theme/static_src/src/styles.css` - CSS file with Tailwind directives and custom styles

## Development Workflow

1. Start the Django development server: `make -f Makefile.local runserver`
2. In a separate terminal, start the Tailwind CSS watcher: `make -f Makefile.local tailwind-start`
3. Make changes to your HTML templates using Tailwind CSS classes
4. For custom styles or Tailwind configuration changes, edit the files in the `theme` app