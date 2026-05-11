# UniEvent — Cloud-Hosted University Event Management Platform

A scalable, fault-tolerant web application that aggregates events from the Ticketmaster Discovery API and displays them as official university events. Deployed on AWS using a multi-AZ architecture with private application servers behind an internet-facing Application Load Balancer.

**Course:** CE 308/408 — Cloud Computing  
**Institution:** Ghulam Ishaq Khan Institute of Engineering Sciences and Technology  
**Assignment:** Assignment 1 — Deployment of a Scalable University Event Management System on AWS

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [AWS Services Used](#aws-services-used)
- [External API](#external-api)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Deployment Guide](#deployment-guide)
- [How It Works](#how-it-works)
- [Security](#security)
- [Fault Tolerance](#fault-tolerance)
- [Cost](#cost)
- [Teardown](#teardown)
- [Troubleshooting](#troubleshooting)

---

## Overview

UniEvent lets students browse university events, view event posters, and see structured information about each event. Event data is **not** manually entered — the application automatically fetches events from the Ticketmaster Discovery API every 15 minutes and treats them as official university events.

The system is designed to meet four non-negotiable requirements:

- **High availability** — runs across two Availability Zones
- **Scalability** — Auto Scaling Group automatically adjusts instance count based on load
- **Security** — defense in depth across network, identity, and data layers
- **Fault tolerance** — survives instance failure and Availability Zone failure

---

## Architecture
