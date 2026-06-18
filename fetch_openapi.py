import urllib.request
import json

url = 'https://retail-mind-ikhi.onrender.com/openapi.json'
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        paths = data.get('paths', {})
        print(f"Successfully downloaded OpenAPI spec. Found {len(paths)} paths.")
        
        with open('openapi_dump.json', 'w') as f:
            json.dump(paths, f, indent=2)
except Exception as e:
    print(f"Failed to fetch openapi.json: {e}")
