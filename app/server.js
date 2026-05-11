const http = require('http');
const https = require('https');
const os = require('os');

const BUCKET = process.env.S3_BUCKET;
const REGION = process.env.AWS_REGION || 'ap-south-1';

let cachedEvents = [];
let lastFetch = null;

// Read events from S3
function loadEventsFromS3() {
  return new Promise((resolve) => {
    const { execSync } = require('child_process');
    try {
      const json = execSync(
        `aws s3 cp s3://${BUCKET}/data/events-latest.json - --region ${REGION} 2>/dev/null`,
        { encoding: 'utf8' }
      );
      cachedEvents = JSON.parse(json);
      lastFetch = new Date();
      console.log(`Loaded ${cachedEvents.length} events from S3`);
    } catch (e) {
      console.log('No events file in S3 yet (will appear after first fetch)');
    }
    resolve();
  });
}

// Refresh cache every 2 minutes
setInterval(loadEventsFromS3, 120 * 1000);
loadEventsFromS3();

// HTML template
function renderPage(events) {
  const eventCards = events.length === 0
    ? '<p class="empty">No events loaded yet. The fetch service runs every 15 minutes.</p>'
    : events.map(e => `
        <div class="card">
          ${e.image ? `<img src="${e.image}" alt="${e.title}">` : ''}
          <div class="card-body">
            <h3>${e.title}</h3>
            <p class="venue">📍 ${e.venue}, ${e.city}</p>
            <p class="date">📅 ${e.startsAt}</p>
            <p class="desc">${e.description || ''}</p>
          </div>
        </div>
      `).join('');

  return `
<!DOCTYPE html>
<html>
<head>
  <title>UniEvent — University Events</title>
  <meta charset="utf-8">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, sans-serif; background: #f5f7fa; color: #2c3e50; }
    header { background: linear-gradient(135deg, #1a237e, #283593); color: white; padding: 40px 20px; text-align: center; }
    header h1 { font-size: 2.5em; }
    header p { opacity: 0.9; margin-top: 8px; }
    main { max-width: 1200px; margin: -20px auto 40px; padding: 20px; }
    .meta { background: white; padding: 16px; border-radius: 8px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); font-size: 0.9em; color: #546e7a; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
    .card { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08); transition: transform 0.2s; }
    .card:hover { transform: translateY(-4px); }
    .card img { width: 100%; height: 180px; object-fit: cover; }
    .card-body { padding: 16px; }
    .card h3 { color: #1a237e; margin-bottom: 8px; font-size: 1.15em; }
    .venue, .date { color: #546e7a; font-size: 0.9em; margin: 4px 0; }
    .desc { margin-top: 10px; font-size: 0.9em; line-height: 1.4; color: #455a64; }
    .empty { background: white; padding: 40px; text-align: center; border-radius: 12px; color: #78909c; }
    footer { text-align: center; padding: 20px; color: #78909c; font-size: 0.85em; }
  </style>
</head>
<body>
  <header>
    <h1>🎓 UniEvent</h1>
    <p>University Events Platform</p>
  </header>
  <main>
    <div class="meta">
      <strong>${events.length}</strong> events loaded •
      Served by <code>${os.hostname()}</code> •
      Last refresh: ${lastFetch ? lastFetch.toLocaleString() : 'pending'}
    </div>
    <div class="grid">${eventCards}</div>
  </main>
  <footer>UniEvent on AWS — multi-AZ deployment</footer>
</body>
</html>`;
}

// HTTP server
http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('OK');
    return;
  }
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(renderPage(cachedEvents));
}).listen(80, () => console.log('UniEvent server listening on :80'));