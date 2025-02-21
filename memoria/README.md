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