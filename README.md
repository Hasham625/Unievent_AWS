---

## Prerequisites

Before deploying, you need:

1. **An AWS account** (new accounts get $100 in free credits)
2. **A Ticketmaster API key** — sign up at https://developer.ticketmaster.com/
3. **AWS region selected** — this guide uses `ap-south-1` (Mumbai); adjust if you prefer another region

---

## Deployment Guide

The full step-by-step deployment is described in the design document. The summary:

### 1. Store the API Key

Create a secret in **AWS Secrets Manager** named `unievent/ticketmaster` with:
```json
{ "apikey": "YOUR_TICKETMASTER_KEY" }
```

### 2. Build the VPC

Use the **VPC Wizard** ("VPC and more"):
- Name: `unievent`
- CIDR: `10.0.0.0/16`
- 2 Availability Zones, 2 public subnets, 2 private subnets
- NAT Gateway: in 1 AZ (cheaper) or 1 per AZ (production)
- S3 Gateway VPC Endpoint: enabled

### 3. Create the S3 Bucket

- Name: `unievent-media-<your-account-id>`
- Block Public Access: **all four boxes ticked**
- Versioning: **enabled**
- Encryption: **SSE-S3**
- Bucket policy: apply `policies/s3-bucket-policy.json` (TLS-only)

### 4. Create the IAM Role

- Role name: `UniEventAppRole`
- Trust: EC2 service
- Policies attached:
  - `AmazonSSMManagedEC2InstanceDefaultPolicy` (AWS managed) — for Session Manager
  - `UniEventAppPolicy` (inline) — from `policies/iam-role-policy.json`

### 5. Create Security Groups

| Name | Inbound | Outbound |
|---|---|---|
| `alb-sg` | HTTP/HTTPS from `0.0.0.0/0` | All traffic to `0.0.0.0/0` |
| `app-sg` | HTTP from `alb-sg` only | All traffic to `0.0.0.0/0` |

> ⚠️ Make sure `app-sg`'s outbound rule allows **all traffic** — instances need to reach AWS APIs, package mirrors, and Ticketmaster.

### 6. Create the Launch Template

- Name: `unievent-template`
- AMI: Amazon Linux 2023 (free tier eligible)
- Instance type: `t3.micro`
- Security group: `app-sg`
- IAM instance profile: `UniEventAppRole`
- User data: paste contents of `user-data.sh`
- Update the `S3_BUCKET` environment variable in the script to match your bucket name

### 7. Create the Application Load Balancer

- **Target group** `unievent-tg`:
  - Protocol: HTTP, Port: 80
  - Health check path: `/health`
  - Healthy threshold: 2, Unhealthy threshold: 3
- **ALB** `unievent-alb`:
  - Scheme: Internet-facing
  - Subnets: both public subnets
  - Security group: `alb-sg`
  - Listener: HTTP:80 → forward to `unievent-tg`

### 8. Create the Auto Scaling Group

- Name: `unievent-asg`
- Launch template: `unievent-template`
- Subnets: both **private** subnets
- Attach to existing load balancer → `unievent-tg`
- Health check type: **EC2, ELB**
- Health check grace period: **120 seconds**
- Desired: 2, Min: 2, Max: 6
- Scaling policy: target tracking, average CPU 50%

### 9. Test

After ~5 minutes:
- Target Group shows 2 **healthy** instances
- Visit the ALB DNS name in a browser → see the UniEvent homepage with real events

---

## How It Works

### Request lifecycle (user-facing)

1. User opens the ALB URL in a browser
2. ALB picks a healthy EC2 instance and forwards the HTTP request
3. EC2 reads cached events from memory; if cache is empty, reads `data/events-latest.json` from S3
4. EC2 renders an HTML page showing event cards (each with poster, title, venue, date)
5. ALB returns the response to the browser

### Background ingestion lifecycle

1. Each EC2 runs a systemd timer (`unievent-fetch.timer`) that triggers every 15 minutes
2. The fetcher attempts to acquire a lock file in S3 (`locks/ingestion.lock`) — only one instance wins
3. The winner:
   - Fetches the Ticketmaster API key from Secrets Manager (via IAM role)
   - Calls `https://app.ticketmaster.com/discovery/v2/events.json` (outbound via NAT Gateway)
   - Normalizes events to the UniEvent schema
   - Writes the result to `s3://<bucket>/data/events-latest.json`
