import os
import uuid
import re
import logging

from flask import Flask, abort, send_file, request, after_this_request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import duckdb

# Configuration
CACHE_DIR = os.environ.get('CACHE_DIR', 'cache')
DB_PATH = os.environ.get('DB_PATH', 'local.db')
LOG_FILE = os.environ.get('LOG_FILE', 'app.log')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
PORT = os.environ.get('PORT', 3500)

# Ensure the cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

app = Flask(__name__)

# Set up rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["2000 per day", "500 per hour"]
)

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def is_valid_identifier(name):
    """Validate that the provided name is a valid SQL identifier."""
    return re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name) is not None

def generate_csv(database: str, schema: str, view: str, connection_string: str) -> str:
    """
    Generate a CSV file from the specified DuckDB view.

    Args:
        database (str): The database name.
        schema (str): The schema name.
        view (str): The view name.
        connection_string (str): The DuckDB connection string.

    Returns:
        str: The path to the generated CSV file, or None if generation failed.
    """
    if not all(map(is_valid_identifier, [database, schema, view])):
        logging.warning(f"Invalid identifiers provided: {database}, {schema}, {view}")
        return None

    logging.info(f"Generating CSV for view '{database}.{schema}.{view}'")

    # Ensure directory for the file exists
    dir_path = os.path.join(CACHE_DIR, database, schema)
    os.makedirs(dir_path, exist_ok=True)

    # Use a unique file name
    file_name = f"{view}_{uuid.uuid4().hex}.csv"
    file_path = os.path.join(dir_path, file_name)

    connection = None
    try:
        # Connect to DuckDB
        connection = duckdb.connect(connection_string)

        # Ensure the view exists
        check_query = """
            SELECT 1 FROM information_schema.tables
            WHERE table_catalog = ? AND table_schema = ? AND table_name = ? LIMIT 1;
        """
        result = connection.execute(check_query, [database, schema, view]).fetchone()
        if not result:
            logging.warning(f"View '{database}.{schema}.{view}' does not exist")
            return None

        # Build the query safely
        query = f"COPY (SELECT * FROM \"{database}\".\"{schema}\".\"{view}\") TO '{file_path}' (HEADER, DELIMITER ',');"
        connection.execute(query)
        logging.info(f"CSV generated for view '{database}.{schema}.{view}' at '{file_path}'")
        return file_path
    except Exception as e:
        logging.error(f"Failed to generate CSV for view '{database}.{schema}.{view}': {e}")
        return None
    finally:
        if connection:
            connection.close()

@app.route('/<string:database>/<string:schema>/<string:view>.csv')
@limiter.limit("100 per minute")  # Additional per-route rate limit
def download_csv(database: str, schema: str, view: str):
    """
    Flask route to handle CSV download requests.

    Args:
        database (str): The database name from the URL.
        schema (str): The schema name from the URL.
        view (str): The view name from the URL.

    Returns:
        Response: A Flask response object to send the CSV file.
    """
    motherduck_token = request.args.get('motherduck_token')
    if motherduck_token:
        connection_string = f'md:?motherduck_token={motherduck_token}'
    else:
        connection_string = DB_PATH

    # Generate the latest CSV for every request
    file_path = generate_csv(database, schema, view, connection_string)

    if file_path is None:
        # If the CSV generation fails, return a 404 error
        abort(404, description="View not found or failed to generate CSV")

    @after_this_request
    def remove_file(response):
        try:
            os.remove(file_path)
            logging.info(f"Deleted file '{file_path}' after sending")
        except Exception as e:
            logging.error(f"Error deleting file '{file_path}': {e}")
        return response

    # Serve the freshly generated CSV
    return send_file(file_path, mimetype='text/csv', as_attachment=True, download_name=f"{view}.csv")

if __name__ == '__main__':
    app.run('0.0.0.0', port=PORT)