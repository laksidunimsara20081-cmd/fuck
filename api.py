import time
import json
import hashlib
import urllib.parse
import asyncio
import random
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, JSONResponse
from datetime import datetime
import httpx

app = FastAPI(
    title="MovieBox Direct API",
    description="Direct scraper & Heroku-Compatible Ultra Proxy Engine",
    version="3.2.2"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://themoviebox.xyz"
H5_API_BASE = "https://h5-api.aoneroom.com/wefeed-h5api-bff"

_bearer_token: str | None = None
_token_expiry: float = 0

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Origin": "https://h5.aoneroom.com",
    "Referer": "https://h5.aoneroom.com/",
    "Content-Type": "application/json",
    "X-Request-Lang": "en",
    "X-Client-Info": '{"timezone":"Asia/Colombo"}',
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Connection": "keep-alive"
}

PLAYER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "video/mp4,video/webm,video/*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://themoviebox.xyz/",
    "Origin": "https://themoviebox.xyz",
    "Sec-Fetch-Dest": "video",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
    "Connection": "keep-alive",
    "X-Client-Info": '{"timezone":"Asia/Colombo"}',
    "X-Source": "moviebox",
    "X-Requested-With": "XMLHttpRequest"
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
]

def get_client_token() -> str:
    timestamp = str(int(time.time()))
    reversed_ts = timestamp[::-1]
    md5_hash = hashlib.md5(reversed_ts.encode('utf-8')).hexdigest()
    return f"{timestamp},{md5_hash}"

def get_headers(referer: str = "https://h5.aoneroom.com/") -> dict:
    token = get_client_token()
    headers = DEFAULT_HEADERS.copy()
    headers["Referer"] = referer
    headers["X-Client-Token"] = token
    headers["x-client-token"] = token
    return headers

async def _get_bearer_token() -> str:
    global _bearer_token, _token_expiry
    
    if _bearer_token and time.time() < _token_expiry:
        return _bearer_token
    
    async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=25) as client:
        try:
            resp = await client.get(f"{H5_API_BASE}/home?host=moviebox.ph", headers=get_headers())
            x_user = resp.headers.get("x-user")
            if x_user:
                _bearer_token = json.loads(x_user).get("token")
                _token_expiry = time.time() + 3600
            if not _bearer_token:
                cookie = resp.headers.get("set-cookie", "")
                import re as _re
                m = _re.search(r"token=([^;]+)", cookie)
                if m:
                    _bearer_token = m.group(1)
                    _token_expiry = time.time() + 3600
        except Exception as e:
            print(f"Bearer token error: {e}")
            pass
    return _bearer_token or ""

def format_size(size_bytes: int) -> str:
    try:
        size_bytes = int(size_bytes)
        if size_bytes <= 0:
            return "N/A"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    except Exception:
        return "N/A"

