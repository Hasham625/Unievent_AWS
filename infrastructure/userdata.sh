#!/bin/bash
# UniEvent EC2 user-data template.
# deploy.sh substitutes the __PLACEHOLDERS__ before launching instances.
# Installs Python + Flask, drops the app on disk, and registers a systemd
# service so the app survives crashes and reboots (Restart=always).

set -x
exec > /var/log/userdata.log 2>&1

dnf install -y python3 python3-pip
pip3 install flask requests boto3

cat > /opt/app.py <<'APP_PY_EOF'
__APP_PY_PLACEHOLDER__
APP_PY_EOF

cat > /etc/systemd/system/unievent.service <<SVC
[Unit]
Description=UniEvent Flask Application
After=network.target

[Service]
Environment="TM_KEY=__TM_KEY__"
Environment="S3_BUCKET=__S3_BUCKET__"
ExecStart=/usr/bin/python3 /opt/app.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable --now unievent
sleep 3
systemctl status unievent --no-pager || true
curl -s http://localhost/health || true
