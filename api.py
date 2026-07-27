import time
import hashlib
import urllib.parse
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import httpx

app = FastAPI(
    title="MovieBox Direct API",
    description="Direct scraper for MovieBox official download links (No Third-Party Proxy)",
    version="2.0.0"
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

def get_client_token() -> str:
    """Generate dynamic MD5 authentication token for MovieBox"""
    timestamp = str(int(time.time()))
    reversed_ts = timestamp[::-1]
    md5_hash = hashlib.md5(reversed_ts.encode('utf-8')).hexdigest()
    return f"{timestamp},{md5_hash}"

def get_headers(referer: str = "https://h5.aoneroom.com/") -> dict:
    """Get proper MovieBox headers"""
    token = get_client_token()
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Origin": "https://h5.aoneroom.com",
        "Referer": referer,
        "Content-Type": "application/json",
        "X-Client-Token": token,
        "x-client-token": token,
        "X-Request-Lang": "en",
        "X-Client-Info": '{"timezone":"Asia/Colombo"}'
    }

def format_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
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

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head><title>MovieBox Direct API</title></head>
        <body style="font-family:sans-serif; background:#121212; color:#fff; text-align:center; padding-top:50px;">
            <h1 style="color:#e50914;">🎬 MovieBox Direct API is Running!</h1>
            <p>Go to <a href="/docs" style="color:#00d2ff;">/docs</a> to test endpoints.</p>
        </body>
    </html>
    """

@app.get("/search")
@app.get("/api/search")
async def search_content(q: str = Query(..., description="Search query")):
    """Search Movies & TV Shows"""
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
            
            data = response.json()
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
    url: str = Query(None, description="Full MovieBox URL or detailPath"),
    detail_path: str = Query(None, description="Direct detailPath (e.g. avatar-123)"),
    se: int = Query(1, description="Season number (for TV Shows)"),
    ep: int = Query(1, description="Episode number (for TV Shows)")
):
    """Fetch Metadata & Official Direct Download Links"""
    path = detail_path
    if not path and url:
        parsed_url = urllib.parse.urlparse(url)
        path_parts = parsed_url.path.strip("/").split("/")
        if path_parts:
            path = path_parts[-1]

    if not path:
        raise HTTPException(status_code=400, detail="Provide 'url' or 'detail_path'")

    detail_url = f"{H5_API_BASE}/detail?detailPath={path}"

    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        try:
            r_detail = await client.get(detail_url, headers=get_headers())
            if r_detail.status_code != 200:
                return {"success": False, "error": "Failed to fetch details"}

            res_data = r_detail.json().get("data", {})
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

            # Get Official MovieBox Direct Links
            download_url = f"{H5_API_BASE}/subject/download?subjectId={subject_id}&se={req_se}&ep={req_ep}&detailPath={path}"
            r_play = await client.get(download_url, headers=get_headers("https://videodownloader.site/"))

            downloads = []
            if r_play.status_code == 200:
                play_data = r_play.json().get("data", {})
                streams = play_data.get("downloads", [])
                captions = play_data.get("captions", [])
                title_suffix = f" (S{req_se}E{req_ep})" if subject_type == 2 else ""

                for s in streams:
                    res = s.get("resolution", "HD")
                    size_str = format_size(s.get("size", 0))
                    stream_url = s.get("url", "")
                    if stream_url:
                        downloads.append({
                            "title": f"Direct Download {res}p{title_suffix}",
                            "url": stream_url,
                            "size": size_str,
                            "quality": f"{res}p"
                        })

                for sub in captions:
                    sub_lang = sub.get("lanName") or sub.get("lan") or "Unknown"
                    sub_url = sub.get("url")
                    sub_size = format_size(sub.get("size", 0))
                    if sub_url:
                        downloads.append({
                            "title": f"Subtitle - {sub_lang}{title_suffix}",
                            "url": sub_url,
                            "size": sub_size,
                            "quality": "SUB"
                        })

            # Fallback to Trailer if no downloads
            if not downloads:
                trailer_url = subject.get("trailer", {}).get("videoAddress", {}).get("url", "")
                if trailer_url:
                    downloads.append({
                        "title": "Trailer (MP4)",
                        "url": trailer_url,
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

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "MovieBox Official API", "version": "2.0.0"}
