import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Datasets live next to this script (backend/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def extract_deep_scheme_details():
    # 1. Open your base dataset
    input_file = os.path.join(BASE_DIR, "myscheme_rag_dataset.json")

    api_key = os.getenv("MYSCHEME_API_KEY")
    if not api_key:
        print("Error: MYSCHEME_API_KEY is not set. Add it to backend/.env.")
        return

    if not os.path.exists(input_file):
        print(f"Error: Could not find '{input_file}'. Make sure it is in the same folder.")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        basic_schemes = json.load(f)

    detailed_dataset = []

    # 2. Your updated headers and the working v6 endpoint
    url = 'https://api.myscheme.gov.in/schemes/v6/public/schemes'

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'x-api-key': api_key,
        'Origin': 'https://www.myscheme.gov.in',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }

    print(f"Loaded {len(basic_schemes)} schemes from {input_file}.")
    print("Starting deep extraction using the v6 endpoint...")

    # 3. Loop through every scheme and fetch its deep details
    for index, scheme in enumerate(basic_schemes):
        fields = scheme.get("fields", {})
        scheme_slug = fields.get("slug")

        if not scheme_slug:
            continue

        params = {
            'slug': scheme_slug,
            'lang': 'en',
        }

        try:
            response = requests.get(url, params=params, headers=headers)

            if response.status_code == 200:
                json_response = response.json()

                # Extract the actual data payload
                payload = json_response.get("data", {})

                # Check for the English ("en") specific data block
                if "en" in payload:
                    scheme_details = payload["en"]
                    scheme_details["slug"] = scheme_slug
                else:
                    scheme_details = payload
                    scheme_details["slug"] = scheme_slug

                detailed_dataset.append(scheme_details)
                print(f"[{index + 1}/{len(basic_schemes)}] Success: Fetched '{scheme_slug}'")

            else:
                print(f"[{index + 1}/{len(basic_schemes)}] Failed on {scheme_slug}. Status: {response.status_code}")
                print(f"Response: {response.text}")

                if response.status_code in [401, 403]:
                    print("API Key expired or blocked! You might need to update the key again.")
                    break

            # Rate limiting: Crucial so you don't get IP banned during the hackathon
            time.sleep(1.5)

        except Exception as e:
            print(f"Error fetching {scheme_slug}: {e}")

    # 4. Save the enriched master RAG database
    output_file = os.path.join(BASE_DIR, "myscheme_deep_rag_dataset_v6.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(detailed_dataset, f, indent=4, ensure_ascii=False)

    print(f"\n✅ Deep scraping complete! Saved {len(detailed_dataset)} scheme files to {output_file}.")


if __name__ == "__main__":
    extract_deep_scheme_details()