from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
import uuid
from datetime import datetime

import database

app = FastAPI(title="Factory Inventory Management System")

database.init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    unit_cost: float
    location: str
    last_updated: str

class Order(BaseModel):
    id: str
    order_number: str
    customer: str
    items: List[dict]
    status: str
    order_date: str
    expected_delivery: str
    total_value: float
    actual_delivery: Optional[str] = None
    warehouse: Optional[str] = None
    category: Optional[str] = None

class DemandForecast(BaseModel):
    id: str
    item_sku: str
    item_name: str
    current_demand: int
    forecasted_demand: int
    trend: str
    period: str

class BacklogItem(BaseModel):
    id: str
    order_id: str
    item_sku: str
    item_name: str
    quantity_needed: int
    quantity_available: int
    days_delayed: int
    priority: str
    has_purchase_order: Optional[bool] = False

class PurchaseOrder(BaseModel):
    id: str
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    status: str
    created_date: str
    notes: Optional[str] = None

class CreatePurchaseOrderRequest(BaseModel):
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    notes: Optional[str] = None

class Task(BaseModel):
    id: str
    title: str
    status: str
    created_date: str

class CreateTaskRequest(BaseModel):
    title: str

# In-memory task store
_tasks: list[dict] = []

# API endpoints
@app.get("/")
def root():
    return {"message": "Factory Inventory Management System API", "version": "1.0.0"}

@app.get("/api/inventory", response_model=List[InventoryItem])
def get_inventory(warehouse: Optional[str] = None, category: Optional[str] = None):
    return database.get_inventory(warehouse, category)

@app.get("/api/inventory/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: str):
    item = database.get_inventory_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/api/orders", response_model=List[Order])
def get_orders(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None,
):
    return database.get_orders(warehouse, category, status, month)

@app.get("/api/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    order = database.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/demand", response_model=List[DemandForecast])
def get_demand_forecasts():
    return database.get_demand_forecasts()

@app.get("/api/backlog", response_model=List[BacklogItem])
def get_backlog():
    return database.get_backlog_items()

@app.get("/api/dashboard/summary")
def get_dashboard_summary(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None,
):
    filtered_inventory = database.get_inventory(warehouse, category)
    filtered_orders = database.get_orders(warehouse, category, status, month)
    all_backlog = database.get_backlog_items()

    total_inventory_value = sum(
        item["quantity_on_hand"] * item["unit_cost"] for item in filtered_inventory
    )
    low_stock_items = len(
        [item for item in filtered_inventory if item["quantity_on_hand"] <= item["reorder_point"]]
    )
    pending_orders = len(
        [o for o in filtered_orders if o["status"] in ["Processing", "Backordered"]]
    )

    return {
        "total_inventory_value": round(total_inventory_value, 2),
        "low_stock_items": low_stock_items,
        "pending_orders": pending_orders,
        "total_backlog_items": len(all_backlog),
        "total_orders_value": sum(o["total_value"] for o in filtered_orders),
    }

@app.get("/api/spending/summary")
def get_spending_summary():
    return database.get_spending_summary()

@app.get("/api/spending/monthly")
def get_monthly_spending():
    return database.get_monthly_spending()

@app.get("/api/spending/categories")
def get_category_spending():
    return database.get_category_spending()

@app.get("/api/spending/transactions")
def get_recent_transactions():
    return database.get_transactions()

@app.get("/api/reports/quarterly")
def get_quarterly_reports():
    orders = database.get_orders()
    quarters = {}
    quarter_map = {
        "Q1-2025": ["2025-01", "2025-02", "2025-03"],
        "Q2-2025": ["2025-04", "2025-05", "2025-06"],
        "Q3-2025": ["2025-07", "2025-08", "2025-09"],
        "Q4-2025": ["2025-10", "2025-11", "2025-12"],
    }

    for order in orders:
        order_date = order.get("order_date", "")
        quarter = next(
            (q for q, months in quarter_map.items() if any(m in order_date for m in months)),
            None,
        )
        if not quarter:
            continue
        if quarter not in quarters:
            quarters[quarter] = {
                "quarter": quarter,
                "total_orders": 0,
                "total_revenue": 0,
                "delivered_orders": 0,
                "avg_order_value": 0,
            }
        quarters[quarter]["total_orders"] += 1
        quarters[quarter]["total_revenue"] += order.get("total_value", 0)
        if order.get("status") == "Delivered":
            quarters[quarter]["delivered_orders"] += 1

    result = []
    for q, data in quarters.items():
        if data["total_orders"] > 0:
            data["avg_order_value"] = round(data["total_revenue"] / data["total_orders"], 2)
            data["fulfillment_rate"] = round(
                (data["delivered_orders"] / data["total_orders"]) * 100, 1
            )
        result.append(data)

    result.sort(key=lambda x: x["quarter"])
    return result

@app.get("/api/reports/monthly-trends")
def get_monthly_trends():
    orders = database.get_orders()
    months = {}

    for order in orders:
        order_date = order.get("order_date", "")
        if not order_date:
            continue
        month = order_date[:7]
        if month not in months:
            months[month] = {"month": month, "order_count": 0, "revenue": 0, "delivered_count": 0}
        months[month]["order_count"] += 1
        months[month]["revenue"] += order.get("total_value", 0)
        if order.get("status") == "Delivered":
            months[month]["delivered_count"] += 1

    result = list(months.values())
    result.sort(key=lambda x: x["month"])
    return result

@app.get("/api/tasks", response_model=List[Task])
def get_tasks():
    return _tasks

@app.post("/api/tasks", response_model=Task, status_code=201)
def create_task(request: CreateTaskRequest):
    task = {
        "id": str(uuid.uuid4()),
        "title": request.title,
        "status": "pending",
        "created_date": datetime.now().isoformat(),
    }
    _tasks.append(task)
    return task

@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    global _tasks
    original_len = len(_tasks)
    _tasks = [t for t in _tasks if t["id"] != task_id]
    if len(_tasks) == original_len:
        raise HTTPException(status_code=404, detail="Task not found")

@app.patch("/api/tasks/{task_id}", response_model=Task)
def toggle_task(task_id: str):
    for task in _tasks:
        if task["id"] == task_id:
            task["status"] = "completed" if task["status"] == "pending" else "pending"
            return task
    raise HTTPException(status_code=404, detail="Task not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
