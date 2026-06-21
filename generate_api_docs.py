import requests
import json
import sys

URL = "https://retail-mind-vkbp.onrender.com/openapi.json"

def generate_docs():
    print("Fetching OpenAPI spec...")
    resp = requests.get(URL)
    if resp.status_code != 200:
        print("Failed to fetch openapi.json")
        sys.exit(1)
        
    spec = resp.json()
    paths = spec.get("paths", {})
    components = spec.get("components", {}).get("schemas", {})
    
    output = []
    output.append("# 📚 Retail Mind Complete API Documentation")
    output.append("\nThis document contains all 185 available endpoints and their required payload schemas.\n")
    
    # Group by tags/categories
    grouped_endpoints = {}
    
    for path, methods in paths.items():
        for method, details in methods.items():
            tags = details.get("tags", ["General"])
            tag = tags[0]
            if tag not in grouped_endpoints:
                grouped_endpoints[tag] = []
                
            grouped_endpoints[tag].append({
                "path": path,
                "method": method.upper(),
                "summary": details.get("summary", ""),
                "details": details
            })
            
    for tag, endpoints in grouped_endpoints.items():
        output.append(f"## 🔹 {tag}")
        for ep in endpoints:
            output.append(f"### `[{ep['method']}] {ep['path']}`")
            if ep['summary']:
                output.append(f"**Description:** {ep['summary']}")
            
            # Extract request body schema
            req_body = ep['details'].get("requestBody", {})
            if req_body:
                content = req_body.get("content", {})
                json_content = content.get("application/json", {})
                schema_ref = json_content.get("schema", {}).get("$ref", "")
                
                if schema_ref:
                    schema_name = schema_ref.split("/")[-1]
                    schema = components.get(schema_name, {})
                    properties = schema.get("properties", {})
                    required = schema.get("required", [])
                    
                    if properties:
                        output.append("\n**Required Payload Data:**")
                        output.append("| Field | Type | Required | Description |")
                        output.append("|-------|------|----------|-------------|")
                        for prop_name, prop_details in properties.items():
                            is_req = "✅ Yes" if prop_name in required else "❌ No"
                            p_type = prop_details.get("type", "string")
                            p_title = prop_details.get("title", "")
                            output.append(f"| `{prop_name}` | {p_type} | {is_req} | {p_title} |")
                    else:
                        output.append("\n**Payload:** Any valid JSON.")
            
            # Check for path/query parameters
            params = ep['details'].get("parameters", [])
            if params:
                output.append("\n**Parameters (URL/Query):**")
                output.append("| Name | In | Required | Type |")
                output.append("|------|----|----------|------|")
                for p in params:
                    p_name = p.get("name", "")
                    p_in = p.get("in", "")
                    p_req = "✅ Yes" if p.get("required") else "❌ No"
                    p_type = p.get("schema", {}).get("type", "string")
                    output.append(f"| `{p_name}` | {p_in} | {p_req} | {p_type} |")
                    
            output.append("\n---\n")

    with open('api_documentation.md', 'w', encoding='utf-8') as f:
        f.write("\n".join(output))
        
    print("✅ Documentation generated as api_documentation.md")

if __name__ == "__main__":
    generate_docs()
