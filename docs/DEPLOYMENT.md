# DMS Deployment Guide

## Prerequisites

| Component | Version |
|-----------|---------|
| Ubuntu VPS | 22.04 LTS (minimum 4 vCPU, 8 GB RAM, 100 GB SSD) |
| Python | 3.10+ |
| Node.js | 18+ |
| MariaDB | 10.6+ |
| Redis | 7+ |
| Nginx | 1.24+ |

---

## 1. Backend Deployment (Ubuntu VPS)

### 1.1 Run the setup script

```bash
# Clone this repo on your server
git clone https://github.com/yourorg/dms.git /opt/dms-deploy

# Edit the setup script with your domain
nano /opt/dms-deploy/deploy/setup.sh

# Run as root
chmod +x /opt/dms-deploy/deploy/setup.sh
sudo /opt/dms-deploy/deploy/setup.sh
```

### 1.2 Manual Frappe bench setup (if not using script)

```bash
# Install bench CLI
pip3 install frappe-bench

# Initialize bench (Frappe v15)
bench init ~/frappe-bench --frappe-branch version-15
cd ~/frappe-bench

# Get DMS app
bench get-app dms /path/to/backend/dms

# Create site
bench new-site dms.yourdomain.com \
    --db-name dms_production \
    --admin-password <secure-password>

# Install DMS app
bench --site dms.yourdomain.com install-app dms

# Run migrations
bench --site dms.yourdomain.com migrate

# Set JWT secret in site_config.json
bench --site dms.yourdomain.com set-config jwt_secret "$(openssl rand -base64 32)"

# Enable production mode
bench --site dms.yourdomain.com set-config developer_mode 0
bench setup production frappe
```

### 1.3 Create initial companies and roles

```bash
bench --site dms.yourdomain.com console
```

```python
# In Frappe console:
import frappe

# Create companies
for company in ["Honda", "NEXA", "Jaguar"]:
    doc = frappe.new_doc("DMS Company")
    doc.company_name = company
    doc.company_type = "Automotive"
    doc.brand = company
    doc.is_active = 1
    doc.insert(ignore_permissions=True)

frappe.db.commit()
print("Companies created!")

# Create test users (change passwords before production)
users = [
    ("honda.manager@example.com", "Test@1234", "Honda Manager"),
    ("nexa.user@example.com", "Test@1234", "NEXA User"),
    ("group.admin@example.com", "Test@1234", "Group Admin"),
]
for email, pwd, role in users:
    user = frappe.new_doc("User")
    user.email = email
    user.first_name = email.split("@")[0].replace(".", " ").title()
    user.new_password = pwd
    user.send_welcome_email = 0
    user.append("roles", {"role": role})
    user.insert(ignore_permissions=True)
    
frappe.db.commit()
print("Users created!")
```

### 1.4 Nginx Configuration

```bash
# Copy nginx config
sudo cp /opt/dms-deploy/deploy/nginx.conf /etc/nginx/sites-available/dms

# Edit domain names
sudo nano /etc/nginx/sites-available/dms

# Enable site
sudo ln -sf /etc/nginx/sites-available/dms /etc/nginx/sites-enabled/dms
sudo nginx -t && sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d api.yourdomain.com
```

### 1.5 Supervisor (process management)

```bash
sudo cp /opt/dms-deploy/deploy/supervisor.conf /etc/supervisor/conf.d/frappe-bench.conf
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

---

## 2. Frontend Deployment (Vercel)

### 2.1 Vercel CLI deployment

```bash
cd frontend

# Install dependencies
npm install

# Set environment variables
vercel env add NEXT_PUBLIC_API_URL production
# Enter: https://api.yourdomain.com

# Deploy
vercel --prod
```

### 2.2 Via Vercel Dashboard

1. Connect your GitHub repo to Vercel
2. Set Root Directory: `frontend`
3. Add Environment Variables:
   - `NEXT_PUBLIC_API_URL` = `https://api.yourdomain.com`
   - `NEXT_PUBLIC_APP_NAME` = `DMS`
4. Deploy

### 2.3 Custom domain

In Vercel Dashboard → Project → Settings → Domains:
- Add `app.yourdomain.com`
- Update your DNS: CNAME `app` → `cname.vercel-dns.com`

---

## 3. Environment Variables

### Frontend (.env.local / Vercel)
```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_APP_NAME=DMS
```

### Backend (site_config.json)
```json
{
  "jwt_secret": "<min 32 char random string>",
  "db_password": "<mariadb password>",
  "redis_cache": "redis://127.0.0.1:6379",
  "redis_queue": "redis://127.0.0.1:6380"
}
```

---

## 4. Monitoring

### Health check endpoint

```bash
curl https://api.yourdomain.com/api/method/ping
# Should return: {"message": "pong"}
```

### Log locations

| Log | Path |
|-----|------|
| Gunicorn web | `~/frappe-bench/logs/web.log` |
| Worker | `~/frappe-bench/logs/worker.log` |
| Scheduler | `~/frappe-bench/logs/schedule.log` |
| Nginx access | `/var/log/nginx/dms-api-access.log` |
| Nginx error | `/var/log/nginx/dms-api-error.log` |

### Useful commands

```bash
# Restart all services
sudo supervisorctl restart all

# Check Frappe status
bench status

# Clear cache
bench --site dms.yourdomain.com clear-cache

# Run migrations after update
bench --site dms.yourdomain.com migrate

# Backup database
bench --site dms.yourdomain.com backup --with-files
```

---

## 5. Updating the Application

### Backend update

```bash
cd ~/frappe-bench
bench update --apps dms --no-backup
bench --site dms.yourdomain.com migrate
sudo supervisorctl restart frappe-bench-frappe-web
```

### Frontend update

Push to `main` branch → Vercel auto-deploys (if connected to GitHub)  
Or: `cd frontend && vercel --prod`
