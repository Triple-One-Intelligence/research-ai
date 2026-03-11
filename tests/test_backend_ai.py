"""
Test script: Backend → AI service integratie test
"""

import json
import sys
import urllib.error
import urllib.request
import ssl

# Backend API URL via Caddy reverse proxy (HTTPS voor lokale development)
BACKEND_URL = "https://localhost:8443/api"

# SSL context om self-signed certificaten te accepteren (alleen voor development)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def test_backend_health():
    """Test of de backend API bereikbaar is en correct draait."""
    print("Test 1: Controleer of de backend draait...")
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=5, context=ssl_context) as r:
            data = json.loads(r.read())
            print(f"  OK — {data.get('service')} is actief")
            return True
    except ConnectionRefusedError:
        print("  FOUT — Kan geen verbinding maken met de backend. Draait de API?")
        return False
    except urllib.error.URLError as e:
        print(f"  FOUT — {e.reason}")
        return False


def test_backend_chat_endpoint():
    """
    Test of het /api/chat endpoint werkt (backend → AI service).
    
    """
    print("Test 2: Test /api/chat endpoint (backend -> AI)...")
    payload = json.dumps({
        "model": "llama3.2",
        "messages": [
            {"role": "user", "content": "Zeg hallo in het Nederlands."}
        ],
        "stream": False
    }).encode()
    
    req = urllib.request.Request(
        f"{BACKEND_URL}/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    
    try:
        with urllib.request.urlopen(req, timeout=60, context=ssl_context) as r:
            response = json.loads(r.read())
            if "message" in response:
                content = response["message"].get("content", "")
                print(f"  OK — AI antwoord ontvangen: {content[:100]}...")
                return True
            else:
                print(f"  WAARSCHUWING — Onverwacht response formaat: {response}")
                return False
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  FOUT — HTTPError {e.code}: {error_body}")
        if "model" in error_body and "not found" in error_body:
            print("  INFO — Model bestaat niet. Zorg dat een model beschikbaar is.")
        return False
    except TimeoutError:
        print("  FOUT — Timeout. AI service reageert niet of model laadt nog.")
        return False
    except Exception as e:
        print(f"  FOUT — {e}")
        return False


def test_backend_embed_endpoint():
    """
    Test of het /api/embed endpoint werkt (backend → AI service).

    """
    print("Test 3: Test /api/embed endpoint (backend -> AI)...")
    payload = json.dumps({
        "model": "nomic-embed-text",
        "prompt": "Test embedding"
    }).encode()
    
    req = urllib.request.Request(
        f"{BACKEND_URL}/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as r:
            response = json.loads(r.read())
            if "embedding" in response:
                embedding_len = len(response["embedding"])
                print(f"  OK — Embedding ontvangen (dimensie: {embedding_len})")
                return True
            else:
                print(f"  WAARSCHUWING — Onverwacht response formaat: {response}")
                return False
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  FOUT — HTTPError {e.code}: {error_body}")
        if "model" in error_body and "not found" in error_body:
            print("  INFO — Embedding model bestaat niet.")
        return False
    except TimeoutError:
        print("  FOUT — Timeout. AI service reageert niet.")
        return False
    except Exception as e:
        print(f"  FOUT — {e}")
        return False


def main():
    print("=== Backend AI Connection Test ===\n")
    
    # Test 1: Controleer of backend bereikbaar is
    health_ok = test_backend_health()
    if not health_ok:
        print("\nResultaat: MISLUKT — Backend is niet bereikbaar.")
        print("Zorg dat de containers draaien met: wsl make up")
        sys.exit(1)
    
    # Test 2 & 3: Test AI endpoints
    chat_ok = test_backend_chat_endpoint()
    embed_ok = test_backend_embed_endpoint()
    
    print()
    
    # Evalueer resultaten
    if chat_ok and embed_ok:
        print("Resultaat: GESLAAGD — Backend maakt correct verbinding met de AI service.")
    elif chat_ok or embed_ok:
        print("Resultaat: GEDEELTELIJK GESLAAGD — Sommige endpoints werken.")
        if not chat_ok:
            print("  → Chat endpoint faalt (waarschijnlijk geen chat model geïnstalleerd)")
        if not embed_ok:
            print("  → Embed endpoint faalt")
    else:
        print("Resultaat: MISLUKT — Backend kan geen verbinding maken met AI service.")
        sys.exit(1)


if __name__ == "__main__":
    main()
