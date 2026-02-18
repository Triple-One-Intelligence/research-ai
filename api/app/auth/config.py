import os
import sys

JWT_SECRET = os.environ.get("JWT_SECRET")

if not JWT_SECRET:
    print("FATAL ERROR: JWT_SECRET is missing from environment variables.", file=sys.stderr)
    sys.exit(1) # Stop the server immediately

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 86400      # 1 day
REFRESH_TOKEN_EXPIRE_SECONDS = 604800    # 7 days

# incoming
SERVER_CREDENTIALS = {}
_user = os.environ.get("SERVER_AUTH_USER", "")
_pass = os.environ.get("SERVER_AUTH_PASS", "")
if _user and _pass:
    SERVER_CREDENTIALS[_user] = _pass

# outgoing
REMOTE_SERVERS = {}
_seen = set()
for key in os.environ:
    if key.startswith("REMOTE_") and key.endswith("_URL"):
        name = key[len("REMOTE_"):-len("_URL")]
        if name in _seen: continue
        _seen.add(name)
        
        REMOTE_SERVERS[name.lower()] = {
            "url": os.environ.get(f"REMOTE_{name}_URL", ""),
            "user": os.environ.get(f"REMOTE_{name}_USER", ""),
            "pass": os.environ.get(f"REMOTE_{name}_PASS", ""),
        }