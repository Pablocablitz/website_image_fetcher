from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from PIL import Image
from app2 import fetch_images_for_seasons

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all origins

# Directory where images are saved
IMAGE_DIR = '/home/eouser/miniconda3/envs/my_ML/Website/images'

def compress_image(image_path, output_path, quality=85):
    """Compresses an image and saves it to the specified output path."""
    with Image.open(image_path) as img:
        img.save(output_path, 'JPEG', quality=quality)

@app.route('/fetch_images', methods=['POST'])
def fetch_images():
    app.logger.info("Received request at /fetch_images")
    try:
        data = request.get_json()
        if data is None:
            app.logger.error("No data received in request")
            return jsonify({'error': 'No data received'}), 400

        location_name = data.get('locationName')
        year = data.get('year')
        if not location_name or not year:
            app.logger.error("Missing locationName or year in request")
            return jsonify({'error': 'Missing locationName or year'}), 400

        app.logger.info(f"Fetching images for location: {location_name}, year: {year}")
        image_paths = fetch_images_for_seasons(location_name, int(year))
        
        if not image_paths:
            app.logger.error("Location not found")
            return jsonify({'error': 'Location not found'}), 404
        
        compressed_image_paths = {}
        for season, path in image_paths.items():
            base_name = os.path.basename(path)
            compressed_path = os.path.join(IMAGE_DIR, f"compressed_{base_name}")
            compress_image(path, compressed_path)
            compressed_image_paths[season] = os.path.basename(compressed_path)
            app.logger.info(f"{season} image compressed and saved at {compressed_path}")
        
        app.logger.info(f"Compressed image paths: {compressed_image_paths}")
        response = jsonify(compressed_image_paths)
        app.logger.info(f"Response JSON: {response.get_json()}")
        return response
    except Exception as e:
        app.logger.error(f"Error fetching images: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/images/<path:filename>')
def get_image(filename):
    image_path = os.path.join(IMAGE_DIR, filename)
    app.logger.info(f"Serving image from path: {image_path}")
    if os.path.exists(image_path):
        return send_from_directory(IMAGE_DIR, filename)
    else:
        app.logger.error(f"File not found: {image_path}")
        return jsonify({'error': 'File not found'}), 404

# Test endpoint to check server connection
@app.route('/test', methods=['GET'])
def test():
    return jsonify({'message': 'Server is running'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)  