# 🆕 Encoding fix function
def safe_json_decode(content):
    """Try multiple encodings to decode JSON"""
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16']
    
    if isinstance(content, bytes):
        for encoding in encodings:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        # All failed - return as string with replacement
        return content.decode('utf-8', errors='replace')
    return content

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head>
            <title>MovieBox Direct API</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #121212; color: #fff; text-align: center; padding-top: 50px; }
                h1 { color: #e50914; }
                a { color: #00d2ff; text-decoration: none; }
                a:hover { text-decoration: underline; }
                .container { max-width: 800px; margin: 0 auto; padding: 20px; }
                .status { background: #1e1e1e; padding: 20px; border-radius: 10px; margin-top: 20px; }
                .endpoint { background: #2a2a2a; padding: 10px; border-radius: 5px; margin: 10px 0; font-family: monospace; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎬 MovieBox Direct API</h1>
                <p>Version 3.2.2 - Fixed Encoding</p>
                <div class="status">
                    <h3>📡 API Status: Online</h3>
                    <p>Go to <a href="/docs">/docs</a> to test endpoints</p>
                    <div class="endpoint">GET /search?q=movie_name</div>
                    <div class="endpoint">GET /api/details?detail_path=movie-id</div>
                    <div class="endpoint">GET /api/download-proxy?url=video_url</div>
                </div>
            </div>
        </body>
    </html>
    """

@app.get("/search")
@app.get("/api/search")
async def search_content(q: str = Query(..., description="Search query")):
    url = f"{H5_API_BASE}/subject/search"
    payload = {
        "keyword": q,
        "page": 1,
        "perPage": 30,
        "subjectType": 0
    }
    
    async with httpx.AsyncClient(verify=False, timeout=12) as client:
        try:
            response = await client.post(url, json=payload, headers=get_headers())
            if response.status_code != 200:
                return {"success": False, "error": f"API status code {response.status_code}", "data": []}
            
            # 🆕 Fix encoding
            try:
                data = response.json()
            except UnicodeDecodeError:
                # Try to decode with different encoding
                content = safe_json_decode(response.content)
                data = json.loads(content)
            
            items = data.get("data", {}).get("items", [])
            
            results = []
            for item in items:
                detail_path = item.get("detailPath")
                if not detail_path:
                    continue
                
                cover_url = item.get("cover", {}).get("url", "")
                release_date = item.get("releaseDate", "")
                year = release_date[:4] if release_date else "N/A"
                
                results.append({
                    "title": item.get("title", ""),
                    "link": f"{BASE_URL}/detail/{detail_path}",
                    "image": cover_url,
                    "type": "tvshows" if item.get("subjectType") == 2 else "movies",
                    "quality": "HD",
                    "year": year,
                    "subjectId": item.get("subjectId"),
                    "detailPath": detail_path
                })
            return {"success": True, "total": len(results), "data": results}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

@app.get("/api/details")
@app.get("/detail")
async def get_details(
    request: Request,
    url: str = Query(None, description="Full MovieBox URL or detailPath"),
    detail_path: str = Query(None, description="Direct detailPath (e.g. avatar-123)"),
    se: int = Query(0, description="Season number (0 for Movies)"),
    ep: int = Query(0, description="Episode number (0 for Movies)")
):
    path = detail_path
    if not path and url:
        parsed_url = urllib.parse.urlparse(url)
        path_parts = parsed_url.path.strip("/").split("/")
        if path_parts:
            path = path_parts[-1]

    if not path:
        raise HTTPException(status_code=400, detail="Provide 'url' or 'detail_path'")

    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    base_domain = f"{scheme}://{host}".rstrip("/")

    detail_url = f"{H5_API_BASE}/detail?detailPath={path}"

    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        try:
            r_detail = await client.get(detail_url, headers=get_headers())
            if r_detail.status_code != 200:
                return {"success": False, "error": "Failed to fetch details"}

            # 🆕 Fix encoding for detail response
            try:
                detail_json = r_detail.json()
            except UnicodeDecodeError:
                content = safe_json_decode(r_detail.content)
                detail_json = json.loads(content)
            
            res_data = detail_json.get("data", {})
            subject = res_data.get("subject", {})
            if not subject:
                return {"success": False, "error": "Metadata empty"}

            title = subject.get("title", "")
            story = subject.get("description", "")
            image = subject.get("cover", {}).get("url", "")
            imdb = subject.get("imdbRatingValue", "N/A")
            genres_str = subject.get("genre", "")
            genres = [g.strip() for g in genres_str.split(",") if g.strip()] if genres_str else []
            subject_id = subject.get("subjectId")
            subject_type = subject.get("subjectType")

            req_se = se if subject_type == 2 else 0
            req_ep = ep if subject_type == 2 else 0

            download_url = f"{H5_API_BASE}/subject/download?subjectId={subject_id}&se={req_se}&ep={req_ep}&detailPath={path}"
            
            dl_headers = get_headers("https://videodownloader.site/")
            dl_headers["User-Agent"] = random.choice(USER_AGENTS)
            
            r_play = await client.get(download_url, headers=dl_headers)

            downloads = []
            if r_play.status_code == 200:
                # 🆕 Fix encoding for download response
                try:
                    play_data = r_play.json()
                except UnicodeDecodeError:
                    content = safe_json_decode(r_play.content)
                    play_data = json.loads(content)
                
                play_data = play_data.get("data", {})
                streams = play_data.get("downloads", [])
                captions = play_data.get("captions", [])
                title_suffix = f" (S{req_se}E{req_ep})" if subject_type == 2 else ""

                for s in streams:
                    res = s.get("resolution", "HD")
                    size_str = format_size(s.get("size", 0))
                    original_url = s.get("url", "")
                    if original_url:
                        clean_filename = f"{title}_{res}p.mp4".replace(" ", "_")
                        proxy_link = f"{base_domain}/api/download-proxy?url={urllib.parse.quote(original_url, safe='')}&filename={urllib.parse.quote(clean_filename)}"
                        
                        downloads.append({
                            "title": f"Direct Download {res}p{title_suffix}",
                            "url": proxy_link,
                            "original_url": original_url,
                            "size": size_str,
                            "quality": f"{res}p",
                            "note": "⚠️ If download fails, copy 'original_url' and paste in browser"
                        })

                for sub in captions:
                    sub_lang = sub.get("lanName") or sub.get("lan") or "Unknown"
                    original_sub_url = sub.get("url")
                    sub_size = format_size(sub.get("size", 0))
                    if original_sub_url:
                        clean_sub_file = f"{title}_{sub_lang}.srt".replace(" ", "_")
                        proxy_sub_link = f"{base_domain}/api/download-proxy?url={urllib.parse.quote(original_sub_url, safe='')}&filename={urllib.parse.quote(clean_sub_file)}"
                        downloads.append({
                            "title": f"Subtitle - {sub_lang}{title_suffix}",
                            "url": proxy_sub_link,
                            "original_url": original_sub_url,
                            "size": sub_size,
                            "quality": "SUB"
                        })

            if not downloads:
                trailer_url = subject.get("trailer", {}).get("videoAddress", {}).get("url", "")
                if trailer_url:
                    clean_trailer_file = f"{title}_Trailer.mp4".replace(" ", "_")
                    proxy_trailer = f"{base_domain}/api/download-proxy?url={urllib.parse.quote(trailer_url, safe='')}&filename={urllib.parse.quote(clean_trailer_file)}"
                    downloads.append({
                        "title": "Trailer (MP4)",
                        "url": proxy_trailer,
                        "original_url": trailer_url,
                        "size": "N/A",
                        "quality": "Trailer"
                    })

            cast_list = [
                {
                    "name": star.get("name", ""),
                    "role": star.get("character", "N/A"),
                    "image": star.get("avatarUrl", "")
                }
                for star in res_data.get("stars", [])
            ]

            director_val = "N/A"
            for staff in subject.get("staffList", []):
                if staff.get("staffType") == 2 or "director" in staff.get("job", "").lower():
                    director_val = staff.get("name", "N/A")
                    break

            return {
                "success": True,
                "data": {
                    "title": title,
                    "image": image,
                    "imdb": imdb,
                    "director": director_val,
                    "genres": genres,
                    "story": story,
                    "cast": cast_list,
                    "downloads": downloads,
                    "subjectId": subject_id,
                    "subjectType": subject_type,
                    "detailPath": path
                }
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

# ⚡ Fixed download proxy with better encoding handling
@app.get("/api/download-proxy")
async def download_proxy(request: Request, url: str = Query(...), filename: str = Query("video.mp4")):
    """Enhanced proxy engine with encoding fixes"""
    
    target_url = urllib.parse.unquote(url)
    
    user_agent = random.choice(USER_AGENTS)
    
    proxy_headers = {
        "User-Agent": user_agent,
        "Referer": "https://themoviebox.xyz/",
        "Origin": "https://themoviebox.xyz",
        "Accept": "video/mp4,video/webm,video/*;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "video",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
        "X-Requested-With": "XMLHttpRequest"
    }

    range_header = request.headers.get("range")
    if range_header:
        proxy_headers["Range"] = range_header

    max_retries = 3
    retry_delays = [2, 4, 8]
    
    for attempt in range(max_retries):
        try:
            # 🆕 Use HTTP/1.1 to avoid encoding issues
            async with httpx.AsyncClient(
                verify=False, 
                follow_redirects=True, 
                timeout=httpx.Timeout(20.0, read=120.0),
                http2=False  # Force HTTP/1.1
            ) as client:
                req = client.build_request("GET", target_url, headers=proxy_headers)
                res = await client.send(req, stream=True)
                
                if res.status_code == 429:
                    await res.aclose()
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        await asyncio.sleep(delay)
                        proxy_headers["User-Agent"] = random.choice(USER_AGENTS)
                        continue
                    else:
                        return RedirectResponse(url=target_url, status_code=307)
                
                if res.status_code == 403:
                    await res.aclose()
                    if attempt < max_retries - 1:
                        proxy_headers["Referer"] = "https://www.google.com/"
                        proxy_headers["User-Agent"] = random.choice(USER_AGENTS)
                        await asyncio.sleep(retry_delays[attempt])
                        continue
                    else:
                        return RedirectResponse(url=target_url, status_code=307)
                
                if res.status_code in [200, 206]:
                    async def stream_chunks():
                        try:
                            async for chunk in res.aiter_bytes(chunk_size=65536):
                                yield chunk
                        except Exception as e:
                            print(f"Stream error: {e}")
                        finally:
                            await res.aclose()
                    
                    # 🆕 Better filename handling
                    safe_filename = urllib.parse.quote(filename)
                    # Remove invalid characters
                    clean_filename = filename.replace('"', '').replace("'", "").replace("\n", "")
                    content_disposition = f"attachment; filename=\"{clean_filename}\"; filename*=UTF-8''{safe_filename}"
                    
                    response_headers = {
                        "Content-Disposition": content_disposition,
                        "Content-Type": res.headers.get("content-type", "video/mp4"),
                        "Accept-Ranges": "bytes",
                        "Cache-Control": "public, max-age=3600",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Expose-Headers": "Content-Disposition, Content-Length, Content-Range"
                    }
                    
                    for h in ["content-length", "content-range"]:
                        if h in res.headers:
                            response_headers[h] = res.headers[h]
                    
                    return StreamingResponse(
                        stream_chunks(),
                        status_code=res.status_code,
                        headers=response_headers
                    )
                else:
                    await res.aclose()
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delays[attempt])
                        continue
                    else:
                        return RedirectResponse(url=target_url, status_code=307)
                    
        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delays[attempt])
                continue
            else:
                return RedirectResponse(url=target_url, status_code=307)
        except Exception as e:
            print(f"Download proxy error (attempt {attempt}): {e}")
            if attempt == max_retries - 1:
                return RedirectResponse(url=target_url, status_code=307)
            await asyncio.sleep(retry_delays[attempt])
    
    return RedirectResponse(url=target_url, status_code=307)

@app.get("/api/player")
async def video_player(url: str = Query(...)):
    """Video player page with embedded video"""
    target_url = urllib.parse.unquote(url)
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>Video Player</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                * {{ margin: 0; padding: 0; }}
                body {{ background: #000; display: flex; justify-content: center; align-items: center; height: 100vh; }}
                video {{ max-width: 100%; max-height: 100vh; }}
            </style>
        </head>
        <body>
            <video controls autoplay>
                <source src="{target_url}" type="video/mp4">
                <p>Your browser doesn't support HTML5 video. <a href="{target_url}">Download directly</a></p>
            </video>
        </body>
    </html>
    """)

@app.get("/api/health")
async def health():
    return {
        "status": "ok", 
        "service": "MovieBox Official API", 
        "version": "3.2.2",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "proxy_engine": "enhanced",
            "retry_logic": "enabled",
            "rate_limit_handling": "enabled",
            "user_agent_rotation": "enabled",
            "encoding_fix": "enabled"
        }
    }

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "Endpoint not found",
            "available_endpoints": [
                "/",
                "/docs",
                "/search",
                "/api/search",
                "/api/details",
                "/api/download-proxy",
                "/api/player",
                "/api/health"
            ]
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
