# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

JAMAC Product Updater is a Flask web application that transforms CSV/Excel product data and updates WooCommerce products via REST API. The project has two main components:

1. **csv-mapper.py** - Core transformation engine that maps CSV columns using YAML/JSON configuration files
2. **app.py** - Flask web interface with WooCommerce integration

## Commands

### Development
```bash
# Install dependencies
uv sync

# Run the application
uv run python app.py

# Access at http://localhost:5001
```

### Docker
```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild after changes
docker-compose up -d --build

# Stop
docker-compose down
```

## Architecture

### Data Flow

1. **Transform Mode**: CSV/Excel → csv-mapper.py → Transformed CSV → Download
2. **Update Mode**: CSV/Excel → csv-mapper.py → Transformed CSV → WooCommerce API Update
3. **Backup Mode**: WooCommerce API → CSV backup file

### Key Components

**csv-mapper.py** (Lines 1-165)
- Pure CSV transformation logic with no WooCommerce dependencies
- Handles multiple mapping value types:
  - Simple column mapping: `"source_col"`
  - Column concatenation: `["col1", "col2"]` (space-separated)
  - Advanced concat: `{"concat": ["col1", "col2"], "sep": " "}`
  - Constants: `"key(Some Value)"` or `{"key": "Some Value"}`
- Strips whitespace from column names automatically (lines 78, 130)
- Used as imported module by app.py (lines 22-28)

**app.py** (Lines 1-695)
- Flask web server on port 5001
- Three main routes:
  - `/transform` (line 119): Transform and download CSV
  - `/update-woocommerce` (line 396): Transform and push to WooCommerce
  - `/start-backup` (line 340): Backup WooCommerce products to CSV
- WooCommerce API client initialization (lines 60-75) using python-woocommerce library
- Environment variables loaded from `.env` file (line 19)

### WooCommerce Integration

**Product Lookup** (app.py:577-593)
- Products are looked up by SKU: `GET /products?sku={sku}`
- Response is JSON array of matching products

**Product Update** (app.py:509-574, 642-655)
- Updates use product ID: `PUT /products/{product_id}`
- Special field handling:
  - **Categories**: `[{"name": "Category Name"}]` (lines 524-530)
  - **Tags**: `[{"name": "Tag Name"}]` (lines 531-537)
  - **Attributes**: Paired columns "Attribute N name" and "Attribute N value(s)" converted to `[{"name": "...", "options": [...], "visible": true}]` (lines 538-574)
  - Empty categories/tags are omitted entirely (not sent as empty arrays)
  - Regular fields: snake_case normalized (line 560)

**Dry-Run Mode** (app.py:419, 604-638)
- Compares CSV data against current WooCommerce data
- Text normalization for comparison (lines 85-98): strips HTML tags, decodes entities, normalizes whitespace
- Reports differences without making changes

**Backup** (app.py:233-318)
- Paginated API fetch (100 products per page)
- Background thread with SSE progress updates (lines 320-338)
- Exports: id, sku, name, type, status, prices, stock, descriptions, categories, tags, attributes

### Mapping Configuration

The `mapping.yaml` file defines output column → input column mappings. Key patterns in the default mapping:

- **Attributes**: Use `key()` syntax for constant attribute names (lines 15, 17, 19, 21, 23)
- **Concatenation**: Arrays join with spaces (lines 9-14)
- **Direct mapping**: String values map to source columns (lines 1, 2, 6, etc.)

## Important Implementation Details

### Column Name Handling
The codebase strips whitespace from column names in two places:
- When inferring headers (csv-mapper.py:78)
- When reading each row (csv-mapper.py:130)

This handles trailing spaces in CSV headers (noted in README feature #12).

### WooCommerce API Authentication
Uses WooCommerce REST API v3 with Basic Auth over consumer_key:consumer_secret.
Credentials stored in `.env`:
- `WOOCOMMERCE_URL` (base URL, no /wp-json/wc/v3/)
- `WOOCOMMERCE_CONSUMER_KEY`
- `WOOCOMMERCE_CONSUMER_SECRET`

### Excel Support
Excel files (.xlsx, .xls) are automatically converted to CSV using pandas/openpyxl (app.py:48-58) before transformation.

### Error Handling
- WooCommerce updates collect all errors and show up to 10 at a time (app.py:684)
- Dry-run mode shows all differences as info messages (app.py:674-675)
- Transformation supports `strict` mode to fail on missing columns vs. warn (csv-mapper.py:116-119, 136-139)
