#!/bin/bash
exec > /var/log/unievent-setup.log 2>&1
set -x

# Install Node.js + AWS CLI v2
dnf install -y nodejs unzip
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
export PATH=$PATH:/usr/local/bin

mkdir -p /opt/unievent

# ============ server.js ============
cat > /opt/unievent/server.js <<'SERVEREOF'
const http = require('http');
const os = require('os');
const { execSync } = require('child_process');

const BUCKET = process.env.S3_BUCKET;
const REGION = process.env.AWS_REGION || 'ap-south-1';

let cachedEvents = [];
let lastFetch = null;

function loadEventsFromS3() {
  try {
    const json = execSync(
      `aws s3 cp s3://${BUCKET}/data/events-latest.json - --region ${REGION} 2>/dev/null`,
      { encoding: 'utf8' }
    );
    cachedEvents = JSON.parse(json);
    lastFetch = new Date();
    console.log(`Loaded ${cachedEvents.length} events from S3`);
  } catch (e) {
    console.log('No events file in S3 yet');
  }
}

setInterval(loadEventsFromS3, 120 * 1000);
loadEventsFromS3();

function renderPage(events) {
  const cards = events.length === 0
    ? '<p class="empty">No events loaded yet. The fetch service runs every 15 minutes.</p>'
    : events.map(e => `
        <div class="card">
          ${e.image ? `<img src="${e.image}" alt="">` : ''}
          <div class="card-body">
            <h3>${e.title}</h3>
            <p class="venue">📍 ${e.venue}, ${e.city}</p>
            <p class="date">📅 ${e.startsAt}</p>
            <p class="desc">${e.description || ''}</p>
          </div>
        </div>`).join('');
  return `<!DOCTYPE html><html><head><title>UniEvent</title><meta charset="utf-8">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,sans-serif;background:#f5f7fa;color:#2c3e50}
header{background:linear-gradient(135deg,#1a237e,#283593);color:#fff;padding:40px 20px;text-align:center}
header h1{font-size:2.5em}
header p{opacity:.9;margin-top:8px}
main{max-width:1200px;margin:-20px auto 40px;padding:20px}
.meta{background:#fff;padding:16px;border-radius:8px;margin-bottom:24px;box-shadow:0 2px 8px rgba(0,0,0,.05);font-size:.9em;color:#546e7a}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:20px}
.card{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);transition:transform .2s}
.card:hover{transform:translateY(-4px)}
.card img{width:100%;height:180px;object-fit:cover}
.card-body{padding:16px}
.card h3{color:#1a237e;margin-bottom:8px;font-size:1.15em}
.venue,.date{color:#546e7a;font-size:.9em;margin:4px 0}
.desc{margin-top:10px;font-size:.9em;line-height:1.4;color:#455a64}
.empty{background:#fff;padding:40px;text-align:center;border-radius:12px;color:#78909c}
footer{text-align:center;padding:20px;color:#78909c;font-size:.85em}
</style></head><body>
<header><h1>🎓 UniEvent</h1><p>University Events Platform</p></header>
<main>
<div class="meta"><strong>${events.length}</strong> events •
Served by <code>${os.hostname()}</code> •
Last refresh: ${lastFetch ? lastFetch.toLocaleString() : 'pending'}</div>
<div class="grid">${cards}</div>
</main>
<footer>UniEvent on AWS — multi-AZ deployment</footer>
</body></html>`;
}

http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, {'Content-Type':'text/plain'});
    res.end('OK');
    return;
  }
  res.writeHead(200, {'Content-Type':'text/html; charset=utf-8'});
  res.end(renderPage(cachedEvents));
}).listen(80, () => console.log('UniEvent listening on :80'));
SERVEREOF

# ============ fetcher.js ============
cat > /opt/unievent/fetcher.js <<'FETCHEREOF'
const https = require('https');
const { execSync } = require('child_process');
const fs = require('fs');
const os = require('os');

