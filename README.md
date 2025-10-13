# JAMAC Product Updater

A web application to transform CSV/Excel product data and update WooCommerce products via API.

## Features

- 📊 Support for CSV and Excel (.xlsx, .xls) files
- 🔄 Transform data using YAML/JSON mapping configurations
- 🛒 Direct WooCommerce product updates via REST API
- 📥 Export transformed data as CSV
- 🎨 Clean, modern web interface
- 🔧 Handles trailing whitespace in column names
- 🏷️ Proper formatting for WooCommerce categories, tags, and attributes

## Quick Start with Docker

### Prerequisites

- Docker and Docker Compose installed
- WooCommerce REST API credentials (consumer key and secret)

### Setup

1. **Clone or download this repository**

2. **Create a `.env` file** with your WooCommerce credentials:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
WOOCOMMERCE_URL=https://your-store.com
WOOCOMMERCE_CONSUMER_KEY=ck_your_consumer_key_here
WOOCOMMERCE_CONSUMER_SECRET=cs_your_consumer_secret_here
```

3. **Build and run with Docker Compose**:

```bash
docker-compose up -d
```

4. **Access the application**:

Open your browser to http://localhost:5001

### Docker Commands

```bash
# Start the application
docker-compose up -d

# Stop the application
docker-compose down

# View logs
docker-compose logs -f

# Rebuild after changes
docker-compose up -d --build

# Stop and remove everything
docker-compose down -v
```

## Manual Installation (without Docker)

### Prerequisites

- Python 3.9 or higher
- `uv` package manager (or pip)

### Setup

1. **Install dependencies**:

```bash
uv sync
```

Or with pip:

```bash
pip install -r requirements.txt
```

2. **Create `.env` file** with your WooCommerce credentials (see above)

3. **Run the application**:

```bash
uv run python app.py
```

Or:

```bash
python app.py
```

4. **Access the application** at http://localhost:5001

## Usage

### Mapping Configuration

Edit `mapping.yaml` to define how your input columns map to WooCommerce fields:

```yaml
Categories: Category
SKU: Code
Name:
  - Brand
  - Description
Tags: Tags
# ... more mappings
```

### Uploading Files

1. Upload your CSV or Excel file
2. Choose to use the default mapping or upload a custom one
3. Click "Download CSV" to get transformed data, or "Update WooCommerce" to directly update your store

### WooCommerce API Setup

To get your API credentials:

1. Go to WooCommerce → Settings → Advanced → REST API
2. Click "Add key"
3. Set permissions to "Read/Write"
4. Copy the Consumer Key and Consumer Secret

## Field Mapping

The application handles these WooCommerce-specific fields:

- **Categories**: Comma-separated values converted to category objects
- **Tags**: Comma-separated values converted to tag objects
- **Attributes**: Pairs of "Attribute N name" and "Attribute N value(s)" columns
- **Regular fields**: name, description, short_description, etc.

## Troubleshooting

### WooCommerce Not Connected

Make sure your `.env` file contains valid credentials and the URL is correct (no trailing `/wp-json/wc/v3/`).

### Products Not Found

Ensure the SKU column in your data matches exactly with WooCommerce product SKUs.

### Attribute Errors

Check that your attribute columns follow the pattern:
- `Attribute 1 name` with corresponding `Attribute 1 value(s)`
- `Attribute 2 name` with corresponding `Attribute 2 value(s)`
- etc.

## Development

The application uses:
- Flask for the web framework
- WooCommerce REST API Python library
- Pandas for Excel file handling
- PyYAML for configuration

## License

MIT
