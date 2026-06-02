from gdeltdoc import GdeltDoc, Filters
from gdeltdoc.errors import RateLimitError
import socket
import datetime

# global socket timeout for connect/read operations
socket.setdefaulttimeout(30)  # 30 second timeout

dat = Filters(
    keyword="conflict",
    start_date=datetime.datetime(2020, 5, 10, 0, 0, 0),
    end_date=datetime.datetime(2020, 5, 10, 0, 30, 0),
)

def dns_check(hostname="api.gdeltproject.org"):
    try:
        print(f"Resolving {hostname}...")
        infos = socket.getaddrinfo(hostname, None)
        print(f"DNS OK: {len(infos)} records")
    except Exception as e:
        print(f"DNS resolution failed: {type(e).__name__}: {e}")


def dump_response(resp):
    try:
        status = getattr(resp, 'status_code', None)
        reason = getattr(resp, 'reason', None)
        headers = getattr(resp, 'headers', None)
        text = getattr(resp, 'text', None)
        print(f"Response status: {status} {reason}")
        if headers:
            try:
                print("Response headers:", dict(headers))
            except Exception:
                print("Response headers (raw):", headers)
        if text:
            snippet = text if len(text) <= 2000 else text[:2000] + "... (truncated)"
            print("Response body (snippet):")
            print(snippet)
        else:
            content = getattr(resp, 'content', None)
            if content is not None:
                print(f"Response content length: {len(content)} bytes")
    except Exception as ex:
        print(f"Failed to dump response: {type(ex).__name__}: {ex}")


gd = None

try:
    dns_check()
    print("Connecting to GDELT API client...")
    gd = GdeltDoc()
except Exception as e:
    print(f"Client init error: {type(e).__name__}: {e}")
    gd = None

if gd is None:
    print("GdeltDoc client not available — aborting.")
else:
    try:
        print("Executing single query...")
        results = gd.article_search(dat)
        print("Success!")
        print(results)
    except RateLimitError as e:
        print(f"RateLimitError: {e}.")
        resp = getattr(e, 'response', None)
        if resp is not None:
            dump_response(resp)
        else:
            print("No response object attached to RateLimitError.")
    except socket.timeout:
        print("socket.timeout: the network connection exceeded the 30 second limit.")
    except Exception as e:
        print(f"Error ({type(e).__name__}): {e}")
        resp = getattr(e, 'response', None)
        if resp is not None:
            dump_response(resp)
