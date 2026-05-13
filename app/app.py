"""
UniEvent - University Event Management System
Flask application that fetches events from Ticketmaster Discovery API
and displays them as "University Events" on the UniEvent platform.
"""

import os
import socket
from datetime import datetime
from flask import Flask
import requests
import boto3
from botocore.exceptions import ClientError

app = Flask(__name__)

TICKETMASTER_API_KEY = os.environ.get("TM_KEY", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
TICKETMASTER_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

s3 = boto3.client("s3") if S3_BUCKET else None


def fetch_events(size=12):
    params = {"apikey": TICKETMASTER_API_KEY, "size": size}
    response = requests.get(TICKETMASTER_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json().get("_embedded", {}).get("events", [])


def cache_poster_to_s3(event_id, image_url):
    if not s3 or not image_url:
        return None
    key = f"posters/{event_id}.jpg"
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        return key
    except ClientError:
        pass
    img = requests.get(image_url, timeout=10).content
    s3.put_object(
        Bucket=S3_BUCKET, Key=key, Body=img,
        ContentType="image/jpeg", ServerSideEncryption="AES256",
    )
    return key


def render_page(events):
    hostname = socket.gethostname()
    cards = []
    for event in events:
        name = event.get("name", "Untitled Event")
        date = event.get("dates", {}).get("start", {}).get("localDate", "TBA")
        venues = event.get("_embedded", {}).get("venues", [{}])
        venue = venues[0].get("name", "TBA") if venues else "TBA"
        city = venues[0].get("city", {}).get("name", "") if venues else ""
        images = event.get("images", [])
        image_url = images[0].get("url", "") if images else ""
        category = (event.get("classifications", [{}])[0]
                    .get("segment", {}).get("name", "Event"))
        url = event.get("url", "#")

        if S3_BUCKET and image_url:
            try:
                cache_poster_to_s3(event.get("id", ""), image_url)
            except Exception:
                pass

        cards.append(f"""
        <article class="card">
          <div class="card-image" style="background-image:url('{image_url}')">
            <span class="badge">{category}</span>
          </div>
          <div class="card-body">
            <h3 class="card-title">{name}</h3>
            <div class="meta">
              <div class="meta-row">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                <span>{date}</span>
              </div>
              <div class="meta-row">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                <span>{venue}{', ' + city if city else ''}</span>
              </div>
            </div>
            <a class="card-link" href="{url}" target="_blank" rel="noopener">View Details →</a>
          </div>
        </article>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>UniEvent · Official University Events Portal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:wght@700;900&display=swap" rel="stylesheet">
  <style>
    *,*::before,*::after {{ box-sizing:border-box; margin:0; padding:0; }}
    :root {{
      --bg:#0a0e27; --bg2:#141937; --card:#1a1f3a;
      --text:#e8eaf6; --muted:#8b92b8;
      --accent:#7c3aed; --accent2:#ec4899; --gold:#fbbf24;
      --radius:16px;
    }}
    body {{
      font-family:'Inter',system-ui,-apple-system,sans-serif;
      background:var(--bg); color:var(--text);
      min-height:100vh; line-height:1.5;
    }}

    /* Header / hero */
    header {{
      position:relative; padding:80px 24px 100px; text-align:center;
      background:radial-gradient(ellipse at top,#2d1b69 0%,#0a0e27 60%);
      overflow:hidden;
    }}
    header::before {{
      content:''; position:absolute; inset:0;
      background:
        radial-gradient(circle at 20% 30%,rgba(124,58,237,.3) 0,transparent 40%),
        radial-gradient(circle at 80% 70%,rgba(236,72,153,.25) 0,transparent 40%);
    }}
    .nav {{
      position:relative; display:flex; justify-content:space-between;
      align-items:center; max-width:1200px; margin:0 auto 60px;
    }}
    .logo {{
      display:flex; align-items:center; gap:10px;
      font-family:'Playfair Display',serif; font-size:1.6rem; font-weight:900;
      background:linear-gradient(135deg,var(--gold),var(--accent2));
      -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    }}
    .logo-mark {{
      width:36px; height:36px; border-radius:10px;
      background:linear-gradient(135deg,var(--accent),var(--accent2));
      display:grid; place-items:center; color:#fff;
      font-family:'Inter',sans-serif; font-size:1.1rem; font-weight:800;
      box-shadow:0 8px 24px rgba(124,58,237,.4);
    }}
    .nav-links {{ display:flex; gap:32px; color:var(--muted); font-weight:500; font-size:.95rem; }}
    .nav-links a {{ color:inherit; text-decoration:none; transition:color .2s; }}
    .nav-links a:hover {{ color:var(--text); }}
    .hero {{ position:relative; max-width:900px; margin:0 auto; }}
    .hero-tag {{
      display:inline-block; padding:6px 16px; border-radius:999px;
      background:rgba(124,58,237,.15); border:1px solid rgba(124,58,237,.3);
      color:#c4b5fd; font-size:.85rem; font-weight:600; margin-bottom:24px;
    }}
    h1 {{
      font-family:'Playfair Display',serif;
      font-size:clamp(2.5rem,6vw,4.5rem); font-weight:900;
      line-height:1.1; margin-bottom:20px; letter-spacing:-.02em;
    }}
    h1 .accent {{
      background:linear-gradient(135deg,var(--gold) 0%,var(--accent2) 100%);
      -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    }}
    .subtitle {{
      font-size:1.15rem; color:var(--muted); max-width:600px;
      margin:0 auto 32px;
    }}
    .stats {{
      display:flex; justify-content:center; gap:48px; margin-top:40px;
      flex-wrap:wrap;
    }}
    .stat {{ text-align:center; }}
    .stat-num {{
      font-family:'Playfair Display',serif; font-size:2.2rem; font-weight:900;
      background:linear-gradient(135deg,var(--gold),var(--accent2));
      -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    }}
    .stat-label {{ color:var(--muted); font-size:.85rem; text-transform:uppercase; letter-spacing:.1em; }}

    /* Main */
    main {{ max-width:1280px; margin:-40px auto 0; padding:0 24px 80px; position:relative; }}
    .section-head {{
      display:flex; justify-content:space-between; align-items:end;
      margin-bottom:32px; flex-wrap:wrap; gap:16px;
    }}
    .section-head h2 {{
      font-family:'Playfair Display',serif; font-size:2rem; font-weight:700;
    }}
    .section-head p {{ color:var(--muted); }}
    .filter {{
      display:flex; gap:8px; flex-wrap:wrap;
    }}
    .chip {{
      padding:8px 16px; border-radius:999px; background:var(--card);
      border:1px solid rgba(255,255,255,.08); color:var(--muted);
      font-size:.85rem; font-weight:500; cursor:pointer;
    }}
    .chip.active {{
      background:linear-gradient(135deg,var(--accent),var(--accent2));
      color:#fff; border-color:transparent;
    }}

    /* Grid */
    .grid {{
      display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
      gap:24px;
    }}
    .card {{
      background:var(--card); border-radius:var(--radius);
      overflow:hidden; transition:transform .3s,box-shadow .3s;
      border:1px solid rgba(255,255,255,.06);
      display:flex; flex-direction:column;
    }}
    .card:hover {{
      transform:translateY(-6px);
      box-shadow:0 24px 60px rgba(124,58,237,.25);
      border-color:rgba(124,58,237,.4);
    }}
    .card-image {{
      height:200px; background-size:cover; background-position:center;
      background-color:#2d1b69; position:relative;
    }}
    .card-image::after {{
      content:''; position:absolute; inset:0;
      background:linear-gradient(to top,rgba(26,31,58,.9),transparent 60%);
    }}
    .badge {{
      position:absolute; top:14px; left:14px; z-index:2;
      padding:5px 12px; border-radius:999px;
      background:rgba(10,14,39,.8); backdrop-filter:blur(8px);
      color:var(--gold); font-size:.75rem; font-weight:700;
      text-transform:uppercase; letter-spacing:.08em;
    }}
    .card-body {{ padding:20px 22px 22px; display:flex; flex-direction:column; flex:1; }}
    .card-title {{
      font-size:1.15rem; font-weight:700; line-height:1.35;
      margin-bottom:14px; min-height:3em;
      display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
      overflow:hidden;
    }}
    .meta {{ display:flex; flex-direction:column; gap:8px; margin-bottom:16px; flex:1; }}
    .meta-row {{
      display:flex; align-items:center; gap:10px;
      color:var(--muted); font-size:.9rem;
    }}
    .meta-row svg {{ width:16px; height:16px; flex-shrink:0; color:var(--accent2); }}
    .card-link {{
      align-self:flex-start; padding:10px 18px; border-radius:10px;
      background:linear-gradient(135deg,var(--accent),var(--accent2));
      color:#fff; text-decoration:none; font-weight:600; font-size:.9rem;
      transition:opacity .2s,transform .2s;
    }}
    .card-link:hover {{ opacity:.9; transform:translateX(2px); }}

    /* Footer */
    footer {{
      border-top:1px solid rgba(255,255,255,.06); padding:40px 24px;
      text-align:center; color:var(--muted); font-size:.85rem;
    }}
    footer code {{
      background:var(--card); padding:2px 8px; border-radius:6px;
      font-family:ui-monospace,SFMono-Regular,monospace; color:var(--gold);
    }}
    .empty {{
      text-align:center; padding:60px; color:var(--muted);
    }}
  </style>
</head>
<body>
  <header>
    <nav class="nav">
      <div class="logo">
        <span class="logo-mark">U</span>UniEvent
      </div>
      <div class="nav-links">
        <a href="#events">Events</a>
        <a href="#">Calendar</a>
        <a href="#">Societies</a>
        <a href="#">About</a>
      </div>
    </nav>
    <div class="hero">
      <span class="hero-tag">✨ Official University Events Portal</span>
      <h1>Discover Your<br><span class="accent">Campus Experience</span></h1>
      <p class="subtitle">
        From society recruitment drives to annual festivals, never miss a moment.
        Curated live events streamed directly from our partner network.
      </p>
      <div class="stats">
        <div class="stat"><div class="stat-num">{len(events)}+</div><div class="stat-label">Live Events</div></div>
        <div class="stat"><div class="stat-num">24/7</div><div class="stat-label">Availability</div></div>
        <div class="stat"><div class="stat-num">∞</div><div class="stat-label">Memories</div></div>
      </div>
    </div>
  </header>

  <main id="events">
    <div class="section-head">
      <div>
        <h2>University Events</h2>
        <p>Refreshed live from the official events feed.</p>
      </div>
      <div class="filter">
        <span class="chip active">All</span>
        <span class="chip">This Week</span>
        <span class="chip">Music</span>
        <span class="chip">Sports</span>
        <span class="chip">Arts</span>
      </div>
    </div>

    <div class="grid">
      {''.join(cards) if cards else '<div class="empty">No events available right now. Check back soon.</div>'}
    </div>
  </main>

  <footer>
    Served by <code>{hostname}</code> · UTC {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} ·
    Built on AWS — VPC · EC2 · ALB · S3 · IAM
  </footer>
</body>
</html>"""


@app.route("/")
def home():
    try:
        events = fetch_events()
        return render_page(events)
    except Exception as ex:
        return f"<h1>UniEvent</h1><p>Could not load events: {ex}</p>", 200


@app.route("/health")
def health():
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
