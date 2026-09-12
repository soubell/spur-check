#!/usr/bin/env python3
"""Direct proxy session test - connects to IPRoyal proxy directly."""
import os, time, random, json, requests
# Load .env automatically if present
_dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.isfile(_dotenv_path):
    with open(_dotenv_path) as f:
        for line in f:
            line=line.strip()
            if line and not line.startswith("#") and "=" in line:
                k,v=line.split("=",1)
                if k not in os.environ:
                    os.environ[k]=v

BASE_PASS = os.environ.get("IPROYAL_PASSWORD", "")
USER = os.environ.get("IPROYAL_USERNAME", "")
HOST = os.environ.get("IPROYAL_HOST", "geo.iproyal.com")
PORT = os.environ.get("IPROYAL_PORT", "11203")

def run_session(sid=None):
    if sid is None:
        sid = ''.join(random.choice('0123456789abcdef') for _ in range(8))

    password = f"{BASE_PASS}_country-jp_city-tokyo_session-{sid}_lifetime-15m"
    proxy_url = f"http://{USER}:{password}@{HOST}:{PORT}"
    start = time.time()
    try:
        res = requests.get(
            "https://ipctx.me/json",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=15
        )
        ms = round((time.time() - start) * 1000)
        data = res.json()
        proxies = data.get("client", {}).get("proxies", [])
        risks = data.get("risks", [])
        tunnels = data.get("tunnels", [])
        clean = (len(proxies) == 0 and len(risks) == 0 and len(tunnels) == 0)
        return {
            "sid": sid,
            "ip": data.get("ip"),
            "org": data.get("organization"),
            "country": data.get("location", {}).get("country"),
            "city": data.get("location", {}).get("city"),
            "isp": data.get("as", {}).get("organization"),
            "ms": ms,
            "clean": clean,
            "proxies": proxies,
            "risks": risks,
            "tunnels": tunnels,
            "password": password
        }
    except Exception as e:
        return {"sid": sid, "error": str(e), "ms": round((time.time()-start)*1000)}

if __name__ == "__main__":
    result = run_session()
    print(json.dumps(result, indent=2, ensure_ascii=False))