4. Other instances refresh their cache from S3 every 2 minutes and see the new events

### Concurrency control

The S3 lock file prevents multiple instances from calling Ticketmaster simultaneously and burning rate-limit quota. The lock is best-effort (cooperative), which is fine for a 15-minute cycle.

---

## Security

Defense in depth across layers:

**Network layer**
- Application servers in private subnets (no public IPs)
- Security groups deny-by-default
- ALB is the only public ingress point
- S3 traffic uses VPC Gateway Endpoint (never traverses the public internet)

**Identity layer**
- No static AWS credentials on instances — IAM Instance Role only
- Least-privilege policy: only the two S3 prefixes and one Secrets Manager entry the app actually needs
- Session Manager replaces SSH (no port 22 open anywhere)

**Data layer**
- S3 Block Public Access enabled (all four settings)
- S3 default encryption: SSE-S3 (AES-256)
- S3 bucket policy denies any non-TLS request
- S3 versioning enabled (recovers from accidental overwrites)

**Secret layer**
- Ticketmaster API key in AWS Secrets Manager
- Fetched at boot via IAM role — never in source code, AMIs, or environment variables baked into images

---

## Fault Tolerance

| Failure | Behavior |
|---|---|
| One EC2 crashes | ALB health check fails → traffic shifts to surviving instance → ASG launches replacement |
| Entire AZ goes offline | ALB stops routing to that AZ → ASG launches replacements in surviving AZ |
| Ticketmaster API outage | Background fetch fails; app continues serving the last successful events from S3 |
| Bad deployment | ASG instance refresh has built-in rollback if new instances fail health checks |
| Compromised application | Blast radius limited to two S3 prefixes + one secret (IAM least privilege) |

---

## Cost

Approximate monthly costs (Mumbai region, on-demand pricing):

| Component | Cost |
|---|---|
| 2× t3.micro EC2 (24/7) | ~$8 |
| Application Load Balancer | ~$18 |
| 1× NAT Gateway | ~$32 |
| S3 (minimal usage) | <$1 |
| Secrets Manager (1 secret) | $0.40 |
| **Total** | **~$60/month** |

> 💡 New AWS accounts get $100 in credits — more than enough for a 1-week assignment demo. For a one-week deployment with active testing, expect to use ~$15–25 of credits.

---

## Teardown

To avoid unnecessary charges, delete resources in this order:

1. Auto Scaling Group → Delete
2. Load Balancer → Delete
3. Target Group → Delete
4. Launch Template → Delete
5. NAT Gateway → Delete (wait 2 min)
6. Elastic IPs → Release (VPC console)
7. S3 bucket → Empty → Delete
8. Secrets Manager → Schedule deletion (7-day minimum)
9. VPC → Delete VPC
10. IAM role and policies → Delete (optional)
11. (Optional) Close AWS account: root user → Account → Close Account

---

## Troubleshooting

### Targets stuck in "Unhealthy"

1. Verify `app-sg` inbound allows HTTP from `alb-sg`
2. Verify `app-sg` outbound allows **all traffic** (not just port 80)
3. Connect via Session Manager and check `sudo journalctl -u unievent.service`
4. Check `/var/log/unievent-setup.log` for boot script errors

### Session Manager grey / "SSM Agent unable to acquire credentials"

This means the instance has no internet. Check:
1. NAT Gateway state is "Available" and in a **public** subnet
2. Both private route tables have route `0.0.0.0/0 → nat-...`
3. `app-sg` outbound allows all traffic to `0.0.0.0/0`

### Page shows "No events loaded yet"

1. Wait 1–2 minutes for the first fetch cycle
2. Connect to an instance via Session Manager
3. Run: `sudo journalctl -u unievent-fetch.service -n 50`
4. Verify the Secrets Manager secret has key `apikey` (not `key` or `value`)
5. Verify the bucket name in the systemd Environment matches your actual bucket

### Auto Scaling Group keeps launching/terminating instances

Usually means health checks are failing. Check:
1. Target group is attached to the ASG (Integrations tab)
2. `app-sg` inbound rule allows HTTP from `alb-sg`
3. Health check grace period is at least 120 seconds (boot script needs time)

---

## Author

Submitted as part of the CE 308/408 Cloud Computing course at GIKI.

## License

This project is for academic purposes.
