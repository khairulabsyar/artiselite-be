# WMS Dashboard API Documentation

This document provides the API specification for the Warehouse Management System (WMS) dashboard endpoints.

---

## 1. Get Dashboard Summary

Provides a high-level summary of key warehouse metrics.

- **Endpoint**: `GET /api/dashboard/summary/`
- **Method**: `GET`
- **Authentication**: Required (Token-based)

### Response Body (Success: 200 OK)

A JSON object containing summary statistics.

**Example Response:**
```json
{
    "total_inventory_items": 152,
    "today_inbound": 8,
    "today_outbound": 12,
    "low_stock_alerts": 5
}
```

### Field Descriptions:
- `total_inventory_items` (integer): The total count of active (non-archived) products in the inventory.
- `today_inbound` (integer): The number of completed inbound shipments for the current day.
- `today_outbound` (integer): The number of completed outbound shipments for the current day.
- `low_stock_alerts` (integer): The number of active products whose quantity is at or below their defined low stock threshold.

---

## 2. Get Recent Activity

Retrieves the 20 most recent activity logs from across the system.

- **Endpoint**: `GET /api/dashboard/activity/`
- **Method**: `GET`
- **Authentication**: Required (Token-based)

### Response Body (Success: 200 OK)

A JSON array of activity log objects.

**Example Response:**
```json
[
    {
        "id": 101,
        "actor": "testuser",
        "verb": "updated",
        "action_object": "Product: Product A (PROD-A)",
        "timestamp": "2025-07-06T21:30:00Z",
        "changes": {
            "quantity": [
                95,
                100
            ]
        }
    },
    {
        "id": 100,
        "actor": "admin",
        "verb": "created",
        "action_object": "Inbound: Shipment #123",
        "timestamp": "2025-07-06T20:15:00Z",
        "changes": {}
    }
]
```

### Field Descriptions:
- `id` (integer): The unique ID of the log entry.
- `actor` (string): The username of the user who performed the action.
- `verb` (string): A description of the action taken (e.g., 'created', 'updated', 'deleted').
- `action_object` (string): A string representation of the object that was acted upon.
- `timestamp` (datetime): The ISO 8601 timestamp of when the action occurred.
- `changes` (object): A dictionary detailing the fields that were changed and their old/new values.

---

## 3. Get Transaction Volume

Provides daily inbound and outbound transaction counts for a specified number of past days.

- **Endpoint**: `GET /api/dashboard/transaction-volume/`
- **Method**: `GET`
- **Authentication**: Required (Token-based)

### Query Parameters
- `days` (integer, optional, default: 7): The number of days of transaction data to retrieve, including today.

**Example Request:**
`/api/dashboard/transaction-volume/?days=5`

### Response Body (Success: 200 OK)

A JSON array of objects, where each object represents a day and its transaction counts.

**Example Response (for `?days=5`):
```json
[
    {
        "date": "2025-07-02",
        "inbound": 5,
        "outbound": 8
    },
    {
        "date": "2025-07-03",
        "inbound": 7,
        "outbound": 6
    },
    {
        "date": "2025-07-04",
        "inbound": 3,
        "outbound": 10
    },
    {
        "date": "2025-07-05",
        "inbound": 10,
        "outbound": 12
    },
    {
        "date": "2025-07-06",
        "inbound": 8,
        "outbound": 12
    }
]
```

### Field Descriptions:
- `date` (date): The date (YYYY-MM-DD) for the transaction counts.
- `inbound` (integer): The total number of completed inbound shipments on that date.
- `outbound` (integer): The total number of completed outbound shipments on that date.