const BUCKET = process.env.S3_BUCKET;
const REGION = process.env.AWS_REGION || 'ap-south-1';

function getApiKey() {
  const result = execSync(
    `aws secretsmanager get-secret-value --secret-id unievent/ticketmaster --region ${REGION} --query SecretString --output text`,
    { encoding: 'utf8' }
  );
  return JSON.parse(result).apikey;
}

function tryAcquireLock() {
  const myId = `${os.hostname()}-${Date.now()}`;
  try {
    fs.writeFileSync('/tmp/lock.txt', myId);
    execSync(`aws s3 cp /tmp/lock.txt s3://${BUCKET}/locks/ingestion.lock --region ${REGION}`, { stdio: 'pipe' });
    const remote = execSync(`aws s3 cp s3://${BUCKET}/locks/ingestion.lock - --region ${REGION}`, { encoding: 'utf8' }).trim();
    return remote === myId;
  } catch (e) { return false; }
}

function fetchEvents(apiKey) {
  return new Promise((resolve, reject) => {
    https.get(`https://app.ticketmaster.com/discovery/v2/events.json?countryCode=US&size=20&apikey=${apiKey}`, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try {
          const p = JSON.parse(data);
          const events = (p._embedded?.events || []).map(e => ({
            id: e.id,
            title: e.name,
            startsAt: `${e.dates?.start?.localDate || ''} ${e.dates?.start?.localTime || ''}`.trim(),
            venue: e._embedded?.venues?.[0]?.name || 'TBA',
            city: e._embedded?.venues?.[0]?.city?.name || '',
            description: e.info || e.pleaseNote || '',
            image: (e.images?.find(i => i.ratio === '16_9' && i.width >= 1024) || e.images?.[0])?.url
          }));
          resolve(events);
        } catch (err) { reject(err); }
      });
    }).on('error', reject);
  });
}

async function run() {
  console.log(`[${new Date().toISOString()}] Fetch cycle starting`);
  if (!tryAcquireLock()) { console.log('Lock not acquired, skipping'); return; }
  console.log('Lock acquired');
  const apiKey = getApiKey();
  const events = await fetchEvents(apiKey);
  console.log(`Fetched ${events.length} events`);
  fs.writeFileSync('/tmp/events.json', JSON.stringify(events, null, 2));
  execSync(`aws s3 cp /tmp/events.json s3://${BUCKET}/data/events-latest.json --region ${REGION}`, { stdio: 'pipe' });
  console.log('Uploaded to S3');
}

run().catch(err => { console.error('Failed:', err.message); process.exit(1); });
FETCHEREOF

# ============ systemd: web server ============
cat > /etc/systemd/system/unievent.service <<'EOF'
[Unit]
Description=UniEvent web server
After=network.target

[Service]
Type=simple
Environment=S3_BUCKET=unievent-media-301003368683
Environment=AWS_REGION=ap-south-1
ExecStart=/usr/bin/node /opt/unievent/server.js
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

# ============ systemd: fetcher service + timer ============
cat > /etc/systemd/system/unievent-fetch.service <<'EOF'
[Unit]
Description=Fetch events from Ticketmaster
After=network.target

[Service]
Type=oneshot
Environment=S3_BUCKET=unievent-media-301003368683
Environment=AWS_REGION=ap-south-1
ExecStart=/usr/bin/node /opt/unievent/fetcher.js
User=root
EOF

cat > /etc/systemd/system/unievent-fetch.timer <<'EOF'
[Unit]
Description=Run UniEvent fetcher every 15 minutes

[Timer]
OnBootSec=30s
OnUnitActiveSec=15min
Unit=unievent-fetch.service

[Install]
WantedBy=timers.target
EOF

# Start everything
systemctl daemon-reload
systemctl enable --now unievent.service
systemctl enable --now unievent-fetch.timer

# Trigger the first fetch right away so the page isn't empty
systemctl start unievent-fetch.service