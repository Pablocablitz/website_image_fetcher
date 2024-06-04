import os
import numpy as np
import imageio
import googlemaps
from sentinelhub import (
    CRS,
    BBox,
    DataCollection,
    MimeType,
    SentinelHubRequest,
    bbox_to_dimensions,
    SHConfig,
    MosaickingOrder
)
from PIL import Image, ImageDraw
from datetime import datetime

# Sentinel Hub configuration
config = SHConfig()
config.sh_client_id = '38eaf371-ff5a-4a0e-be00-a23a3d3d8e95'
config.sh_client_secret = '89QJeKGQ7lnUsYk1nfWdiUPyJoCHd5nm'
config.sh_base_url = 'https://sh.dataspace.copernicus.eu'

IMAGE_DIR = '/home/eouser/miniconda3/envs/my_ML/Website/images'

# Ensure the image directory exists
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)
    print(f"Created directory: {IMAGE_DIR}")

def get_bounding_box(location_name):
    """Useful for getting a range of coordinates for a location"""
    gmaps = googlemaps.Client(key="AIzaSyD7S9rejpC8AQJcV4fzN5NKRncGncdrs8U")
    
    # Get place details
    geocode_result = gmaps.geocode(location_name)
    
    if (geocode_result):
        viewport = geocode_result[0]['geometry']['viewport']
        bounding_box = {
            "north": viewport['northeast']['lat'],
            "south": viewport['southwest']['lat'],
            "east": viewport['northeast']['lng'],
            "west": viewport['southwest']['lng']
        }
        return bounding_box
    else:
        return None

def adjust_bbox_coordinates(bbox, resolution=10, min_size=500, max_size=2500):
    width, height = bbox_to_dimensions(BBox(bbox=bbox, crs=CRS.WGS84), resolution=resolution)
    
    if width < min_size or height < min_size:
        scale_factor = max(min_size / width, min_size / height)
    elif width > max_size or height > max_size:
        scale_factor = min(max_size / width, max_size / height)
    else:
        scale_factor = 1.0

    if scale_factor != 1.0:
        center_lat = (bbox[1] + bbox[3]) / 2
        center_lng = (bbox[0] + bbox[2]) / 2
        half_width = (bbox[2] - bbox[0]) * scale_factor / 2
        half_height = (bbox[3] - bbox[1]) * scale_factor / 2
        
        new_bbox = [
            center_lng - half_width,  # west
            center_lat - half_height, # south
            center_lng + half_width,  # east
            center_lat + half_height  # north
        ]
        return new_bbox
    else:
        return bbox

