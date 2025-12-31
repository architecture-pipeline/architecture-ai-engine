import os
import requests
from dotenv import load_dotenv

load_dotenv()
stability_key = os.getenv("STABILITY_API_KEY")

input_folder = "images_not_real"
output_folder = "images_realism"
os.makedirs(output_folder, exist_ok=True)

api_url = "https://api.stability.ai/v2beta/stable-image/generate/sd3"
headers = {
    "Authorization": f"Bearer {stability_key}",
    "Accept": "image/*"
}

prompt = (
    "Transform this modular voxel structure into a photorealistic modern apartment building. "
    "Preserve the geometric grid but replace the surfaces with realistic materials such as glass, concrete, and metal. "
    "Add windows, balconies, structural details like mullions, and warm interior lighting. "
    "The result should appear professionally built, sharp, and entirely real — no abstract or toy-like appearance."
)

model = "sd3.5-medium"
strength = 0.85
style = "photographic"

for filename in os.listdir(input_folder):
    if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        continue

    image_path = os.path.join(input_folder, filename)
    print(f"Processing {filename}...")

    try:
        with open(image_path, "rb") as img_file:
            files = {
                "prompt": (None, prompt),
                "model": (None, model),
                "mode": (None, "image-to-image"),
                "strength": (None, str(strength)),
                "output_format": (None, "png"),
                "style_preset": (None, style),
                "image": (filename, img_file, "image/png")
            }

            response = requests.post(api_url, headers=headers, files=files)

        if response.status_code == 200:
            output_path = os.path.join(output_folder, filename)
            with open(output_path, "wb") as out_file:
                out_file.write(response.content)
            print(f"Saved: {output_path}")
        else:
            print(f"Error {response.status_code} for {filename}: {response.text}")

    except Exception as e:
        print(f"Failed to process {filename}: {e}")
