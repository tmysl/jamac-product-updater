#!/usr/bin/env python3
import os
import tempfile
import csv
import pandas as pd
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from woocommerce import API
from dotenv import load_dotenv
import sys
import importlib.util

# Load environment variables
load_dotenv()

# Import the csv-mapper module
csv_mapper_path = os.path.join(os.path.dirname(__file__), 'csv-mapper.py')
spec = importlib.util.spec_from_file_location("csv_mapper", csv_mapper_path)
csv_mapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csv_mapper)

load_mapping = csv_mapper.load_mapping
transform_csv = csv_mapper.transform_csv

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'yaml', 'yml', 'json'}
DEFAULT_MAPPING_PATH = os.path.join(os.path.dirname(__file__), 'mapping.yaml')

def convert_excel_to_csv(excel_path, csv_path):
    """Convert Excel file to CSV"""
    try:
        # Read the first sheet of the Excel file
        df = pd.read_excel(excel_path, engine='openpyxl')
        # Convert to CSV
        df.to_csv(csv_path, index=False, encoding='utf-8')
        return True
    except Exception as e:
        print(f"Error converting Excel to CSV: {e}")
        return False

def get_woocommerce_api():
    """Initialize WooCommerce API client"""
    url = os.getenv('WOOCOMMERCE_URL')
    consumer_key = os.getenv('WOOCOMMERCE_CONSUMER_KEY')
    consumer_secret = os.getenv('WOOCOMMERCE_CONSUMER_SECRET')

    if not all([url, consumer_key, consumer_secret]):
        return None

    return API(
        url=url,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        version="wc/v3",
        timeout=30
    )

def woocommerce_configured():
    """Check if WooCommerce credentials are configured"""
    return all([
        os.getenv('WOOCOMMERCE_URL'),
        os.getenv('WOOCOMMERCE_CONSUMER_KEY'),
        os.getenv('WOOCOMMERCE_CONSUMER_SECRET')
    ])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_default_mapping_display():
    """Read and return the default mapping file contents for display"""
    try:
        if os.path.exists(DEFAULT_MAPPING_PATH):
            with open(DEFAULT_MAPPING_PATH, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception:
        pass
    return None

@app.route('/')
def index():
    mapping_content = get_default_mapping_display()
    woo_configured = woocommerce_configured()
    return render_template('index.html', default_mapping=mapping_content, woo_configured=woo_configured)

@app.route('/transform', methods=['POST'])
def transform():
    # Check if file is present
    if 'csv_file' not in request.files:
        flash('Input file is required')
        return redirect(url_for('index'))

    input_file = request.files['csv_file']

    # Check if file is selected
    if input_file.filename == '':
        flash('Please select a file')
        return redirect(url_for('index'))

    # Validate file type
    if not allowed_file(input_file.filename):
        flash('File must be CSV or Excel (.csv, .xlsx, .xls)')
        return redirect(url_for('index'))

    try:
        # Save uploaded file
        input_filename = secure_filename(input_file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        input_file.save(input_path)

        # Convert Excel to CSV if needed
        file_ext = input_filename.rsplit('.', 1)[1].lower()
        if file_ext in ['xlsx', 'xls']:
            csv_filename = input_filename.rsplit('.', 1)[0] + '.csv'
            csv_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
            if not convert_excel_to_csv(input_path, csv_path):
                flash('Failed to convert Excel file to CSV')
                return redirect(url_for('index'))
            # Clean up the Excel file
            try:
                os.remove(input_path)
            except:
                pass
        else:
            csv_filename = input_filename
            csv_path = input_path

        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'output_{csv_filename}')


        # Determine which mapping to use
        use_default_mapping = request.form.get('use_default_mapping') == 'on'

        if use_default_mapping:
            # Use the default mapping.yaml
            if not os.path.exists(DEFAULT_MAPPING_PATH):
                flash('Default mapping file not found')
                return redirect(url_for('index'))
            mapping_path = DEFAULT_MAPPING_PATH
            cleanup_mapping = False
        else:
            # Use uploaded mapping file
            if 'mapping_file' not in request.files:
                flash('Mapping file is required when not using default mapping')
                return redirect(url_for('index'))

            mapping_file = request.files['mapping_file']

            if mapping_file.filename == '':
                flash('Please select a mapping file or use default mapping')
                return redirect(url_for('index'))

            if not allowed_file(mapping_file.filename):
                flash('Mapping file must have .yaml, .yml, or .json extension')
                return redirect(url_for('index'))

            mapping_filename = secure_filename(mapping_file.filename)
            mapping_path = os.path.join(app.config['UPLOAD_FOLDER'], mapping_filename)
            mapping_file.save(mapping_path)
            cleanup_mapping = True

        # Get options
        delimiter_in = request.form.get('delimiter_in', ',')
        delimiter_out = request.form.get('delimiter_out', ',')
        strict = 'strict' in request.form

        # Perform transformation
        mapping = load_mapping(mapping_path)
        transform_csv(
            in_path=csv_path,
            out_path=output_path,
            mapping=mapping,
            delimiter_in=delimiter_in,
            delimiter_out=delimiter_out,
            strict=strict
        )

        # Send the output file
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=f'transformed_{csv_filename}',
            mimetype='text/csv'
        )

        # Clean up uploaded files (output will be cleaned after sending)
        try:
            os.remove(csv_path)
            if cleanup_mapping:
                os.remove(mapping_path)
        except:
            pass

        return response

    except Exception as e:
        flash(f'Error processing files: {str(e)}')
        return redirect(url_for('index'))

