# DMS API Reference

Base URL: `https://api.yourdomain.com`

All endpoints require `Authorization: Bearer <access_token>` except where noted.

---

## Authentication

### POST /api/method/dms.api.auth.login
**Public** — no token required.

Request:
```json
{ "email": "user@example.com", "password": "secret" }
```

Response 200:
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "user@example.com",
      "email": "user@example.com",
      "full_name": "Rahul Sharma",
      "role": "honda_manager",
      "company": "Honda",
      "company_id": "HONDA-00001",
      "avatar": null,
      "is_active": true
    },
    "tokens": {
      "access_token": "eyJ...",
      "refresh_token": "eyJ...",
      "expires_in": 28800,
      "token_type": "Bearer"
    }
  }
}
```

Response 401:
```json
{ "success": false, "message": "Invalid email or password." }
```

---

### POST /api/method/dms.api.auth.logout
Invalidates current session.

Response 200:
```json
{ "success": true, "message": "Logged out successfully" }
```

---

### POST /api/method/dms.api.auth.refresh
**Public** — uses refresh token.

Request:
```json
{ "refresh_token": "eyJ..." }
```

Response 200:
```json
{
  "success": true,
  "data": { "access_token": "eyJ...", "expires_in": 28800 }
}
```

---

### GET /api/method/dms.api.auth.me
Returns current user profile.

---

## Leads

### GET /api/method/dms.api.leads.get_leads

Query params: `page`, `page_size`, `status`, `source`, `search`, `date_from`, `date_to`, `assigned_to`

Response 200:
```json
{
  "success": true,
  "data": {
    "data": [
      {
        "id": "LEAD-HON-2024-00001",
        "lead_name": "Priya Nair",
        "email": "priya@example.com",
        "mobile_no": "9876543210",
        "status": "Open",
        "source": "Website",
        "company_id": "HONDA-00001",
        "vehicle_interest": "Honda City",
        "created_at": "2024-01-15T10:30:00Z"
      }
    ],
    "total": 142,
    "page": 1,
    "page_size": 20,
    "total_pages": 8
  }
}
```

### POST /api/method/dms.api.leads.create_lead
```json
{
  "lead_name": "Amit Kumar",
  "email": "amit@example.com",
  "mobile_no": "9876543211",
  "status": "New",
  "source": "Walk-in",
  "vehicle_interest": "Honda Amaze"
}
```

### PUT /api/method/dms.api.leads.update_lead
```json
{ "lead_id": "LEAD-HON-2024-00001", "status": "Opportunity" }
```

### DELETE /api/method/dms.api.leads.delete_lead
```json
{ "lead_id": "LEAD-HON-2024-00001" }
```

### POST /api/method/dms.api.leads.convert_to_customer
```json
{ "lead_id": "LEAD-HON-2024-00001" }
```
Response: `{ "customer_id": "CUST-HON-2024-00001" }`

---

## Customers

### GET /api/method/dms.api.customers.get_customers
Query params: `page`, `page_size`, `status`, `customer_type`, `search`

### POST /api/method/dms.api.customers.create_customer
```json
{
  "customer_name": "Sunita Rao",
  "email": "sunita@example.com",
  "mobile_no": "9876543212",
  "customer_type": "Individual",
  "city": "Bangalore"
}
```

---

## Sales

### GET /api/method/dms.api.sales.get_sales
Query params: `page`, `page_size`, `status`, `search`

### POST /api/method/dms.api.sales.create_sale
```json
{
  "customer_id": "CUST-HON-2024-00001",
  "vehicle_id": "VEH-HON-2024-00005",
  "sale_price": 1250000,
  "discount": 25000,
  "payment_mode": "Finance",
  "delivery_date": "2024-02-15"
}
```

### PATCH /api/method/dms.api.sales.update_sale_status
```json
{ "sale_id": "SALE-HON-2024-00001", "status": "Delivered" }
```

---

## Dashboard

### GET /api/method/dms.api.dashboard.get_honda_dashboard
### GET /api/method/dms.api.dashboard.get_nexa_dashboard
### GET /api/method/dms.api.dashboard.get_jaguar_dashboard
### GET /api/method/dms.api.dashboard.get_group_dashboard

All return the same structure with company-specific KPIs and chart data.

Response 200 (Honda example):
```json
{
  "success": true,
  "data": {
    "kpis": {
      "todays_sales": { "label": "Today's Sales", "value": 3, "change": 12.0, "change_type": "increase" },
      "monthly_revenue": { "label": "Monthly Revenue", "value": 4750000, "change": 8.0, "change_type": "increase", "prefix": "₹" }
    },
    "charts": {
      "monthly_sales_trend": [
        { "month": "Jan", "value": 24 },
        { "month": "Feb", "value": 31 }
      ],
      "lead_sources": [
        { "name": "Website", "value": 35, "color": "#E40521" }
      ]
    },
    "recent_leads": [...],
    "recent_sales": [...]
  }
}
```

---

## Error Responses

| Code | Meaning |
|------|---------|
| 400 | Bad Request — validation error |
| 401 | Unauthorized — missing or expired token |
| 403 | Forbidden — correct token but wrong company |
| 404 | Not Found |
| 409 | Conflict — duplicate record |
| 429 | Too Many Requests — rate limited |
| 500 | Internal Server Error |

Error body:
```json
{ "success": false, "data": null, "message": "Human-readable error" }
```