def get_true_color_image(coords_wgs84, time_interval, output_file='true_color_image.png', resolution=10, brightness_factor=2.0, red_intensity_factor=1.2, green_intensity_factor=1.3, blue_intensity_factor=1.2):
    bbox = BBox(bbox=coords_wgs84, crs=CRS.WGS84)
    bbox_adjusted = adjust_bbox_coordinates(coords_wgs84, resolution=resolution)
    bbox = BBox(bbox=bbox_adjusted, crs=CRS.WGS84)
    
    width, height = bbox_to_dimensions(bbox, resolution=resolution)

    evalscript_true_color = f"""
        //VERSION=3

        function setup() {{
            return {{
                input: [{{
                    bands: ["B02", "B03", "B04"]
                }}],
                output: {{
                    bands: 3
                }}
            }};
        }}

        function evaluatePixel(sample) {{
            return [sample.B04 * {red_intensity_factor}, sample.B03 * {green_intensity_factor}, sample.B02 * {blue_intensity_factor}];
        }}
    """

    request = SentinelHubRequest(
        evalscript=evalscript_true_color,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L1C,
                time_interval=time_interval,
                mosaicking_order=MosaickingOrder.LEAST_CC,
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.PNG)],
        bbox=bbox,
        size=(width, height),
        config=config,
    )

    true_color_imgs = request.get_data()

    if not true_color_imgs:
        raise ValueError("No images returned from the request.")

    image = true_color_imgs[0]

    # Adjust brightness
    image = np.clip(image * brightness_factor, 0, 255).astype(np.uint8)

    # Save the image to a file
    imageio.imwrite(output_file, image)
    print(f"Image saved to {output_file}")  # Log the saved image path

    # Convert the numpy array to a PIL Image for drawing
    pil_image = Image.fromarray(image)
    draw = ImageDraw.Draw(pil_image)

    # Calculate pixel coordinates for the original bounding box
    orig_bbox = BBox(bbox=coords_wgs84, crs=CRS.WGS84)
    orig_width, orig_height = bbox_to_dimensions(orig_bbox, resolution=resolution)
    width_ratio = width / (bbox.max_x - bbox.min_x)
    height_ratio = height / (bbox.max_y - bbox.min_y)

    orig_min_x_pix = int((orig_bbox.min_x - bbox.min_x) * width_ratio)
    orig_max_x_pix = int((orig_bbox.max_x - bbox.min_x) * width_ratio)
    orig_min_y_pix = int((bbox.max_y - orig_bbox.max_y) * height_ratio)
    orig_max_y_pix = int((bbox.max_y - orig_bbox.min_y) * height_ratio)

    # Draw the red square representing the original bounding box
    draw.rectangle([(orig_min_x_pix, orig_min_y_pix), (orig_max_x_pix, orig_max_y_pix)], outline="red", width=3)

    # Save the image with the red square
    pil_image.save(output_file)
    print(f"Image with bounding box saved to {output_file}")  # Log the saved image path

    return output_file

def fetch_images_for_seasons(location_name, year, resolution=10, brightness_factor=2.0, red_intensity_factor=1.2, green_intensity_factor=1.3, blue_intensity_factor=1.2):
    # Clean the location name to make it filesystem-friendly
    location_name_cleaned = "".join(c if c.isalnum() or c in (' ', '.', '_') else '_' for c in location_name).replace(' ', '_')
    
    bounding_box = get_bounding_box(location_name)
    if bounding_box:
        coords_wgs84 = (
            bounding_box["west"], bounding_box["south"],
            bounding_box["east"], bounding_box["north"]
        )

        time_intervals = {
            "Spring": (f"{year}-03-01", f"{year}-05-31"),
            "Summer": (f"{year}-06-01", f"{year}-08-31"),
            "Autumn": (f"{year}-09-01", f"{year}-11-30"),
            "Winter": (f"{year}-12-01", f"{year + 1}-02-28")
        }

        image_paths = {}
        for season, interval in time_intervals.items():
            output_image_path = os.path.join(IMAGE_DIR, f"{location_name_cleaned}_{season.lower()}_{year}.png")
            get_true_color_image(
                coords_wgs84, interval, output_file=output_image_path,
                resolution=resolution, brightness_factor=brightness_factor,
                red_intensity_factor=red_intensity_factor, green_intensity_factor=green_intensity_factor,
                blue_intensity_factor=blue_intensity_factor
            )
            image_paths[season] = output_image_path

        return image_paths
    else:
        return None

def convert_png_to_jpg(png_file_path):
    """
    Converts a PNG image to JPG format.

    :param png_file_path: Path to the PNG image file
    :return: Path to the saved JPG image file
    """
    jpg_file_path = png_file_path.replace('.png', '.jpg')
    
    with Image.open(png_file_path) as img:
        rgb_img = img.convert('RGB')  # Convert to RGB
        rgb_img.save(jpg_file_path, 'JPEG')  # Save as JPG

    return jpg_file_path

if __name__ == "__main__":
    location_name = "New York, USA"
    year = 2023
    images = fetch_images_for_seasons(location_name, year)
    if images:
        for season, path in images.items():
            print(f"{season} image saved at: {path}")
    else:
        print("No images were generated.")