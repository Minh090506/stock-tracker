# Deployment Experience Runbook

Kinh nghiệm deploy VN Stock Tracker lên VPS + domain, ghi lại từ thực tế ngày 24-25/02/2026.

---

## Tổng quan

| Hạng mục | Chi tiết |
|----------|----------|
| VPS | Hetzner CX22 (2 vCPU, 4GB RAM, 40GB SSD) — €3.99/tháng |
| OS | Ubuntu 24.04 |
| Domain | stock.myvivatour.com (subdomain) |
| SSL | Cloudflare Free (proxy mode) — không cần Certbot |
| Stack | Docker Compose (7 containers) |
| Tổng thời gian | ~3-4 giờ (bao gồm debug) |

---

## Các bước từ đầu đến cuối

### Bước 1: Mua VPS Hetzner (~5 phút)

1. Vào [Hetzner Cloud Console](https://console.hetzner.cloud)
2. Create server → CX22, Ubuntu 24.04, Nuremberg
3. Thêm SSH public key từ máy local (`~/.ssh/id_ed25519.pub`)
4. Ghi lại IP → `46.225.168.123`

### Bước 2: Setup server cơ bản (~15 phút)

```bash
ssh root@46.225.168.123

# Update system
apt update && apt upgrade -y

# Tạo user deploy (không dùng root)
adduser --disabled-password deploy
usermod -aG sudo deploy
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy

# Copy SSH key sang user deploy
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
```

### Bước 3: Cài Docker (~5 phút)

```bash
# Chuyển sang user deploy
su - deploy

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy

# Logout rồi login lại để group có hiệu lực
exit
ssh deploy@46.225.168.123

# Verify
docker compose version
```

### Bước 4: Firewall (~2 phút)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

> Prometheus/Grafana KHÔNG expose ra ngoài — truy cập qua SSH tunnel.

### Bước 5: Clone repo & tạo .env (~10 phút)

```bash
cd /home/deploy
git clone https://github.com/Minh090506/stock-tracker.git
cd stock-tracker

# Tạo .env từ example
cp .env.example .env
nano .env
```

**Các biến quan trọng cần điền:**
```
SSI_CONSUMER_ID=<your_id>
SSI_CONSUMER_SECRET=<your_secret>
CORS_ORIGINS=http://localhost,https://stock.myvivatour.com   ← QUAN TRỌNG
```

### Bước 6: Build & start containers (~5 phút)

```bash
docker compose -f docker-compose.prod.yml up -d --build

# Verify
docker compose -f docker-compose.prod.yml ps
curl http://localhost/health
```

### Bước 7: Setup domain + Cloudflare SSL (~15 phút)

1. Thêm domain vào [Cloudflare](https://dash.cloudflare.com) (free plan)
2. Đổi nameserver ở nhà đăng ký domain sang Cloudflare
3. Thêm DNS record:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | stock | 46.225.168.123 | Proxied (orange) |

4. Cấu hình SSL/TLS:
   - Mode: **Full** (không cần Full Strict)
   - Always Use HTTPS: **ON**
   - Minimum TLS: **1.2**

5. Cấu hình Nginx trên VPS để listen 443 + trust Cloudflare IPs (xem `nginx/nginx.conf`)

6. Rebuild nginx:
```bash
docker compose -f docker-compose.prod.yml up -d --build nginx
```

### Bước 8: Verify production

```bash
curl -I https://stock.myvivatour.com
curl https://stock.myvivatour.com/health
```

---

## Quy trình deploy code mới (sau lần đầu)

```bash
# 1. Trên LOCAL — push code
git push origin master

# 2. SSH vào VPS
ssh root@46.225.168.123
cd /home/deploy/stock-tracker

# 3. Pull code mới
git config --global --add safe.directory /home/deploy/stock-tracker  # chỉ cần 1 lần
git pull origin master

# 4. Rebuild & restart
docker compose -f docker-compose.prod.yml build --no-cache backend frontend
docker compose -f docker-compose.prod.yml up -d backend frontend

# 5. Verify
docker compose -f docker-compose.prod.yml ps
```

---

## Bài học kinh nghiệm (Lessons Learned)

### 1. CORS — Sai một chữ, trắng cả bảng

**Vấn đề**: Price board trống hoàn toàn dù WebSocket "Live" xanh lè.

**Nguyên nhân**: `.env` trên VPS có `CORS_ORIGINS=https://yourdomain.com` (placeholder chưa đổi).

**Tại sao khó debug**:
- WebSocket KHÔNG bị CORS chặn (browser không gửi preflight cho WS upgrade)
- Chỉ REST API bị chặn → fetch VN30 symbols thất bại → `vn30Symbols = []` → bảng rỗng
- Frontend `.catch(() => {})` nuốt lỗi im lặng

**Fix**: Sửa `.env` → `CORS_ORIGINS=http://localhost,https://stock.myvivatour.com`

**Bài học**:
- Luôn kiểm tra CORS ngay sau deploy
- Không dùng `.catch(() => {})` — ít nhất phải `console.error()`
- WebSocket "Live" ≠ mọi thứ đều hoạt động

### 2. Git safe.directory — root vs deploy user

**Vấn đề**: `git pull` báo `fatal: detected dubious ownership`

**Nguyên nhân**: Repo clone bởi user `deploy` nhưng SSH vào bằng `root`.

**Fix**:
```bash
git config --global --add safe.directory /home/deploy/stock-tracker
```

**Bài học**: Nên SSH bằng đúng user đã clone repo. Hoặc chạy lệnh trên 1 lần khi dùng root.

### 3. macOS sed khác Linux sed

**Vấn đề**: `sed -i 's|old|new|' file` lỗi trên macOS.

**Fix macOS**: `sed -i '' 's|old|new|' file` (thêm `''` sau `-i`)

**Bài học**: Trên macOS dùng `sed -i ''`, trên Linux (VPS) dùng `sed -i` không cần quote.

### 4. VPS chưa có code mới nhất

**Vấn đề**: Rebuild xong nhưng UI vẫn hiển thị mã phái sinh cũ (VN30F2503).

**Nguyên nhân**: Quên push code từ local trước khi pull trên VPS. VPS vẫn ở commit cũ.

**Fix**: Push từ local trước → pull trên VPS → rebuild.

**Bài học**: Luôn kiểm tra `git log --oneline -3` trên VPS sau khi pull để verify code mới nhất.

### 5. Docker build cache

**Vấn đề**: `docker compose up -d --build` vẫn dùng layer cũ.

**Fix**: Tách 2 lệnh:
```bash
docker compose -f docker-compose.prod.yml build --no-cache backend frontend
docker compose -f docker-compose.prod.yml up -d backend frontend
```

**Bài học**: `--no-cache` không phải flag của `up`, mà của `build`. Phải tách ra.

### 6. Cloudflare SSL mode

**Vấn đề**: Dùng "Full (Strict)" cần origin certificate. Dùng "Flexible" gây redirect loop.

**Fix**: Dùng mode **Full** (không Strict) — Cloudflare chấp nhận self-signed cert từ origin.

**Bài học**: Full mode là đủ cho hầu hết trường hợp. Không cần Certbot.

### 7. Browser cache sau deploy

**Vấn đề**: Deploy code mới nhưng trình duyệt vẫn hiển thị UI cũ.

**Fix**: Hard refresh `Cmd + Shift + R` (macOS) hoặc `Ctrl + Shift + R` (Windows/Linux).

**Bài học**: Luôn hard refresh sau deploy. Hoặc cấu hình Vite hash tên file để cache-bust tự động.

---

## Checklist deploy nhanh

- [ ] Code đã push lên remote (`git push origin master`)
- [ ] SSH vào VPS, `cd /home/deploy/stock-tracker`
- [ ] `git pull origin master` — verify commit mới nhất
- [ ] `.env` đúng (đặc biệt `CORS_ORIGINS`)
- [ ] `docker compose build --no-cache backend frontend`
- [ ] `docker compose up -d backend frontend`
- [ ] `docker compose ps` — tất cả healthy
- [ ] Hard refresh trình duyệt
- [ ] Test: Price Board có data (trong giờ giao dịch 9:00-15:00 VN)
- [ ] Test: WebSocket kết nối (indicator "Live" xanh)
- [ ] Test: Charts hiển thị đúng mã phái sinh (VN30F T0x/202x)

---

## Truy cập Monitoring (qua SSH tunnel)

```bash
# Grafana (trên local)
ssh -L 3000:localhost:3000 root@46.225.168.123
# Mở http://localhost:3000 (admin/admin)

# Prometheus
ssh -L 9090:localhost:9090 root@46.225.168.123
# Mở http://localhost:9090
```

---

## Xem logs trên VPS

```bash
# Backend logs
docker compose -f docker-compose.prod.yml logs backend --tail 50

# Nginx logs
docker compose -f docker-compose.prod.yml logs nginx --tail 50

# Tất cả services
docker compose -f docker-compose.prod.yml logs --tail 20

# Follow real-time
docker compose -f docker-compose.prod.yml logs -f backend
```
