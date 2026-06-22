# DMS Production Security Checklist

## Authentication & Authorization

- [x] JWT tokens signed with HS256, minimum 32-char secret
- [x] Access tokens expire in 8 hours
- [x] Refresh tokens expire in 30 days
- [x] JWT secret stored in `site_config.json`, never in source code
- [x] Password validation via Frappe's built-in auth manager
- [x] Role-Based Access Control (7 roles across 3 companies + Group Admin)
- [x] Row-Level Security via `company_id` on every DocType
- [x] `require_company_access()` guard on all write operations
- [x] Frappe `permission_query_conditions` auto-filters all DB reads
- [x] `has_permission` hook validates individual document access

## API Security

- [x] JWT Bearer token required on all non-public endpoints
- [x] Rate limiting on login endpoint: 5 req/min per IP
- [x] Rate limiting on API: 30 req/min per IP
- [x] CORS restricted to specific frontend domain
- [x] HTTP → HTTPS redirect enforced at Nginx
- [x] TLS 1.2+ only (TLS 1.0/1.1 disabled)
- [x] HSTS header with 2-year max-age + preload
- [x] X-Frame-Options: DENY
- [x] X-Content-Type-Options: nosniff
- [x] Referrer-Policy: strict-origin-when-cross-origin
- [x] Permissions-Policy restricts camera, microphone, geolocation

## Database Security

- [x] MariaDB listens on 127.0.0.1 only (no external exposure)
- [x] Dedicated DB user with grants only on DMS database
- [x] Strong random password generated at setup
- [x] `utf8mb4` charset prevents encoding attacks
- [x] `LOAD DATA INFILE` disabled in MariaDB

## Infrastructure Security

- [x] Frappe runs as non-root `frappe` user
- [x] Redis listens on localhost only
- [x] UFW firewall: only 22, 80, 443 open
- [x] SSH key-based authentication (disable password auth)
- [x] Automatic security updates enabled
- [x] SSL certificates via Let's Encrypt (auto-renewed)

## Frontend Security

- [x] Next.js security headers configured
- [x] Tokens stored in localStorage (access) — consider HttpOnly cookies for extra security
- [x] No sensitive data logged to browser console in production
- [x] API URL never exposes internal infrastructure
- [x] XSS prevention via React's JSX escaping (never use `dangerouslySetInnerHTML`)

## Actions Before Going Live

### Critical (Do These First)

```bash
# 1. Change JWT secret
bench --site your-site.com set-config jwt_secret "$(openssl rand -base64 48)"

# 2. Change all user passwords from test values
bench --site your-site.com set-admin-password <new-strong-password>

# 3. Disable developer mode
bench --site your-site.com set-config developer_mode 0

# 4. Remove Frappe debug routes
bench --site your-site.com set-config server_script_enabled 0

# 5. Enable Redis password auth
# In redis.conf: requirepass <strong-password>
# Update site_config.json redis URLs accordingly

# 6. Set up UFW firewall
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# 7. Disable SSH password auth
echo "PasswordAuthentication no" >> /etc/ssh/sshd_config
systemctl restart sshd
```

### Important (Do Before Launch)

```bash
# 8. Enable automatic security updates
apt-get install -y unattended-upgrades
dpkg-reconfigure --priority=low unattended-upgrades

# 9. Set up log rotation
# /etc/logrotate.d/dms
# /home/frappe/frappe-bench/logs/*.log {
#     daily
#     rotate 30
#     compress
#     delaycompress
#     missingok
# }

# 10. Set up database backups
bench --site your-site.com backup
# Schedule daily cron:
# 0 2 * * * /home/frappe/frappe-bench/env/bin/bench --site your-site.com backup --with-files
```

### Monitoring & Alerting

```bash
# 11. Install fail2ban for SSH and Nginx brute force protection
apt-get install -y fail2ban

# /etc/fail2ban/jail.local
# [nginx-limit-req]
# enabled = true
# filter = nginx-limit-req
# logpath = /var/log/nginx/dms-api-error.log
# maxretry = 10

# 12. Set up server monitoring (uptime + performance)
# Recommended: Grafana + Prometheus, or use a managed service
```

## Security Contacts

Report vulnerabilities to: security@yourdomain.com

Do NOT report security issues in public GitHub issues.

## Regular Security Tasks (Monthly)

- [ ] Rotate JWT secret
- [ ] Review user accounts — disable inactive users
- [ ] Review Nginx access logs for anomalies
- [ ] Update system packages: `apt-get update && apt-get upgrade`
- [ ] Update Python dependencies: `cd ~/frappe-bench && pip install --upgrade frappe`
- [ ] Renew SSL certificate (automatic via certbot, verify: `certbot renew --dry-run`)
- [ ] Review failed login attempts in logs
- [ ] Backup restoration test
