# csv-proxy-duckdb

**csv-proxy-duckdb** is a lightweight Flask-based service designed to serve dynamically generated CSV files from DuckDB query results via a simple HTTP interface. This service is particularly useful for tools that require live data in CSV format, such as mapping or visualization platforms that support CSV links.

## Motivation

Many mapping and data visualization tools can only ingest live data via CSV links, limiting their ability to integrate with databases or more dynamic data sources. This project acts as an intermediary (a "proxy") that enables you to query a DuckDB database and dynamically serve the results as CSVs through a standard web link, keeping your data live and up to date.

## Features

- Dynamically generates CSV files from DuckDB database queries on each request.
- Proxies requests to DuckDB, allowing real-time data to be served in CSV format.
- Supports custom database paths and flexible query structures for different datasets.
- Lightweight, easily deployable using Flask or Docker.
- Ideal for integration with mapping or visualization tools that require live CSV links.
- Supports authentication with a `motherduck_token` query parameter for secure access to remote DuckDB databases.
- Custom database path defaults to a local DuckDB file if no token is provided.
- Rate limiting and input validation for enhanced security.

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/DoSomething/csv-proxy-duckdb.git
   cd csv-proxy-duckdb
   ```

2. **Create and activate a virtual environment**:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The application can be customized using environment variables:

- `CACHE_DIR`: Directory to store temporary CSV files (default: `cache`).
- `DB_PATH`: Path to your DuckDB database file (default: `local.db`).
- `LOG_FILE`: File to write logs to (default: `app.log`).
- `LOG_LEVEL`: Logging level \[`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`\] (default: `INFO`).

### Setting Environment Variables

```bash
export DB_PATH=/path/to/your/database.db
export LOG_LEVEL=DEBUG
```

## Usage

### Running the Server

Start the Flask server:

```bash
python app.py
```

### Example URL Usage

Once the server is running, you can request CSV data by accessing URLs like the following:

```
http://localhost:3500/<database>/<schema>/<view>.csv
```

Where:

- `<database>` is the name of the database.
- `<schema>` is the schema.
- `<view>` is the view or table you want to query.

For example:

```
http://localhost:3500/local/main/test.csv
```

### Using `motherduck_token` for Authentication

If you need to access MotherDuck using a `motherduck_token`, append the token to the URL as a query parameter:

```
http://localhost:3500/local/main/test.csv?motherduck_token=your_token_here
```

### Testing with `curl`

Retrieve a CSV without authentication:

```bash
curl -O http://localhost:3500/local/main/test.csv
```

Retrieve a CSV with `motherduck_token`:

```bash
curl -O "http://localhost:3500/local/main/test.csv?motherduck_token=your_token_here"
```

## CORS

Cross-Origin Resource Sharing (CORS) is enabled by default to allow cross-origin access. Configure the allowed origins based on your security requirements.

## Security Considerations

- **Input Validation**: Prevents SQL injection and directory traversal attacks.
- **Rate Limiting**: Protects against denial-of-service attacks.
- **Authentication**: Secure access to remote DuckDB databases with `motherduck_token`.
- **Recommendations**:
  - Use HTTPS in production.
  - Secure environment variables and secrets.
  - Restrict access using firewall rules.

## Docker Deployment

### Build the Docker Image

```bash
docker build -t csv-proxy-duckdb .
```

### Run the Docker Container

```bash
docker run -d -p 3500:3500 \
  --name csv-proxy-duckdb \
  csv-proxy-duckdb
```

### Passing Environment Variables

```bash
docker run -d -p 3500:3500 \
  -e DB_PATH=/app/local.db \
  -e LOG_LEVEL=DEBUG \
  --name csv-proxy-duckdb \
  csv-proxy-duckdb
```

## AI Disclaimer

This code was generated with the assistance of `gpt-4o` and `o1-preview`.