@app.route('/update-woocommerce', methods=['POST'])
def update_woocommerce():
    """Update WooCommerce products directly via API"""
    if not woocommerce_configured():
        flash('WooCommerce is not configured. Please set up your .env file.')
        return redirect(url_for('index'))

    # Check if file is present
    if 'csv_file' not in request.files:
        flash('Input file is required')
        return redirect(url_for('index'))

    input_file = request.files['csv_file']

    if input_file.filename == '':
        flash('Please select a file')
        return redirect(url_for('index'))

    if not allowed_file(input_file.filename):
        flash('File must be CSV or Excel (.csv, .xlsx, .xls)')
        return redirect(url_for('index'))

    try:
        # Save uploaded file
        input_filename = secure_filename(input_file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        input_file.save(input_path)

        # Convert Excel to CSV if needed
        file_ext = input_filename.rsplit('.', 1)[1].lower()
        if file_ext in ['xlsx', 'xls']:
            csv_filename = input_filename.rsplit('.', 1)[0] + '.csv'
            csv_path = os.path.join(app.config['UPLOAD_FOLDER'], csv_filename)
            if not convert_excel_to_csv(input_path, csv_path):
                flash('Failed to convert Excel file to CSV')
                return redirect(url_for('index'))
            # Clean up the Excel file
            try:
                os.remove(input_path)
            except:
                pass
        else:
            csv_filename = input_filename
            csv_path = input_path

        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'output_{csv_filename}')

        # Determine which mapping to use
        use_default_mapping = request.form.get('use_default_mapping') == 'on'

        if use_default_mapping:
            if not os.path.exists(DEFAULT_MAPPING_PATH):
                flash('Default mapping file not found')
                return redirect(url_for('index'))
            mapping_path = DEFAULT_MAPPING_PATH
            cleanup_mapping = False
        else:
            if 'mapping_file' not in request.files:
                flash('Mapping file is required when not using default mapping')
                return redirect(url_for('index'))

            mapping_file = request.files['mapping_file']

            if mapping_file.filename == '':
                flash('Please select a mapping file or use default mapping')
                return redirect(url_for('index'))

            if not allowed_file(mapping_file.filename):
                flash('Mapping file must have .yaml, .yml, or .json extension')
                return redirect(url_for('index'))

            mapping_filename = secure_filename(mapping_file.filename)
            mapping_path = os.path.join(app.config['UPLOAD_FOLDER'], mapping_filename)
            mapping_file.save(mapping_path)
            cleanup_mapping = True

        # Get options
        delimiter_in = request.form.get('delimiter_in', ',')
        delimiter_out = request.form.get('delimiter_out', ',')
        strict = 'strict' in request.form

        # Perform transformation to get the output data
        mapping = load_mapping(mapping_path)
        transform_csv(
            in_path=csv_path,
            out_path=output_path,
            mapping=mapping,
            delimiter_in=delimiter_in,
            delimiter_out=delimiter_out,
            strict=strict
        )

        # Read the transformed CSV and update WooCommerce
        wcapi = get_woocommerce_api()
        success_count = 0
        error_count = 0
        errors = []

        with open(output_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    # Assuming 'SKU' is the product identifier
                    sku = row.get('SKU', '').strip()
                    if not sku:
                        error_count += 1
                        errors.append(f"Row missing SKU")
                        continue

                    # Build product data from the row with proper WooCommerce formatting
                    product_data = {}
                    attributes = []
                    attribute_pairs = {}  # Store attribute name-value pairs

                    # First pass: collect all fields
                    for key, value in row.items():
                        if key == 'SKU' or not value:
                            continue

                        # Handle special WooCommerce fields that need specific formats
                        if key.lower() == 'categories':
                            # Categories need to be an array of objects with name
                            categories = [cat.strip() for cat in value.split(',') if cat.strip()]
                            product_data['categories'] = [{'name': cat} for cat in categories]
                        elif key.lower() == 'tags':
                            # Tags need to be an array of objects with name
                            tags = [tag.strip() for tag in value.split(',') if tag.strip()]
                            product_data['tags'] = [{'name': tag} for tag in tags]
                        elif 'attribute' in key.lower() and 'name' in key.lower():
                            # Extract attribute number (e.g., "Attribute 1 name" -> "1")
                            import re
                            match = re.search(r'attribute\s*(\d+)', key.lower())
                            if match:
                                attr_num = match.group(1)
                                if attr_num not in attribute_pairs:
                                    attribute_pairs[attr_num] = {}
                                attribute_pairs[attr_num]['name'] = value
                        elif 'attribute' in key.lower() and 'value' in key.lower():
                            # Extract attribute number
                            import re
                            match = re.search(r'attribute\s*(\d+)', key.lower())
                            if match:
                                attr_num = match.group(1)
                                if attr_num not in attribute_pairs:
                                    attribute_pairs[attr_num] = {}
                                # Handle multiple values separated by commas
                                values = [v.strip() for v in value.split(',') if v.strip()]
                                attribute_pairs[attr_num]['options'] = values
                        else:
                            # Regular fields - normalize the key
                            normalized_key = key.lower().replace(' ', '_')
                            product_data[normalized_key] = value

                    # Build attributes array from pairs
                    for attr_num in sorted(attribute_pairs.keys()):
                        attr = attribute_pairs[attr_num]
                        if 'name' in attr and 'options' in attr:
                            attributes.append({
                                'name': attr['name'],
                                'options': attr['options'],
                                'visible': True
                            })

                    if attributes:
                        product_data['attributes'] = attributes

                    # Find product by SKU
                    try:
                        print(f"Looking up product with SKU: {sku}")
                        lookup_response = wcapi.get(f"products?sku={sku}")
                        print(f"Response status: {lookup_response.status_code}")
                        print(f"Response URL: {lookup_response.url}")

                        if lookup_response.status_code != 200:
                            error_count += 1
                            errors.append(f"SKU {sku}: API error {lookup_response.status_code} at {lookup_response.url} - {lookup_response.text[:200]}")
                            continue

                        products = lookup_response.json()
                        print(f"Found {len(products)} products")
                    except Exception as json_err:
                        error_count += 1
                        errors.append(f"SKU {sku}: Failed to parse API response - {str(json_err)}")
                        continue

                    if not products or len(products) == 0:
                        error_count += 1
                        errors.append(f"Product not found with SKU: {sku}")
                        continue

                    product_id = products[0]['id']

                    # Update the product
                    try:
                        result = wcapi.put(f"products/{product_id}", product_data)

                        if result.status_code in [200, 201]:
                            success_count += 1
                        else:
                            error_count += 1
                            try:
                                error_detail = result.json()
                            except:
                                error_detail = result.text[:200]
                            errors.append(f"SKU {sku}: Update failed ({result.status_code}) - {error_detail}")
                    except Exception as update_err:
                        error_count += 1
                        errors.append(f"SKU {sku}: Update request failed - {str(update_err)}")

                except Exception as e:
                    error_count += 1
                    errors.append(f"Unexpected error: {str(e)}")

        # Clean up files
        try:
            os.remove(csv_path)
            os.remove(output_path)
            if cleanup_mapping:
                os.remove(mapping_path)
        except:
            pass

        # Show results
        if success_count > 0:
            flash(f'Successfully updated {success_count} products in WooCommerce!', 'success')

        if error_count > 0:
            flash(f'{error_count} products failed to update.', 'error')
            for error in errors[:10]:  # Show first 10 errors
                flash(error, 'error')

        return redirect(url_for('index'))

    except Exception as e:
        flash(f'Error updating WooCommerce: {str(e)}')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
