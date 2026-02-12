# Hướng Dẫn Sử Dụng VN Stock Tracker

## Mục Lục

1. [Giới thiệu](#1-giới-thiệu)
2. [Yêu cầu hệ thống](#2-yêu-cầu-hệ-thống)
3. [Cài đặt & Khởi chạy](#3-cài-đặt--khởi-chạy)
4. [Cấu hình](#4-cấu-hình)
5. [Hướng dẫn sử dụng giao diện](#5-hướng-dẫn-sử-dụng-giao-diện)
6. [Logic kỹ thuật & Phân tích chuyên sâu](#6-logic-kỹ-thuật--phân-tích-chuyên-sâu)
7. [API Reference](#7-api-reference)
8. [WebSocket Real-time](#8-websocket-real-time)
9. [Giám sát hệ thống (Monitoring)](#9-giám-sát-hệ-thống-monitoring)
10. [Xử lý sự cố](#10-xử-lý-sự-cố)
11. [Hướng dẫn vận hành hàng ngày](#11-hướng-dẫn-vận-hành-hàng-ngày)
12. [FAQ](#12-faq)

---

## 1. Giới thiệu

**VN Stock Tracker** là nền tảng theo dõi chứng khoán Việt Nam **thời gian thực**, tập trung vào rổ **VN30** với các tính năng chính:

- **Bảng giá VN30** — Giá real-time, sparkline, sắp xếp cột, phân loại mua/bán chủ động
- **Dòng tiền NDTNN** — Theo dõi nhà đầu tư nước ngoài: tổng hợp, theo mã, theo ngành, top mua/bán
- **Phân tích khối lượng** — Mua chủ động / Bán chủ động / Trung lập theo từng phiên ATO/Liên tục/ATC
- **Phái sinh (Derivatives)** — Basis VN30F vs VN30, premium/discount, xu hướng hội tụ
- **Cảnh báo (Signals)** — Volume spike, price breakout, foreign acceleration, basis divergence

**Nguồn dữ liệu**: SSI FastConnect (WebSocket + REST) — duy nhất, không dùng vnstock hay TCBS.

**Quy ước màu thị trường VN**:
| Màu | Ý nghĩa |
|------|---------|
| Đỏ | Tăng giá |
| Xanh lá | Giảm giá |
| Hồng (Fuchsia) | Giá trần (TVT) |
| Xanh dương (Cyan) | Giá sàn (STC) |

---

## 2. Yêu cầu hệ thống

### Triển khai bằng Docker (khuyến nghị)

- Docker Engine 20.10+
- Docker Compose 2.0+
- RAM: tối thiểu 4GB (khuyến nghị 8GB)
- Tài khoản SSI FastConnect (Consumer ID + Secret)

### Phát triển cục bộ (local development)

- Python 3.12+
- Node.js 20+
- PostgreSQL 16 (hoặc TimescaleDB)
- Tài khoản SSI FastConnect

---

## 3. Cài đặt & Khởi chạy

### 3.1. Triển khai Docker (Production)

**Bước 1**: Clone dự án

```bash
git clone <repo-url> stock-tracker
cd stock-tracker
```

**Bước 2**: Tạo file cấu hình

```bash
cp backend/.env.example backend/.env
```

**Bước 3**: Chỉnh sửa `backend/.env` — điền thông tin SSI

```bash
# BẮT BUỘC: Thông tin SSI FastConnect
SSI_CONSUMER_ID=your_consumer_id_here
SSI_CONSUMER_SECRET=your_consumer_secret_here

# QUAN TRỌNG: Hai domain khác nhau!
SSI_BASE_URL=https://fc-data.ssi.com.vn/          # REST API
SSI_STREAM_URL=https://fc-datahub.ssi.com.vn/     # WebSocket (KHÁC fc-data!)
```

**Bước 4**: Khởi chạy toàn bộ hệ thống

```bash
# Sử dụng script deploy tự động (khuyến nghị)
./scripts/deploy.sh

# Hoặc chạy thủ công
docker compose -f docker-compose.prod.yml up -d
```

**Bước 5**: Kiểm tra hệ thống

```bash
# Health check
curl http://localhost/health

# Xem trạng thái container
docker compose -f docker-compose.prod.yml ps
```

**Truy cập**:
| Dịch vụ | URL |
|---------|-----|
| Giao diện chính | http://localhost |
| Backend API | http://localhost/api/market/snapshot |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

### 3.2. Phát triển cục bộ (Local Development)

#### Backend

```bash
cd backend

# Tạo virtual environment
python3.12 -m venv venv

# Cài đặt dependencies
./venv/bin/pip install -r requirements.txt

# Tạo file cấu hình
cp .env.example .env
# Chỉnh sửa .env với thông tin SSI

# Chạy backend
./venv/bin/uvicorn app.main:app --reload
# Backend chạy tại: http://localhost:8000
```

#### Frontend

```bash
cd frontend

# Cài đặt dependencies
npm install

# Chạy development server
npm run dev
# Frontend chạy tại: http://localhost:5173
```

### 3.3. Dừng hệ thống

```bash
# Dừng tất cả container
docker compose -f docker-compose.prod.yml down

# Dừng + xóa dữ liệu (volumes)
docker compose -f docker-compose.prod.yml down -v
```

### 3.4. Rebuild

```bash
# Rebuild toàn bộ
docker compose -f docker-compose.prod.yml build --no-cache

# Rebuild một service cụ thể
docker compose -f docker-compose.prod.yml build --no-cache backend
```

---

## 4. Cấu hình

### 4.1. Biến môi trường

Tất cả cấu hình qua file `.env`. Mẫu đầy đủ:

```bash
# ============================================
# SSI FastConnect (BẮT BUỘC)
# ============================================
SSI_CONSUMER_ID=your_id
SSI_CONSUMER_SECRET=your_secret
SSI_BASE_URL=https://fc-data.ssi.com.vn/
SSI_STREAM_URL=https://fc-datahub.ssi.com.vn/

# ============================================
# Database
# ============================================
DATABASE_URL=postgresql://stock:stock@timescaledb:5432/stock_tracker
DB_POOL_MIN=2           # Pool tối thiểu
DB_POOL_MAX=10          # Pool tối đa

# ============================================
# Ứng dụng
# ============================================
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false
LOG_LEVEL=INFO           # DEBUG, INFO, WARNING, ERROR

# ============================================
# CORS
# ============================================
CORS_ORIGINS=http://localhost,https://yourdomain.com

# ============================================
# Dữ liệu thị trường
# ============================================
CHANNEL_R_INTERVAL_MS=1000      # Tần suất cập nhật NDTNN (ms)
FUTURES_OVERRIDE=               # Override hợp đồng phái sinh (VN30F2603)

# ============================================
# WebSocket
# ============================================
WS_THROTTLE_INTERVAL_MS=500     # Throttle broadcast (ms)
WS_HEARTBEAT_INTERVAL=30.0      # Ping mỗi 30s
WS_HEARTBEAT_TIMEOUT=10.0       # Timeout sau 10s
WS_QUEUE_SIZE=50                # Queue mỗi client
WS_AUTH_TOKEN=                  # Token xác thực (để trống = tắt)
WS_MAX_CONNECTIONS_PER_IP=5     # Giới hạn kết nối/IP
```

### 4.2. Lưu ý quan trọng về SSI

SSI FastConnect sử dụng **HAI domain khác nhau**:

| Mục đích | Domain | Biến |
|----------|--------|------|
| REST API (tra cứu) | `fc-data.ssi.com.vn` | `SSI_BASE_URL` |
| WebSocket (streaming) | `fc-datahub.ssi.com.vn` | `SSI_STREAM_URL` |

> **Sai domain WebSocket là lỗi phổ biến nhất!** Nếu thấy "502 Bad Gateway" trong log backend, kiểm tra `SSI_STREAM_URL`.

### 4.3. Override hợp đồng phái sinh

Mặc định, hệ thống tự phát hiện hợp đồng VN30F đang hoạt động dựa theo khối lượng giao dịch. Khi cần override (ví dụ trong kỳ rollover):

```bash
FUTURES_OVERRIDE=VN30F2603,VN30F2606
```

---

## 5. Hướng dẫn sử dụng giao diện

Giao diện gồm thanh điều hướng bên trái (sidebar) với 5 trang chính. Trang mặc định khi mở là **Price Board**.

### 5.1. Bảng Giá VN30 (Price Board)

**Đường dẫn**: `/price-board`

Trang chính hiển thị giá real-time toàn bộ 30 mã trong rổ VN30.

**Thành phần giao diện**:

- **Tiêu đề + Trạng thái phiên**: Hiển thị phiên hiện tại (Pre-market / ATO / Liên tục / Nghỉ trưa / ATC / PLO / Đóng cửa). Tự động cập nhật mỗi 15 giây.
- **Trạng thái kết nối**: Chấm xanh = "Live" (WebSocket), chấm vàng = "Polling" (REST fallback)
- **Bảng giá**: Hiển thị toàn bộ mã VN30 với các cột:

| Cột | Mô tả |
|-----|-------|
| Symbol | Mã chứng khoán |
| Last Price | Giá khớp gần nhất |
| Change | Thay đổi so với giá tham chiếu |
| Change % | Phần trăm thay đổi |
| Ref | Giá tham chiếu (phiên trước) |
| Ceiling | Giá trần |
| Floor | Giá sàn |
| Last Vol | Khối lượng giao dịch gần nhất |
| Sparkline | Biểu đồ giá mini (50 điểm gần nhất) |

**Tính năng**:
- Click vào tiêu đề cột để **sắp xếp** (tăng/giảm)
- Dòng **nhấp nháy** (flash) khi giá thay đổi
- Mã màu theo quy ước VN: đỏ = tăng, xanh = giảm, hồng = trần, cyan = sàn
- Khi mất kết nối WebSocket, tự động chuyển sang REST polling (5 giây/lần) và thử kết nối lại WS mỗi 30 giây

### 5.2. Dòng Tiền NDTNN (Foreign Flow)

**Đường dẫn**: `/foreign-flow`

Theo dõi hoạt động mua/bán của nhà đầu tư nước ngoài (NDTNN) trên VN30.

**Kiến trúc dữ liệu kết hợp (hybrid)**:
- **WebSocket** `/ws/foreign`: Cập nhật tổng hợp real-time (tổng mua/bán/ròng)
- **REST polling** `/api/market/foreign-detail` (10 giây/lần): Chi tiết từng mã

**Các thành phần giao diện**:

1. **Summary Cards** — Tổng quan nhanh:
   - Tổng giá trị mua NDTNN
   - Tổng giá trị bán NDTNN
   - Giá trị ròng (net)
   - Tổng khối lượng mua/bán

2. **Biểu đồ ngành (Sector Bar Chart)** — Phân nhóm 30 mã VN30 theo ngành (Ngân hàng, Bất động sản, Thép, v.v.), hiển thị mua/bán ròng mỗi ngành dạng thanh ngang:
   - Xanh lá = mua ròng
   - Đỏ = bán ròng

3. **Biểu đồ dòng tiền tích lũy (Cumulative Flow)** — Biểu đồ area chart theo dõi giá trị ròng NDTNN trong ngày:
   - Vùng xanh = dòng tiền dương (mua ròng tích lũy)
   - Vùng đỏ = dòng tiền âm (bán ròng tích lũy)
   - Reset tự động khi sang ngày mới

4. **Top 10 Mua/Bán** — Hai bảng cạnh nhau:
   - Top 10 mã NDTNN mua ròng nhiều nhất
   - Top 10 mã NDTNN bán ròng nhiều nhất

5. **Bảng chi tiết** — Toàn bộ mã VN30 với chi tiết NDTNN:
   - Khối lượng mua/bán, giá trị mua/bán, ròng
   - Tốc độ mua/bán (volume/phút, cửa sổ 5 phút)
   - Gia tốc (thay đổi tốc độ)

### 5.3. Phân Tích Khối Lượng (Volume Analysis)

**Đường dẫn**: `/volume`

Phân tích chi tiết khối lượng giao dịch Mua chủ động / Bán chủ động / Trung lập.

**Thuật toán phân loại giao dịch**:
| Điều kiện | Phân loại |
|-----------|----------|
| Giá khớp >= Giá chào bán (Ask) | **Mua chủ động** |
| Giá khớp <= Giá chào mua (Bid) | **Bán chủ động** |
| Giá nằm giữa Bid và Ask | **Trung lập** |
| Phiên ATO/ATC (khớp lệnh tập trung) | **Trung lập** |

**Các thành phần giao diện**:

1. **Biểu đồ tròn (Pie Chart)** — Tỷ lệ mua/bán/trung lập toàn thị trường
2. **Summary Cards** — Tổng hợp tỷ lệ mua/bán chủ động
3. **Biểu đồ thanh xếp chồng (Stacked Bar)** — So sánh mua/bán/trung lập theo từng mã
4. **So sánh phiên (Session Comparison)** — Biểu đồ so sánh khối lượng giữa 3 phiên:
   - **ATO**: Khớp lệnh mở cửa (9:00-9:15)
   - **Liên tục**: Giao dịch liên tục (9:15-14:30)
   - **ATC**: Khớp lệnh đóng cửa (14:30-14:45)
5. **Bảng chi tiết** — Khối lượng mua/bán/trung lập từng mã với thanh áp lực (pressure bar)

### 5.4. Phái Sinh (Derivatives)

**Đường dẫn**: `/derivatives`

Phân tích chênh lệch (basis) giữa hợp đồng tương lai VN30F và chỉ số VN30.

**Công thức**:
```
Basis = Giá VN30F - Giá trị VN30 Index
Basis % = Basis / VN30 Index × 100
```

**Các thành phần giao diện**:

1. **Summary Cards**:
   - Hợp đồng đang hoạt động (VN30F2603)
   - Giá VN30F hiện tại
   - Giá trị VN30 Index
   - Basis (điểm) + Basis %
   - Trạng thái: **Premium** (basis > 0) hoặc **Discount** (basis < 0)

2. **Biểu đồ xu hướng Basis (Area Chart)** — Hiển thị 30 phút gần nhất (~200 điểm):
   - Vùng đỏ = Premium (futures > spot)
   - Vùng xanh = Discount (futures < spot)
   - Đường zero rõ ràng

3. **Chỉ báo hội tụ (Convergence Indicator)** — Phân tích xu hướng basis đang hội tụ hay phân kỳ:
   - Tính slope (độ dốc) của basis
   - Hội tụ = basis đang tiến về 0
   - Phân kỳ = basis đang rời xa 0

4. **Open Interest** — Hiển thị thông tin open interest (nếu có từ SSI)

### 5.5. Cảnh Báo (Signals)

**Đường dẫn**: `/signals`

Hệ thống cảnh báo analytics real-time với 4 loại tín hiệu:

| Loại cảnh báo | Mô tả | Điều kiện |
|---------------|--------|-----------|
| **VOLUME_SPIKE** | Đột biến khối lượng | Khối lượng > 3× trung bình (cửa sổ 20 phút) |
| **PRICE_BREAKOUT** | Phá vỡ giá trần/sàn | Giá khớp = giá trần (TVT) hoặc giá sàn (STC) |
| **FOREIGN_ACCELERATION** | Gia tốc NDTNN | Giá trị ròng thay đổi > 30% trong 5 phút |
| **BASIS_DIVERGENCE** | Đảo chiều basis | Basis chuyển từ premium → discount hoặc ngược lại |

**Mức độ nghiêm trọng**:
| Mức | Ý nghĩa |
|-----|---------|
| INFO | Thông tin tham khảo |
| WARNING | Cảnh báo cần chú ý |
| CRITICAL | Cảnh báo nghiêm trọng |

**Tính năng giao diện**:

1. **Bộ lọc kép** — Filter theo loại cảnh báo (4 loại) VÀ mức độ (3 mức), hiển thị dưới dạng chip/badge có màu
2. **Danh sách cảnh báo** — Thẻ cảnh báo real-time với:
   - Icon theo loại cảnh báo
   - Mã chứng khoán liên quan
   - Mô tả chi tiết
   - Timestamp
   - Tự động cuộn khi có cảnh báo mới
3. **Âm thanh** — Bật/tắt thông báo âm thanh cho cảnh báo CRITICAL
4. **Dedup** — Mỗi cặp (loại, mã) chỉ cảnh báo 1 lần mỗi 60 giây (tránh spam)

### 5.6. Trạng thái kết nối

Trên mỗi trang, góc phải hiển thị trạng thái kết nối:

| Trạng thái | Hiển thị | Ý nghĩa |
|-----------|---------|---------|
| Chấm xanh + "Live" | WebSocket đang hoạt động | Dữ liệu real-time, độ trễ < 100ms |
| Chấm vàng + "Polling" | REST fallback | WebSocket mất kết nối, polling mỗi 5s |
| "reconnecting..." | Đang kết nối lại | Đang thử kết nối lại WS |

**Cơ chế tự phục hồi**:
1. WebSocket mất kết nối → thử lại với backoff tăng dần (1s → 2s → 4s → 8s → 16s → 30s)
2. Sau 3 lần thất bại → chuyển sang REST polling (5 giây/lần)
3. Trong chế độ polling → thử kết nối lại WS mỗi 30 giây
4. Khi WS kết nối lại thành công → tự động tắt polling

---

## 6. Logic kỹ thuật & Phân tích chuyên sâu

Phần này giải thích chi tiết logic xử lý dữ liệu đằng sau mỗi tính năng, kèm ví dụ cụ thể và cách tìm insight khi sử dụng.

### 6.1. Mua Chủ Động / Bán Chủ Động — Nguyên lý hoạt động

#### Tại sao cần phân loại?

Trên sổ lệnh, mỗi giao dịch khớp đều có giá và khối lượng, nhưng **không cho biết ai là người chủ động khớp lệnh**. Phân loại mua/bán chủ động giúp trả lời câu hỏi: "Bên mua hay bên bán đang chủ động hơn?" — đây là tín hiệu quan trọng để đánh giá áp lực cung/cầu thực tế.

#### Thuật toán phân loại

Hệ thống sử dụng phương pháp **so sánh giá khớp với giá chào mua/bán tốt nhất (Best Bid/Ask)** tại thời điểm khớp lệnh:

```
┌─────────────────────────────────────────────────────────┐
│                    Sổ Lệnh (Order Book)                 │
│                                                         │
│  Bên Bán (Ask/Offer)        Bên Mua (Bid)              │
│  ┌──────────────────┐       ┌──────────────────┐        │
│  │ Ask3: 52.5 (200) │       │ Bid1: 51.5 (500) │ ← Best│
│  │ Ask2: 52.2 (300) │       │ Bid2: 51.2 (400) │        │
│  │ Ask1: 52.0 (100) │ ← Best│ Bid3: 51.0 (200) │        │
│  └──────────────────┘       └──────────────────┘        │
│                                                         │
│  Giá khớp = 52.0 → Người mua chủ động "ăn" giá Ask     │
│  → MUA CHỦ ĐỘNG                                         │
│                                                         │
│  Giá khớp = 51.5 → Người bán chủ động "đập" giá Bid    │
│  → BÁN CHỦ ĐỘNG                                         │
│                                                         │
│  Giá khớp = 51.8 → Nằm giữa Bid và Ask                 │
│  → TRUNG LẬP                                            │
└─────────────────────────────────────────────────────────┘
```

**Logic chính xác (từ source code `trade_classifier.py`)**:

| Điều kiện | Kết quả | Giải thích |
|-----------|---------|------------|
| Phiên ATO hoặc ATC | **TRUNG LẬP** | Khớp lệnh tập trung (batch auction) — không có bên chủ động rõ ràng |
| `Giá khớp >= Ask1` | **MUA CHỦ ĐỘNG** | Bên mua sẵn sàng mua ở giá chào bán → mua chủ động |
| `Giá khớp <= Bid1` | **BÁN CHỦ ĐỘNG** | Bên bán sẵn sàng bán ở giá chào mua → bán chủ động |
| Giá nằm giữa Bid-Ask | **TRUNG LẬP** | Không xác định được bên chủ động |
| Chưa có dữ liệu Bid/Ask | **TRUNG LẬP** | Vài giây đầu phiên, cache chưa đủ dữ liệu |

#### Dữ liệu đầu vào quan trọng

- **`LastVol`** (khối lượng PER-TRADE) — Hệ thống dùng khối lượng **từng giao dịch** riêng lẻ, KHÔNG phải `TotalVol` (khối lượng tích lũy cả phiên). Đây là khác biệt quan trọng: nếu dùng TotalVol, mỗi message sẽ cộng dồn toàn bộ phiên → sai hoàn toàn.

- **Bid1/Ask1** — Cache từ message Quote gần nhất (cập nhật real-time qua `QuoteCache`). Mỗi khi có quote mới, cache được ghi đè, đảm bảo trade classifier luôn dùng bid/ask mới nhất.

#### Ví dụ thực tế

**Ví dụ 1: VNM trong phiên liên tục**
```
QuoteCache: VNM → Bid1 = 75.2, Ask1 = 75.5

Trade #1: VNM, LastPrice = 75.5, LastVol = 1000
→ 75.5 >= Ask1(75.5) → MUA CHỦ ĐỘNG, volume = 1000

Trade #2: VNM, LastPrice = 75.2, LastVol = 500
→ 75.2 <= Bid1(75.2) → BÁN CHỦ ĐỘNG, volume = 500

Trade #3: VNM, LastPrice = 75.3, LastVol = 200
→ 75.2 < 75.3 < 75.5 → TRUNG LẬP, volume = 200

Kết quả tích lũy VNM:
  Mua chủ động:  1000 cp (66.7%)
  Bán chủ động:   500 cp (33.3%)
  Trung lập:      200 cp
  → Áp lực MUA mạnh hơn
```

**Ví dụ 2: HPG trong phiên ATO**
```
Trade: HPG, LastPrice = 26.5, LastVol = 50000, TradingSession = "ATO"
→ Phiên ATO → TRUNG LẬP (bất kể giá so với bid/ask)

Lý do: ATO là khớp lệnh tập trung, giá khớp được xác định bởi thuật toán
khớp lệnh tối đa khối lượng, không phản ánh bên nào "chủ động" mua/bán.
```

#### Tích lũy theo phiên (Session Breakdown)

Mỗi giao dịch được phân vào 3 bucket phiên:
```
SessionStats (VNM):
├── ato:        { mua: 5000, bán: 3000, trung_lập: 50000 }  ← ATO luôn trung lập
├── continuous: { mua: 120000, bán: 85000, trung_lập: 15000 }
├── atc:        { mua: 8000, bán: 6000, trung_lập: 30000 }  ← ATC luôn trung lập
└── tổng:       { mua: 133000, bán: 94000, trung_lập: 95000 }
    → Bất biến: tổng = ato + continuous + atc ✓
```

#### Cách đọc insight từ Mua/Bán Chủ Động

| Tín hiệu | Cách đọc | Gợi ý hành động |
|-----------|----------|-----------------|
| Mua chủ động >> Bán chủ động (> 60%) | Bên mua đang chủ động đẩy giá, áp lực cầu mạnh | Xu hướng tăng ngắn hạn, theo dõi xem có duy trì không |
| Bán chủ động >> Mua chủ động (> 60%) | Bên bán đang chủ động xả hàng, áp lực cung mạnh | Xu hướng giảm ngắn hạn, cẩn thận nếu đang nắm giữ |
| Mua ≈ Bán (45-55%) | Cân bằng cung cầu, thị trường đi ngang | Chờ breakout rõ ràng |
| Trung lập cao bất thường (> 40%) | Nhiều giao dịch trong spread → thanh khoản phân tán | Biến động thấp, giá đi sideway |
| Đột biến mua chủ động + volume tăng | "Smart money" đang tích lũy | Kết hợp kiểm tra NDTNN |
| Bán chủ động tập trung ở ATC | Xả hàng cuối phiên → có thể là quỹ rebalance | Ngày hôm sau có thể phục hồi |

**Chiến thuật kết hợp**:
- **Mua chủ động tăng + NDTNN mua ròng** → Tín hiệu mạnh, cả retail và foreign cùng mua
- **Mua chủ động tăng + NDTNN bán ròng** → Retail mua nhưng foreign xả → cẩn thận
- **Volume spike + mua chủ động > 70%** → Có thể có tin tốt chưa public
- **Phiên ATO volume lớn bất thường** → Có lệnh lớn đặt sẵn, theo dõi phiên liên tục sau đó

---

### 6.2. Theo dõi NDTNN — Logic xử lý delta, speed, acceleration

#### Cách SSI gửi dữ liệu NDTNN

SSI Channel R gửi **giá trị tích lũy** (`FBuyVol`, `FSellVol`) từ đầu phiên, KHÔNG phải delta:

```
09:15:01 → VNM: FBuyVol = 1000, FSellVol = 500
09:15:02 → VNM: FBuyVol = 1500, FSellVol = 500    ← NDTNN vừa mua thêm 500
09:15:03 → VNM: FBuyVol = 1500, FSellVol = 800    ← NDTNN vừa bán thêm 300
```

#### Tính Delta (mỗi lần cập nhật)

```
delta_buy  = FBuyVol_hiện_tại - FBuyVol_trước_đó
delta_sell = FSellVol_hiện_tại - FSellVol_trước_đó

Ví dụ (09:15:02):
  delta_buy  = 1500 - 1000 = 500 (vừa mua thêm 500 cổ)
  delta_sell = 500 - 500 = 0    (không bán thêm)
```

**Edge case**: Nếu delta < 0 (do reconnect, SSI reset giá trị) → log warning + clamp về 0.

#### Tính Speed (tốc độ mua/bán mỗi phút)

```
Speed = Tổng delta trong 5 phút gần nhất / 5

Ví dụ (VNM, 5 phút gần nhất):
  Tổng delta_buy  = 5000 → buy_speed = 1000 cổ/phút
  Tổng delta_sell = 2000 → sell_speed = 400 cổ/phút
  → NDTNN đang mua gấp 2.5 lần tốc độ bán
```

Cửa sổ trượt (rolling window): **5 phút**, lưu tối đa 600 data points (~10 phút ở 1 msg/giây).

#### Tính Acceleration (gia tốc)

```
Acceleration = Speed_hiện_tại - Speed_trước_đó

Ví dụ:
  Lúc 10:00 → buy_speed = 1000/phút
  Lúc 10:01 → buy_speed = 1500/phút
  → buy_acceleration = +500 (NDTNN đang tăng tốc mua)

  Lúc 10:02 → buy_speed = 800/phút
  → buy_acceleration = -700 (NDTNN đang giảm tốc)
```

#### Cách đọc insight từ dữ liệu NDTNN

| Tín hiệu | Ý nghĩa | Hành động |
|-----------|---------|-----------|
| Net > 0, speed tăng, acceleration > 0 | NDTNN đang tăng tốc mua — tín hiệu mạnh nhất | Theo dõi sát, cân nhắc tham gia |
| Net > 0, speed giảm, acceleration < 0 | NDTNN vẫn mua ròng nhưng đang giảm tốc | Có thể sắp dừng mua, canh chỉnh |
| Net < 0, acceleration ngày càng âm | NDTNN tăng tốc bán — áp lực rất lớn | Cẩn thận, có thể có tin xấu |
| Net đột ngột đổi chiều (-→+) | NDTNN chuyển từ bán sang mua | Theo dõi xem có duy trì không |
| Top buy/sell đều là Banking | Dòng tiền ngoại tập trung vào ngân hàng | Đánh giá chung ngành banking |
| Sector Banking mua ròng + BĐS bán ròng | Rotation giữa ngành | Theo dòng tiền ngoại |

**Kết hợp biểu đồ tích lũy (Cumulative Flow)**:
- Đường đi lên liên tục → NDTNN mua ròng đều đặn → tích cực
- Đường đi xuống liên tục → NDTNN bán ròng → tiêu cực
- Đường đi lên rồi đột ngột quay đầu → NDTNN đã bán phần đã mua → cẩn thận
- Đường phẳng → NDTNN không tham gia → ít tác động

---

### 6.3. Phái sinh (Basis) — Logic tính toán và ý nghĩa

#### Công thức Basis

```
Basis       = Giá VN30F - Chỉ số VN30
Basis %     = (Basis / VN30) × 100
is_premium  = Basis > 0
```

**Ví dụ**:
```
VN30F2603 = 1285.5 điểm
VN30 Index = 1280.0 điểm
→ Basis = +5.5 điểm
→ Basis % = +0.43%
→ Trạng thái: PREMIUM (futures đắt hơn spot)
```

#### Premium vs Discount

| Trạng thái | Điều kiện | Ý nghĩa |
|-----------|-----------|---------|
| **Premium** | VN30F > VN30 | Thị trường kỳ vọng tăng — futures "đắt hơn" spot vì trader sẵn sàng trả premium |
| **Discount** | VN30F < VN30 | Thị trường kỳ vọng giảm hoặc đang có selling pressure trên phái sinh |

#### Cách đọc basis trend

```
Biểu đồ Basis (30 phút):

Premium
  +8 │     ╱╲
  +5 │   ╱    ╲        ← Basis thu hẹp dần (hội tụ)
  +3 │ ╱        ╲
   0 │────────────╲──── Zero line
  -2 │              ╲  ← Chuyển sang discount (BASIS_DIVERGENCE alert!)
  -5 │
Discount
     └──────────────────→ Thời gian
```

| Tín hiệu | Ý nghĩa | Gợi ý |
|-----------|---------|-------|
| Premium cao (> +5 điểm) | Kỳ vọng tăng mạnh, hoặc short squeeze trên phái sinh | Cẩn thận — premium cao thường mean-revert |
| Premium giảm dần về 0 | Hội tụ — basis co lại | Kỳ vọng tăng đang yếu đi |
| Chuyển từ Premium → Discount | **Đảo chiều** (alert BASIS_DIVERGENCE) | Tín hiệu bearish mạnh |
| Discount sâu (< -5 điểm) | Panic sell trên phái sinh, hoặc hedging lớn | Có thể là cơ hội nếu spot ổn định |
| Basis dao động quanh 0 | Thị trường cân bằng, không kỳ vọng rõ ràng | Sideway, chờ tín hiệu |

**Convergence Indicator**:
- Hệ thống tính slope (độ dốc) của basis theo thời gian
- **Hội tụ**: basis đang tiến về 0 → thị trường đang tìm cân bằng
- **Phân kỳ**: basis đang rời xa 0 → kỳ vọng đang mạnh lên (bull hoặc bear)

#### Ứng dụng thực tế

**Chiến thuật Basis Reversion**:
1. Basis premium > +8 → kỳ vọng basis sẽ co lại → short VN30F
2. Basis discount < -8 → kỳ vọng basis sẽ mở rộng → long VN30F
3. Kết hợp với NDTNN: nếu NDTNN mua ròng + basis premium → xác nhận uptrend

---

### 6.4. Hệ thống cảnh báo — Logic phát hiện tín hiệu

4 loại cảnh báo được tính toán real-time từ dữ liệu thị trường:

#### VOLUME_SPIKE — Đột biến khối lượng

```
Điều kiện: LastVol > 3× trung bình 20 phút
Tối thiểu: cần ≥ 10 giao dịch trong window (tránh false positive)

Ví dụ:
  VNM trung bình 20 phút: 500 cp/giao dịch
  Giao dịch mới: LastVol = 2000 cp
  → Ratio = 2000 / 500 = 4.0x → VOLUME_SPIKE (severity: WARNING)

  Message: "VNM vol spike: 2,000 (4.0x avg)"
```

**Cách đọc**: Volume spike thường xảy ra khi:
- Có tin tốt/xấu → giá sẽ biến động mạnh sau đó
- Block trade (giao dịch lớn của tổ chức)
- Kết hợp với mua/bán chủ động: spike + mua chủ động → bullish, spike + bán chủ động → bearish

#### PRICE_BREAKOUT — Chạm trần/sàn

```
Điều kiện: LastPrice >= Ceiling HOẶC LastPrice <= Floor
Severity: CRITICAL (luôn luôn)

Ví dụ:
  HPG: Ceiling = 27.8, Floor = 24.2
  Giao dịch: LastPrice = 27.8
  → PRICE_BREAKOUT: "HPG hit ceiling 27,800"
```

**Cách đọc**:
- Chạm trần: cầu vượt cung cực mạnh, có thể tiếp tục tăng phiên sau
- Chạm sàn: cung vượt cầu cực mạnh, panic sell
- Kết hợp: trần + NDTNN mua ròng → tín hiệu rất mạnh, có thể tăng nhiều phiên

#### FOREIGN_ACCELERATION — Gia tốc NDTNN

```
Điều kiện: |Net_value_hiện_tại - Net_value_5phút_trước| / |Net_value_5phút_trước| > 30%
Bộ lọc: Chỉ khi |Net_value_5phút_trước| > 1 tỷ VND (lọc noise mã nhỏ)

Ví dụ:
  VNM: Net value 5 phút trước = +10 tỷ
       Net value hiện tại    = +14 tỷ
  → Change = |14-10|/|10| = 40% > 30%
  → FOREIGN_ACCELERATION: "VNM foreign buying accel 40% in 5min"
```

**Cách đọc**: Gia tốc NDTNN cho biết foreign đang thay đổi hành vi:
- Acceleration buying → NDTNN đang tăng tốc mua, có thể có thông tin từ quỹ ngoại
- Acceleration selling → NDTNN đang xả mạnh hơn

#### BASIS_DIVERGENCE — Đảo chiều Basis

```
Điều kiện: Basis chuyển dấu (premium ↔ discount)
Lần trước: is_premium = True (premium)
Lần này:   is_premium = False (discount)
→ BASIS_DIVERGENCE: "Basis flipped premium→discount: -1.50 (-0.117%)"
```

**Cách đọc**: Đây là tín hiệu hiếm nhưng quan trọng:
- Premium → Discount: kỳ vọng tăng đã biến mất, có thể bắt đầu downtrend
- Discount → Premium: kỳ vọng giảm đã biến mất, có thể bắt đầu uptrend

#### Deduplication

Mỗi cặp `(alert_type, symbol)` chỉ được phát 1 lần trong **60 giây**. Tránh spam khi cùng mã liên tục trigger (ví dụ: mã chạm trần, mỗi giao dịch đều = ceiling → chỉ alert 1 lần/phút).

---

### 6.5. Pipeline xử lý dữ liệu tổng thể

```
SSI WebSocket (fc-datahub.ssi.com.vn)
        │
        ▼
  parse_message_multi()        ← Tách message X:ALL thành Trade + Quote
        │
        ├── Quote Message
        │   └── QuoteCache.update()     ← Lưu Bid1/Ask1 mới nhất
        │
        ├── Trade Message
        │   ├── VN30F* symbol?
        │   │   ├── Có → DerivativesTracker    ← Basis = futures - spot
        │   │   │        └── PriceTracker.on_basis_update()
        │   │   └── Không → TradeClassifier     ← So sánh giá vs bid/ask
        │   │               └── SessionAggregator ← Tích lũy theo phiên
        │   └── PriceTracker.on_trade()          ← Kiểm tra spike + breakout
        │
        ├── Foreign Message (R:ALL)
        │   └── ForeignInvestorTracker   ← Delta, speed, acceleration
        │       └── PriceTracker.on_foreign() ← Kiểm tra acceleration
        │
        └── Index Message (MI:ALL)
            └── IndexTracker             ← VN30/VNINDEX + breadth
```

**Toàn bộ pipeline xử lý < 5ms per message**, đảm bảo dữ liệu hiển thị trên UI gần như real-time.

---

### 6.6. Kịch bản phân tích tổng hợp (Playbook)

#### Kịch bản 1: Phát hiện "Smart Money" đang mua

**Các tín hiệu cần kiểm tra đồng thời**:
1. Volume Analysis: Mua chủ động > 65%, volume tăng
2. Foreign Flow: NDTNN mua ròng, acceleration > 0
3. Signals: VOLUME_SPIKE + FOREIGN_ACCELERATION trên cùng mã

**Ví dụ**: 10:30 sáng, trên bảng giá VNM:
- Mua chủ động: 68%, Bán chủ động: 25%
- NDTNN: mua ròng +15 tỷ, speed tăng
- Alert: VOLUME_SPIKE (VNM, 3.5x avg)
→ **Kết luận**: Smart money đang tích lũy VNM

#### Kịch bản 2: Phát hiện phân phối (Distribution)

**Tín hiệu**:
1. Giá tăng nhẹ hoặc đi ngang nhưng Bán chủ động > Mua chủ động
2. NDTNN bán ròng với acceleration tăng
3. Volume tổng tăng nhưng phần lớn là bán chủ động

→ **Kết luận**: Giá được "giữ" trong khi bên bán xả hàng. Nguy hiểm.

#### Kịch bản 3: Dự đoán xu hướng qua Basis

**Tín hiệu**:
1. Basis chuyển từ discount sang premium (alert BASIS_DIVERGENCE)
2. NDTNN mua ròng trên phái sinh (kiểm tra VN30F volume)
3. Mua chủ động tăng trên rổ VN30

→ **Kết luận**: Cả spot lẫn futures đang bullish, uptrend có thể bắt đầu.

#### Kịch bản 4: Phiên ATC bất thường

**Tín hiệu**:
1. Volume Analysis → Session Comparison: ATC volume gấp 3x bình thường
2. ATC toàn bộ là trung lập (đúng theo thiết kế) nhưng giá khớp ATC thấp hơn liên tục
3. Foreign: NDTNN bán ròng tăng mạnh 14:30-14:45

→ **Kết luận**: Quỹ ngoại hoặc ETF rebalance cuối phiên, giá bị ép xuống tạm thời.

---

## 7. API Reference

### 7.1. Health Check

```
GET /health
```

Response:
```json
{
  "status": "ok",
  "database": "connected"  // hoặc "unavailable"
}
```

### 7.2. Market Data

**Snapshot toàn thị trường**:
```
GET /api/market/snapshot
```
Trả về: quotes (VN30), prices, indices (VN30/VNINDEX), foreign summary, derivatives data.

**Chi tiết NDTNN**:
```
GET /api/market/foreign-detail
```
Trả về: danh sách từng mã VN30 với buy/sell volume, speed, acceleration.

**Thống kê khối lượng**:
```
GET /api/market/volume-stats
```
Trả về: mua/bán/trung lập theo từng mã, bao gồm breakdown theo phiên ATO/Liên tục/ATC.

**Xu hướng basis**:
```
GET /api/market/basis-trend?minutes=30
```
Trả về: mảng BasisPoint[] trong 30 phút gần nhất.

**Cảnh báo**:
```
GET /api/market/alerts?limit=50&type=VOLUME_SPIKE&severity=CRITICAL
```
Trả về: danh sách cảnh báo, hỗ trợ filter theo type và severity.

### 7.3. Dữ liệu lịch sử

```
GET /api/history/{symbol}/candles?interval=1m&limit=100   # Nến OHLCV
GET /api/history/{symbol}/ticks?limit=500                  # Giao dịch chi tiết
GET /api/history/{symbol}/foreign?days=5                   # Lịch sử NDTNN
GET /api/history/{symbol}/foreign/daily                    # Tổng hợp NDTNN theo ngày
GET /api/history/index/{name}?days=5                       # Lịch sử chỉ số
GET /api/history/derivatives/{contract}?days=5             # Lịch sử hợp đồng
```

### 7.4. Prometheus Metrics

```
GET /metrics
```
Các metric được thu thập: HTTP request duration, SSI message counters, WebSocket connection counts, trade classifications, alerts generated, database writes.

---

## 8. WebSocket Real-time

### 8.1. Kết nối

```
ws://localhost/ws/{channel}?token={auth_token}
```

Token là tùy chọn. Nếu `WS_AUTH_TOKEN` được đặt trong `.env`, client phải cung cấp token qua query parameter.

### 8.2. Channels

| Channel | Endpoint | Dữ liệu | Tần suất |
|---------|----------|---------|----------|
| market | `/ws/market` | MarketSnapshot đầy đủ (quotes, indices, foreign, derivatives) | Mỗi giao dịch (throttle 500ms) |
| foreign | `/ws/foreign` | ForeignSummary (tổng hợp + top movers) | Mỗi cập nhật foreign (throttle 500ms) |
| index | `/ws/index` | VN30/VNINDEX data | Mỗi cập nhật index (throttle 500ms) |
| alerts | `/ws/alerts` | Alert notifications | Khi có cảnh báo mới |

### 8.3. Giới hạn

- Tối đa **5 kết nối/IP** (mặc định, cấu hình qua `WS_MAX_CONNECTIONS_PER_IP`)
- Heartbeat: ping mỗi 30s, timeout 10s
- Queue size: 50 message/client (client chậm sẽ bị drop message cũ)

### 8.4. Ví dụ kết nối (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost/ws/market');

ws.onopen = () => console.log('Connected');

ws.onmessage = (event) => {
  const snapshot = JSON.parse(event.data);
  console.log('VN30:', snapshot.indices?.VN30?.value);
  console.log('Stocks:', Object.keys(snapshot.prices || {}).length);
};

ws.onclose = () => console.log('Disconnected');
```

---

## 9. Giám sát hệ thống (Monitoring)

### 9.1. Prometheus

- **URL**: http://localhost:9090
- **Scrape interval**: 30 giây
- **Retention**: 30 ngày
- **Target**: `/metrics` endpoint của backend

**Các metric chính**:
- `http_request_duration_seconds` — Thời gian xử lý HTTP request
- `ssi_messages_total` — Tổng số message SSI nhận được
- `ws_connections_active` — Số kết nối WebSocket hiện tại
- `trade_classifications_total` — Số giao dịch đã phân loại
- `alerts_generated_total` — Số cảnh báo đã tạo
- `db_writes_total` — Số lần ghi database

### 9.2. Grafana

- **URL**: http://localhost:3000
- **Đăng nhập**: admin / (password trong `GRAFANA_PASSWORD` env)

**4 Dashboard tự động**:

1. **Application Performance** — Request rates, latencies, error counts
2. **WebSocket Monitoring** — Connected clients, message throughput
3. **Database Health** — Pool connections, query latency
4. **System Metrics** — CPU, memory, disk (qua Node Exporter)

### 9.3. Kiểm tra sức khỏe hệ thống

```bash
# Trạng thái tất cả container
docker compose -f docker-compose.prod.yml ps

# Log real-time
docker compose -f docker-compose.prod.yml logs -f

# Log một service cụ thể
docker compose -f docker-compose.prod.yml logs -f backend

# Tài nguyên
docker stats
```

---

## 10. Xử lý sự cố

### 10.1. Backend không khởi động

**Triệu chứng**: Container backend thoát ngay sau khi start

**Giải pháp**:
1. Kiểm tra log: `docker compose -f docker-compose.prod.yml logs backend`
2. Xác nhận `.env` có SSI credentials
3. Kiểm tra port 8000 chưa bị chiếm

### 10.2. Nginx trả về 502 Bad Gateway

**Nguyên nhân**: Backend chưa sẵn sàng hoặc health check thất bại

**Giải pháp**:
```bash
# Đợi backend healthy
docker compose -f docker-compose.prod.yml logs -f backend | grep -i "started"

# Kiểm tra Nginx logs
docker compose -f docker-compose.prod.yml logs nginx
```

### 10.3. SSI Stream không kết nối được (502)

**Nguyên nhân phổ biến nhất**: Sai `SSI_STREAM_URL`

**Giải pháp**:
1. Xác nhận `SSI_STREAM_URL=https://fc-datahub.ssi.com.vn/` (KHÔNG phải `fc-data.ssi.com.vn`)
2. Restart backend: `docker compose -f docker-compose.prod.yml restart backend`
3. Kiểm tra log: `docker compose -f docker-compose.prod.yml logs backend | grep -i "stream\|signalr"`

### 10.4. WebSocket không kết nối được

**Kiểm tra**:
1. Nginx có header WebSocket upgrade (`proxy_set_header Upgrade $http_upgrade`)
2. Backend health check pass
3. `WS_AUTH_TOKEN` có yêu cầu token không? Client có gửi token đúng không?

### 10.5. Frontend hiển thị trang trắng

**Giải pháp**:
```bash
# Kiểm tra frontend logs
docker compose -f docker-compose.prod.yml logs frontend

# Kiểm tra static files
docker compose -f docker-compose.prod.yml exec frontend ls -la /usr/share/nginx/html/dist/
```

### 10.6. Database không kết nối

**Lưu ý**: Hệ thống có **graceful startup** — dữ liệu market (quotes, trades, foreign, index) vẫn hoạt động bình thường khi không có database. Chỉ các endpoint lịch sử (`/api/history/*`) trả về 503.

```bash
# Kiểm tra TimescaleDB
docker compose -f docker-compose.prod.yml logs timescaledb

# Kiểm tra kết nối
docker compose -f docker-compose.prod.yml exec timescaledb pg_isready -U stockuser
```

### 10.7. Dữ liệu không cập nhật

**Kiểm tra theo thứ tự**:
1. Thời gian hiện tại có trong giờ giao dịch? (9:00-15:00, T2-T6, giờ VN)
2. SSI credentials còn hiệu lực?
3. Backend log có error?
4. WebSocket status trên UI là "Live" hay "Polling"?

---

## 11. Hướng dẫn vận hành hàng ngày

### 11.1. Khi nào mở web?

Mở trình duyệt truy cập **http://localhost** trong giờ giao dịch để xem dữ liệu real-time:

| Phiên | Giờ (VN) | Dữ liệu |
|-------|---------|---------|
| ATO | 9:00 - 9:15 | Khớp lệnh mở cửa |
| Liên tục sáng | 9:15 - 11:30 | Real-time đầy đủ |
| Nghỉ trưa | 11:30 - 13:00 | Dữ liệu đóng băng (phiên sáng) |
| Liên tục chiều | 13:00 - 14:30 | Real-time đầy đủ |
| ATC | 14:30 - 14:45 | Khớp lệnh đóng cửa |
| PLO | 14:45 - 15:00 | Giao dịch thỏa thuận |

**Ngoài giờ giao dịch**: Web vẫn truy cập được, hiển thị dữ liệu cuối phiên gần nhất. SSI WebSocket sẽ tự động thử kết nối lại (có thể trả 502 — đây là bình thường). Khi phiên giao dịch mới bắt đầu (9:00 sáng T2-T6), dữ liệu sẽ tự động chảy trở lại.

### 11.2. Có cần bật webapp hàng ngày không?

**Không.** Hệ thống chạy hoàn toàn tự động nhờ Docker `restart: unless-stopped`:

- **Backend** tự khởi động cùng Docker, tự kết nối SSI khi có phiên giao dịch
- **Nếu SSI mất kết nối** (lỗi mạng, SSI bảo trì, ngoài giờ giao dịch) → backend tự reconnect với backoff tăng dần (2s → 4s → 8s → ... → 60s max), khi SSI sẵn sàng sẽ tự kết nối lại
- **Dữ liệu phiên reset tự động** lúc 15:05 hàng ngày (sau khi thị trường đóng cửa)
- **Nếu máy tính khởi động lại** → Docker tự start lại tất cả container

Bạn chỉ cần can thiệp thủ công khi:
- Thay đổi cấu hình (`.env`) → cần restart: `docker compose up -d backend`
- Cập nhật code mới → cần rebuild: `docker compose build backend && docker compose up -d backend`
- Kiểm tra sự cố → xem log: `docker logs stock-tracker-backend-1 --tail 50`

### 11.3. Dữ liệu có được lưu trữ không? Lưu ở đâu?

**Có.** Hệ thống lưu trữ 2 lớp:

#### Lớp 1: Bộ nhớ (RAM) — Dữ liệu phiên hiện tại

Dữ liệu real-time trong phiên giao dịch được giữ trong RAM:
- Bảng giá, bid/ask, sparkline
- Tổng hợp mua/bán chủ động
- Dòng tiền NDTNN (tốc độ, gia tốc)
- Basis phái sinh, cảnh báo

**Reset tự động** lúc 15:05 hàng ngày → sáng hôm sau bắt đầu từ 0.

#### Lớp 2: TimescaleDB — Dữ liệu lịch sử (lưu vĩnh viễn)

Dữ liệu được ghi tự động vào database TimescaleDB (PostgreSQL), lưu trên ổ đĩa máy tính qua Docker volume:

| Bảng | Dữ liệu | Mục đích |
|------|---------|---------|
| `tick_data` | Từng giao dịch (giá, khối lượng, mua/bán chủ động) | Tra cứu chi tiết |
| `candles_1m` | Nến 1 phút (OHLCV + mua/bán chủ động) | Biểu đồ kỹ thuật |
| `foreign_flow` | Snapshot NDTNN từng mã | Phân tích dòng vốn ngoại |
| `index_snapshots` | Giá trị VN30/VNINDEX | Theo dõi chỉ số |
| `derivatives` | VN30F giá + basis + open interest | Phân tích phái sinh |

**Vị trí lưu trữ trên máy**: Docker volume `stock-tracker_pgdata`

```bash
# Xem vị trí volume trên ổ đĩa
docker volume inspect stock-tracker_pgdata

# Xem dung lượng database
docker exec stock-tracker-timescaledb-1 psql -U stock -d stock_tracker \
  -c "SELECT hypertable_name, pg_size_pretty(hypertable_size(format('%I', hypertable_name)::regclass)) FROM timescaledb_information.hypertables;"
```

**Truy cập dữ liệu lịch sử** qua API:
```bash
# Nến 1 phút VNM, 100 cây gần nhất
curl http://localhost/api/history/VNM/candles?interval=1m&limit=100

# Giao dịch chi tiết VNM
curl http://localhost/api/history/VNM/ticks?limit=500

# NDTNN VNM 5 ngày
curl http://localhost/api/history/VNM/foreign?days=5

# Tổng hợp NDTNN theo ngày
curl http://localhost/api/history/VNM/foreign/daily
```

#### Lưu ý quan trọng về dữ liệu

- **Dữ liệu chỉ ghi khi backend đang chạy** — nếu backend tắt trong giờ giao dịch, phần dữ liệu đó sẽ bị mất
- **Xóa volume = mất toàn bộ lịch sử**: Lệnh `docker compose down -v` sẽ xóa volume. Chỉ dùng `docker compose down` (không có `-v`) khi dừng hệ thống
- **Backup**: Copy Docker volume hoặc dùng `pg_dump`:
  ```bash
  docker exec stock-tracker-timescaledb-1 pg_dump -U stock stock_tracker > backup.sql
  ```
- **Không có database cũng chạy được**: Nếu TimescaleDB không khởi động, backend vẫn hoạt động bình thường với dữ liệu real-time (chỉ mất lịch sử)

---

## 12. FAQ

**Q: Lấy SSI Consumer ID và Secret ở đâu?**
A: Đăng ký tài khoản SSI iBoard tại website SSI, sau đó đăng ký sử dụng FastConnect API.

**Q: Hệ thống hỗ trợ bao nhiêu mã?**
A: Hiện tại tập trung vào VN30 (30 mã). Schema hỗ trợ mở rộng tới 500+ mã.

**Q: Dữ liệu có lưu lịch sử không?**
A: Có. TimescaleDB lưu trades, foreign snapshots, index snapshots, basis points. Dữ liệu lưu vĩnh viễn trên Docker volume `stock-tracker_pgdata` (trừ khi bạn xóa volume). Truy cập qua `/api/history/*` endpoints. Xem chi tiết tại [Mục 11.3](#113-dữ-liệu-có-được-lưu-trữ-không-lưu-ở-đâu).

**Q: Có cần bật web hàng ngày không?**
A: Không. Hệ thống chạy tự động 24/7 nhờ Docker. Backend tự kết nối SSI khi có phiên giao dịch, tự reconnect khi mất kết nối. Bạn chỉ cần mở trình duyệt khi muốn xem dữ liệu. Xem chi tiết tại [Mục 11.2](#112-có-cần-bật-webapp-hàng-ngày-không).

**Q: Có thể dùng ngoài giờ giao dịch không?**
A: Có, nhưng dữ liệu sẽ là dữ liệu cuối phiên. Dữ liệu RAM reset lúc 15:05 hàng ngày, dữ liệu lịch sử trong TimescaleDB được giữ lại.

**Q: Giờ giao dịch sàn HOSE?**
A:
| Phiên | Giờ (VN) |
|-------|---------|
| ATO (Khớp lệnh mở cửa) | 9:00 - 9:15 |
| Liên tục (Continuous) | 9:15 - 11:30 |
| Nghỉ trưa | 11:30 - 13:00 |
| Liên tục (Continuous) | 13:00 - 14:30 |
| ATC (Khớp lệnh đóng cửa) | 14:30 - 14:45 |
| PLO (Put-through/Thỏa thuận) | 14:45 - 15:00 |

**Q: Node Exporter không chạy trên macOS?**
A: Đúng. Node Exporter cần mount `rslave` không được hỗ trợ trên Docker Desktop (macOS). Bỏ qua service này, các metric system sẽ không có trong Grafana nhưng không ảnh hưởng chức năng chính.

**Q: Làm sao kiểm tra hiệu năng?**
A: Chạy load test:
```bash
# Quick test (10 users, 30s)
./scripts/run-load-test.sh --users 10 --duration 30

# Full test với Locust UI
docker compose -f docker-compose.test.yml up
# Truy cập Locust UI: http://localhost:8089
```

**Q: Làm sao chạy unit tests?**
A:
```bash
cd backend
./venv/bin/pytest -v                              # Tất cả tests
./venv/bin/pytest --cov=app --cov-fail-under=80   # Với coverage
./venv/bin/pytest tests/e2e/ -v                   # Chỉ E2E
```

---

## Phụ lục: Kiến trúc hệ thống

```
SSI FastConnect WebSocket (fc-datahub.ssi.com.vn)
    │
    ├── X:ALL ──→ parse_message_multi() ──→ Trade + Quote
    ├── R:ALL ──→ Foreign Investor data
    ├── MI:ALL ──→ Index data (VN30, VNINDEX)
    └── B:ALL ──→ OHLC bars
         │
         ▼
    FastAPI Backend (MarketDataProcessor)
    ├── QuoteCache          (cache bid/ask)
    ├── TradeClassifier     (phân loại mua/bán chủ động)
    ├── SessionAggregator   (tổng hợp theo phiên ATO/Liên tục/ATC)
    ├── ForeignInvestorTracker (delta, speed, acceleration)
    ├── IndexTracker        (VN30, VNINDEX, breadth)
    ├── DerivativesTracker  (basis VN30F - VN30)
    ├── AlertService        (4 loại cảnh báo, dedup 60s)
    └── PriceTracker        (phát hiện tín hiệu)
         │
         ├──→ REST API (polling)
         ├──→ WebSocket (4 channels, real-time)
         ├──→ TimescaleDB (lưu lịch sử)
         └──→ Prometheus (metrics)
              └──→ Grafana (dashboards)
```
