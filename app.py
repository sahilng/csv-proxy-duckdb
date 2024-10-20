import os
import re
import logging
import hashlib
import urllib.parse

from flask import Flask, abort, send_file, request
from datetime import datetime, timedelta
import duckdb

# Configuration
CACHE_DIR = os.environ.get('CACHE_DIR', 'cache')
CACHE_MINUTES = int(os.environ.get('CACHE_MINUTES', 1))  # Convert to integer
DB_PATH = os.environ.get('DB_PATH', 'local.db')
LOG_FILE = os.environ.get('LOG_FILE', 'app.log')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
PORT = int(os.environ.get('PORT', 3500))  # Convert to integer

# Ensure the cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

app = Flask(__name__)

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Hide Flask logs
if LOG_LEVEL != 'DEBUG':
    logging.getLogger('werkzeug').setLevel(logging.CRITICAL)

def is_valid_identifier(name):
    """Validate that the provided name is a valid SQL identifier."""
    return re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name) is not None

def hash_token(token):
    """Hash the token or connection string using SHA-256."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def generate_csv(database: str, schema: str, view: str, connection_string: str, file_path: str) -> bool:
    """
    Generate a CSV file from the specified DuckDB view.

    Args:
        database (str): The database name.
        schema (str): The schema name.
        view (str): The view name.
        connection_string (str): The DuckDB connection string.
        file_path (str): The path where the CSV file will be saved.

    Returns:
        bool: True if CSV generation succeeded, False otherwise.
    """
    if not all(map(is_valid_identifier, [database, schema, view])):
        logging.warning(f"Invalid identifiers provided: {database}, {schema}, {view}")
        return False

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
            
            # Remove the cached file if it exists
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"Removed cached file '{file_path}' due to missing view")

            return False

        # Escape single quotes in file_path to prevent SQL injection
        safe_file_path = file_path.replace("'", "''")

        # Build the query safely
        query = f"COPY (SELECT * FROM \"{database}\".\"{schema}\".\"{view}\") TO '{safe_file_path}' (HEADER, DELIMITER ',');"
        connection.execute(query)
        logging.info(f"CSV generated for view '{database}.{schema}.{view}' at '{file_path}'")
        return True
    except Exception as e:
        logging.error(f"Failed to generate CSV for view '{database}.{schema}.{view}': {e}", exc_info=True)
        return False
    finally:
        if connection:
            connection.close()

@app.route('/<string:database>/<string:schema>/<string:view>.csv')
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
        # URL-encode the token to prevent injection attacks
        encoded_token = urllib.parse.quote(motherduck_token, safe='')
        connection_string = f'md:?motherduck_token={encoded_token}'

        # Hash the token to use in the cache directory path
        token_hash = hash_token(motherduck_token)
    else:
        # Use DB_PATH as the connection string
        connection_string = DB_PATH
        # Hash the DB_PATH to use in the cache directory path
        token_hash = hash_token(DB_PATH)

    # Now token_hash is the top-level directory under CACHE_DIR
    dir_path = os.path.join(CACHE_DIR, token_hash, database, schema)
    os.makedirs(dir_path, exist_ok=True)

    file_name = f"{view}.csv"
    file_path = os.path.join(dir_path, file_name)

    # Use file modification time for caching
    file_exists = os.path.exists(file_path)
    is_cached = False

    if file_exists:
        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
        if datetime.now() - file_mtime < timedelta(minutes=CACHE_MINUTES):
            is_cached = True

    if is_cached:
        logging.info(f"Serving cached CSV for view '{database}.{schema}.{view}' with token hash '{token_hash}'")
        return send_file(file_path, mimetype='text/csv', as_attachment=True, download_name=f"{view}.csv")
    else:
        # Generate the latest CSV
        generated_csv = generate_csv(database, schema, view, connection_string, file_path)

        if not generated_csv:
            # If the CSV generation fails, return a 404 error
            abort(404, description="View not found or failed to generate CSV")

        # Serve the CSV
        return send_file(file_path, mimetype='text/csv', as_attachment=True, download_name=f"{view}.csv")

if __name__ == '__main__':
    app.run('0.0.0.0', port=PORT)
