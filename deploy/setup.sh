#!/bin/bash
# DMS Production Server Setup Script
# Tested on Ubuntu 22.04 LTS

set -euo pipefail
echo "=== DMS Production Setup ==="

BENCH_USER="frappe"
BENCH_PATH="/home/frappe/frappe-bench"
SITE_NAME="dms.yourdomain.com"
DB_PASSWORD="$(openssl rand -base64 24)"
JWT_SECRET="$(openssl rand -base64 32)"

# ─── System Dependencies ────────────────────────────────────────────────────
echo "[1/8] Installing system dependencies..."
apt-get update -qq
apt-get install -y \
    python3-dev python3-pip python3-venv \
    mariadb-server mariadb-client \
    redis-server \
    nodejs npm \
    nginx \
    supervisor \
    certbot python3-certbot-nginx \
    wkhtmltopdf \
    libmysqlclient-dev libssl-dev libffi-dev \
    git curl wget

# Node 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs

# Yarn
npm install -g yarn

# ─── Create Frappe User ──────────────────────────────────────────────────────
echo "[2/8] Creating frappe user..."
if ! id "$BENCH_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$BENCH_USER"
fi

# ─── MariaDB Setup ──────────────────────────────────────────────────────────
echo "[3/8] Configuring MariaDB..."
mysql -e "CREATE DATABASE IF NOT EXISTS \`dms_prod\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -e "CREATE USER IF NOT EXISTS 'frappe'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';"
mysql -e "GRANT ALL PRIVILEGES ON \`dms_prod\`.* TO 'frappe'@'localhost';"
mysql -e "FLUSH PRIVILEGES;"

cat >> /etc/mysql/mariadb.conf.d/50-server.cnf << 'EOF'
[mysqld]
character-set-server = utf8mb4
collation-server     = utf8mb4_unicode_ci
innodb_buffer_pool_size = 512M
innodb_log_file_size  = 128M
max_connections       = 200
query_cache_type      = 0
EOF
systemctl restart mariadb

# ─── Redis Config ───────────────────────────────────────────────────────────
echo "[4/8] Configuring Redis..."
sed -i 's/^# maxmemory .*/maxmemory 256mb/' /etc/redis/redis.conf
sed -i 's/^# maxmemory-policy .*/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf
systemctl restart redis-server

# ─── Frappe Bench ───────────────────────────────────────────────────────────
echo "[5/8] Installing Frappe bench..."
pip3 install frappe-bench
su - "$BENCH_USER" -c "
    bench init $BENCH_PATH --frappe-branch version-15 --python python3
    cd $BENCH_PATH
    bench get-app dms /path/to/your/dms/app
    bench new-site $SITE_NAME \
        --db-name dms_prod \
        --db-password '${DB_PASSWORD}' \
        --admin-password '$(openssl rand -base64 16)'
    bench --site $SITE_NAME install-app dms
    bench --site $SITE_NAME migrate
"

# ─── Frappe Config ──────────────────────────────────────────────────────────
echo "[6/8] Writing Frappe site config..."
cat > "$BENCH_PATH/sites/$SITE_NAME/site_config.json" << EOF
{
    "db_name": "dms_prod",
    "db_password": "${DB_PASSWORD}",
    "jwt_secret": "${JWT_SECRET}",
    "redis_cache": "redis://127.0.0.1:6379",
    "redis_queue": "redis://127.0.0.1:6380",
    "redis_socketio": "redis://127.0.0.1:6381",
    "socketio_port": 9000,
    "webserver_port": 8000,
    "google_analytics_id": "",
    "serve_default_site": true,
    "rebase_on_pull": false,
    "background_workers": 2
}
EOF

# ─── Production Mode ─────────────────────────────────────────────────────────
echo "[7/8] Enabling production mode..."
su - "$BENCH_USER" -c "
    cd $BENCH_PATH
    bench --site $SITE_NAME set-config developer_mode 0
    bench setup production $BENCH_USER
"

# ─── Nginx + SSL ─────────────────────────────────────────────────────────────
echo "[8/8] Configuring Nginx and SSL..."
cp /path/to/deploy/nginx.conf /etc/nginx/sites-available/dms
ln -sf /etc/nginx/sites-available/dms /etc/nginx/sites-enabled/dms
nginx -t && systemctl reload nginx

# Get SSL certificate
certbot --nginx -d api.yourdomain.com --non-interactive --agree-tos -m admin@yourdomain.com

echo ""
echo "========================================="
echo " DMS Backend Setup Complete!"
echo "========================================="
echo " Site:       https://$SITE_NAME"
echo " DB Password: $DB_PASSWORD"
echo " JWT Secret:  $JWT_SECRET"
echo ""
echo " IMPORTANT: Save these credentials securely!"
echo "========================================="
