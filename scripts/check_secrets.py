import json
import sys
import re
import os

SENSITIVE_KEYS = [
    "GOOGLE_API_KEY",
    "CURSOR_API_KEY",
    "GITHUB_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "STRIPE_SECRET_KEY",
    "DATABASE_URL",
    "PASSWORD",
    "SECRET",
    "KEY",
]

# Patterns that look like API keys
KEY_PATTERNS = [
    r"AIza[0-9A-Za-z-_]{35}",  # Google API Key
    r"key_[0-9a-f]{64}",       # Cursor-like API Key
    r"sk-[0-9A-Za-z]{48}",     # OpenAI-like API Key
    r"(?i)password\s*[:=]\s*['\"][^'\"]+['\"]", # Password pattern
    r"(?i)api_key\s*[:=]\s*['\"][^'\"]+['\"]",  # API Key pattern
]

def check_file(filepath):
    # Skip directories and certain file types
    if not os.path.isfile(filepath):
        return True
    
    # Skip .env and other ignored files if they are somehow passed
    if any(ignored in filepath for ignored in [".env", ".git/", "node_modules/", "venv/", "__pycache__/"]):
        return True

    print(f"Checking {filepath} for secrets...")
    try:
        # For JSON files, we can be more specific
        if filepath.endswith(".json"):
            with open(filepath, 'r') as f:
                try:
                    data = json.load(f)
                    return check_dict(data, filepath)
                except json.JSONDecodeError:
                    # Fallback to regex if JSON is invalid
                    pass
        
        # General regex check for all files
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
            
        success = True
        for pattern in KEY_PATTERNS:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Basic heuristic: ignore placeholders
                match_str = match.group(0).lower()
                if any(placeholder in match_str for placeholder in ["placeholder", "your_", "example", "guest", "postgres", "localhost", "127.0.0.1", "minioadmin"]):
                    continue
                
                print(f"Error: Found potential secret matching pattern in {filepath}: {match.group(0)}")
                success = False
        return success
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return True

def check_dict(d, filepath, prefix=""):
    success = True
    if isinstance(d, dict):
        for k, v in d.items():
            current_key = f"{prefix}.{k}" if prefix else k
            # Check key name
            for skey in SENSITIVE_KEYS:
                if skey.lower() in k.lower():
                    # If it's a known sensitive key, it must be empty or a placeholder
                    if v and not any(placeholder in str(v).lower() for placeholder in ["placeholder", "your_", "example", "guest", "postgres", "localhost", "127.0.0.1", "minioadmin"]):
                        print(f"Error: Found potential secret in {filepath}: key '{current_key}' has value '{v}'")
                        success = False
            
            # Check value patterns
            if isinstance(v, str):
                for pattern in KEY_PATTERNS:
                    if re.search(pattern, v):
                        print(f"Error: Found potential secret matching pattern {pattern} in {filepath} at '{current_key}'")
                        success = False
            
            # Recurse
            if not check_dict(v, filepath, current_key):
                success = False
    elif isinstance(d, list):
        for i, item in enumerate(d):
            if not check_dict(item, filepath, f"{prefix}[{i}]"):
                success = False
    return success

if __name__ == "__main__":
    files = sys.argv[1:]
    overall_success = True
    for file in files:
        if not check_file(file):
            overall_success = False
    
    if not overall_success:
        print("\nPre-commit check failed: Sensitive information found in configuration files.")
        print("Please move sensitive keys to a .env file (which is git-ignored).")
        sys.exit(1)
    sys.exit(0)
