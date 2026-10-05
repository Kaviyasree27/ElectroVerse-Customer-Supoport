import os
import json
import base64
import re
import random
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import config, database, llm_client

# Initialize SQLite database schema and seed data on startup
database.init_db()

app = FastAPI(
    title="ElectroVerse Multi-Agent API",
    description="Autonomous Electronics Multi-Agent Platform with Groq, Human Handoff & Multimodal Vision",
    version="1.0.0"
)

# Enable CORS for local Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static product images directly
images_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "images"))
if os.path.exists(images_dir):
    app.mount("/images", StaticFiles(directory=images_dir), name="images")

# --- Pydantic Request Models ---
class ApiKeyUpdate(BaseModel):
    api_key: str

class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str

class ChatMessageRequest(BaseModel):
    session_id: str
    message: str
    user_name: Optional[str] = "Customer"
    user_email: Optional[str] = None
    user_role: Optional[str] = "customer"
    order_id: Optional[str] = None
    image_base64: Optional[str] = None

class HumanResponseRequest(BaseModel):
    ticket_id: str
    session_id: str
    response_message: str
    action: Optional[str] = "REPLY"  # 'REPLY', 'APPROVE_REFUND', 'RESOLVE'

class CartItemRequest(BaseModel):
    session_id: str
    product_id: str
    quantity: int = 1

# --- Endpoints ---

@app.post("/api/auth/login")
def login_user(body: LoginRequest):
    """
    Role-Based Authentication:
    1. Static Admin Credentials: admin123@gmail.com / admin27 -> grants admin role
    2. Customer Credentials: Looked up from SQLite users table -> grants customer role
    """
    email = body.email.strip().lower()
    password = body.password.strip()

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password cannot be empty.")

    # 1. Static Admin Verification
    if email == "admin123@gmail.com":
        if password == "admin27":
            return {
                "status": "success",
                "user": {
                    "email": "admin123@gmail.com",
                    "name": "System Administrator",
                    "role": "admin"
                },
                "message": "Admin login successful! Welcome to the CommerceOS Operations Command Center."
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid admin password. Please try again.")

    # 2. Customer Database Verification
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, password, name, role FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="No customer account found with that email. Please sign up first.")

    if user["password"] != password:
        raise HTTPException(status_code=401, detail="Incorrect password. Please verify and try again.")

    return {
        "status": "success",
        "user": {
            "email": user["email"],
            "name": user["name"],
            "role": user["role"]
        },
        "message": f"Welcome back, {user['name']}! Login successful."
    }

@app.post("/api/auth/signup")
def signup_user(body: SignupRequest):
    """
    Registers a new customer account with their own Gmail and password.
    """
    name = body.name.strip()
    email = body.email.strip().lower()
    password = body.password.strip()

    if not name or not email or not password:
        raise HTTPException(status_code=400, detail="Name, Gmail address, and password are all required.")

    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Please provide a valid Gmail/email address.")

    if email == "admin123@gmail.com":
        raise HTTPException(status_code=400, detail="admin123@gmail.com is reserved for administrator login.")

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    existing = cursor.fetchone()

    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="An account with this email already exists. Please log in.")

    cursor.execute("""
    INSERT INTO users (email, password, name, role, created_at)
    VALUES (?, ?, ?, 'customer', datetime('now'))
    """, (email, password, name))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "user": {
            "email": email,
            "name": name,
            "role": "customer"
        },
        "message": f"Account created successfully! Welcome to CommerceOS, {name}."
    }

@app.get("/api/status")
def get_system_status():
    """Returns AI engine status (Groq vs Ollama), models, and guardrail limits."""
    llm_info = llm_client.check_llm_status()
    return {
        "status": "online",
        "llm": llm_info,
        "guardrails": {
            "max_auto_refund": config.MAX_AUTO_REFUND_AMOUNT,
            "return_policy_days": config.RETURN_POLICY_DAYS,
            "triage_temp": config.TEMPERATURE_TRIAGE,
            "support_temp": config.TEMPERATURE_SUPPORT,
            "shopper_temp": config.TEMPERATURE_SHOPPER
        }
    }

@app.post("/api/settings/key")
def update_api_key(body: ApiKeyUpdate):
    """Sets Groq API key dynamically without restarting server."""
    key = body.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API Key cannot be empty.")
    config.GROQ_API_KEY = key
    os.environ["GROQ_API_KEY"] = key
    
    # Save to .env file as well
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "w") as f:
        f.write(f"GROQ_API_KEY={key}\nGROQ_TEXT_MODEL={config.GROQ_TEXT_MODEL}\nGROQ_VISION_MODEL={config.GROQ_VISION_MODEL}\n")

    return {"status": "success", "message": "Groq API key updated successfully!", "llm": llm_client.check_llm_status()}

@app.get("/api/products")
def list_products():
    """Lists all products from the catalog."""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM products 
    ORDER BY 
        CASE category 
            WHEN 'Laptops' THEN 1 
            WHEN 'Phones' THEN 2 
            WHEN 'Headphones' THEN 3 
            WHEN 'Tablets' THEN 4 
            WHEN 'Cameras' THEN 5 
            WHEN 'Accessories' THEN 6 
            ELSE 7 
        END, 
        id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    products = []
    for r in rows:
        d = dict(r)
        d["specs"] = json.loads(d["specs"]) if d.get("specs") else {}
        products.append(d)
    return {"products": products}

@app.get("/api/orders")
def list_orders(email: Optional[str] = None, role: Optional[str] = "customer"):
    """
    Role-Based Order Manager:
    - If role == 'admin', returns ALL company orders.
    - If role == 'customer' and email provided, strictly returns ONLY that customer's orders.
    """
    conn = database.get_db()
    cursor = conn.cursor()
    
    if role == "admin":
        cursor.execute("SELECT * FROM orders ORDER BY order_date DESC")
    elif email:
        cursor.execute("SELECT * FROM orders WHERE LOWER(customer_email) = ? ORDER BY order_date DESC", (email.strip().lower(),))
    else:
        cursor.execute("SELECT * FROM orders ORDER BY order_date DESC")

    rows = cursor.fetchall()
    conn.close()
    
    orders = []
    for r in rows:
        d = dict(r)
        d["items"] = json.loads(d["items"]) if d.get("items") else []
        orders.append(d)
    return {"orders": orders}

@app.get("/api/cart/{session_id}")
def get_cart(session_id: str):
    """Fetches customer's active cart items with product details."""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.id, c.product_id, c.quantity, p.name, p.price, p.image_url, p.category
    FROM cart_items c
    JOIN products p ON c.product_id = p.id
    WHERE c.session_id = ?
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    items = [dict(r) for r in rows]
    total = sum(item["price"] * item["quantity"] for item in items)
    return {"items": items, "total": round(total, 2)}

@app.post("/api/cart")
def add_to_cart(item: CartItemRequest):
    """Adds a product to the session cart."""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO cart_items (session_id, product_id, quantity, added_at)
    VALUES (?, ?, ?, datetime('now'))
    """, (item.session_id, item.product_id, item.quantity))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Item added to cart"}

@app.delete("/api/cart/{item_id}")
def remove_from_cart(item_id: int):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cart_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

class CartUpdateQuantity(BaseModel):
    quantity: int

@app.put("/api/cart/{item_id}")
def update_cart_quantity(item_id: int, body: CartUpdateQuantity):
    conn = database.get_db()
    cursor = conn.cursor()
    if body.quantity <= 0:
        cursor.execute("DELETE FROM cart_items WHERE id = ?", (item_id,))
    else:
        cursor.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (body.quantity, item_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

class CheckoutRequest(BaseModel):
    session_id: str
    customer_name: Optional[str] = "Customer"
    customer_email: Optional[str] = "customer@example.com"

@app.post("/api/checkout")
def checkout_cart(body: CheckoutRequest):
    """Converts items in customer cart into a real new Order in SQLite database."""
    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT c.product_id, c.quantity, p.name, p.price
    FROM cart_items c
    JOIN products p ON c.product_id = p.id
    WHERE c.session_id = ?
    """, (body.session_id,))
    rows = cursor.fetchall()

    if not rows:
        conn.close()
        raise HTTPException(status_code=400, detail="Cart is empty. Add products before checking out.")

    items = []
    total = 0.0
    for r in rows:
        items.append({
            "product_id": r["product_id"],
            "name": r["name"],
            "qty": r["quantity"],
            "price": r["price"]
        })
        total += r["price"] * r["quantity"]

    # Calculate next order ID
    cursor.execute("SELECT id FROM orders")
    all_orders = cursor.fetchall()
    next_num = 1005
    for o in all_orders:
        match = re.search(r'ORD-(\d+)', o["id"])
        if match:
            num = int(match.group(1))
            if num >= next_num:
                next_num = num + 1
    new_order_id = f"ORD-{next_num}"

    import random
    from datetime import datetime, timedelta
    tracking_no = f"BLUEDART-{random.randint(1000000, 9999999)}"
    today_dt = datetime.now()
    today_str = today_dt.strftime("%Y-%m-%d")
    delivery_str = (today_dt + timedelta(days=3)).strftime("%Y-%m-%d")

    cursor.execute("""
    INSERT INTO orders (id, customer_name, customer_email, order_date, delivery_date, status, tracking_number, carrier, items, total_amount, currency, return_status)
    VALUES (?, ?, ?, ?, ?, 'Placed', ?, 'BlueDart Express', ?, ?, '₹', 'None')
    """, (new_order_id, body.customer_name, body.customer_email, today_str, delivery_str, tracking_no, json.dumps(items), total))

    # Clear user's cart
    cursor.execute("DELETE FROM cart_items WHERE session_id = ?", (body.session_id,))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "order_id": new_order_id,
        "total": total,
        "tracking_number": tracking_no,
        "delivery_date": delivery_str,
        "order_status": "Placed",
        "message": f"Order {new_order_id} placed successfully! Tracking Number: {tracking_no}. Estimated delivery by {delivery_str}."
    }

class UpdateOrderStatusRequest(BaseModel):
    status: str

@app.post("/api/orders/{order_id}/status")
def update_order_status(order_id: str, body: UpdateOrderStatusRequest):
    """Updates order status to Placed, Shipped, In Transit, or Delivered."""
    valid_statuses = ["Placed", "Shipped", "In Transit", "Delivered"]
    new_status = body.status.strip()
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE UPPER(id) = ?", (new_status, order_id.strip().upper()))
    conn.commit()
    cursor.execute("SELECT * FROM orders WHERE UPPER(id) = ?", (order_id.strip().upper(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    
    d = dict(row)
    d["items"] = json.loads(d["items"]) if d.get("items") else []
    return {"status": "success", "order": d}

@app.post("/api/orders/{order_id}/advance_status")
def advance_order_status(order_id: str):
    """Cycles through the 4 Meesho/Myntra tracking stages: Placed -> Shipped -> In Transit -> Delivered."""
    stages = ["Placed", "Shipped", "In Transit", "Delivered"]
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM orders WHERE UPPER(id) = ?", (order_id.strip().upper(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")
    
    current = row["status"]
    try:
        idx = stages.index(current)
        next_status = stages[(idx + 1) % len(stages)]
    except ValueError:
        next_status = "Placed"
    
    cursor.execute("UPDATE orders SET status = ? WHERE UPPER(id) = ?", (next_status, order_id.strip().upper()))
    conn.commit()
    cursor.execute("SELECT * FROM orders WHERE UPPER(id) = ?", (order_id.strip().upper(),))
    updated_row = cursor.fetchone()
    conn.close()
    
    d = dict(updated_row)
    d["items"] = json.loads(d["items"]) if d.get("items") else []
    return {"status": "success", "new_status": next_status, "order": d}

@app.post("/api/session/unfreeze/{session_id}")
def unfreeze_session_api(session_id: str):
    """Unfreezes session and restores AI agents from human handoff state."""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET is_human_handoff = 0 WHERE session_id = ?", (session_id,))
    cursor.execute("UPDATE handoff_tickets SET status = 'RESOLVED' WHERE session_id = ? AND status = 'PENDING'", (session_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Session unfreezed successfully!"}

@app.get("/api/messages/{session_id}")
def get_chat_history(session_id: str):
    """Retrieves full conversation history for persistent past chat view."""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, session_id, sender, content, metadata, created_at
    FROM messages
    WHERE session_id = ?
    ORDER BY id ASC
    """, (session_id,))
    rows = cursor.fetchall()
    
    # Also check if session is currently handed off to a human
    cursor.execute("SELECT is_human_handoff, handoff_reason FROM sessions WHERE session_id = ?", (session_id,))
    sess = cursor.fetchone()
    conn.close()

    history = []
    for r in rows:
        d = dict(r)
        if d.get("metadata"):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except Exception:
                pass
        history.append(d)

    return {
        "messages": history,
        "is_human_handoff": bool(sess["is_human_handoff"]) if sess else False,
        "handoff_reason": sess["handoff_reason"] if sess else None
    }

@app.get("/api/handoff/tickets")
def get_handoff_tickets():
    """Returns all escalated tickets for the Human Agent Live Queue."""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM handoff_tickets ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return {"tickets": [dict(r) for r in rows]}

@app.post("/api/handoff/respond")
def human_takeover_respond(body: HumanResponseRequest):
    """Enables a human customer service agent to reply directly or resolve a ticket."""
    conn = database.get_db()
    cursor = conn.cursor()

    # Save the human agent's message into the conversation
    cursor.execute("""
    INSERT INTO messages (session_id, sender, content, metadata, created_at)
    VALUES (?, 'human_agent', ?, ?, datetime('now'))
    """, (body.session_id, body.response_message, json.dumps({"source": "human_operator"})))

    # If action is RESOLVE, unfreeze the bot
    if body.action == "RESOLVE":
        cursor.execute("UPDATE sessions SET is_human_handoff = 0 WHERE session_id = ?", (body.session_id,))
        cursor.execute("UPDATE handoff_tickets SET status = 'RESOLVED' WHERE ticket_id = ?", (body.ticket_id,))
    else:
        cursor.execute("UPDATE handoff_tickets SET status = 'ACCEPTED' WHERE ticket_id = ?", (body.ticket_id,))

    conn.commit()
    conn.close()
    return {"status": "success", "message": "Human response dispatched"}

# --- Multi-Agent Orchestrator (TriageBot, ShopperBot & SupportBot) ---
from .agents import triage

@app.post("/api/chat")
@app.post("/api/chat/test")
@app.post("/api/chat/shopper")
def chat_dispatch(req: ChatMessageRequest):
    """
    CommerceOS Autonomous Multi-Agent Orchestrator:
    1. TriageBot (Supervisor): Analyzes intent, calculates sentiment score (1-5), and checks for human escalation triggers.
    2. ShopperBot: Handles product discovery, specs comparison, budget matching, and cart actions.
    3. SupportBot: Enforces deterministic 30-day return policy and ₹4,000 threshold auto-refunds.
    4. Human-in-the-Loop (HITL): Freezes AI and transfers ticket to Human Handoff Queue on frustration or high-value claims.
    """
    conn = database.get_db()
    cursor = conn.cursor()

    # Ensure session exists with user_email and order_id
    cursor.execute("""
    INSERT INTO sessions (session_id, user_name, user_email, order_id, created_at, last_active)
    VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
    ON CONFLICT(session_id) DO UPDATE SET
        user_name = excluded.user_name,
        user_email = COALESCE(excluded.user_email, sessions.user_email),
        order_id = COALESCE(excluded.order_id, sessions.order_id),
        last_active = datetime('now')
    """, (req.session_id, req.user_name, req.user_email, req.order_id))

    # Fetch sliding context memory (last 8 messages)
    cursor.execute("""
    SELECT sender, content FROM messages
    WHERE session_id = ? AND content NOT LIKE '%Error%'
    ORDER BY id DESC LIMIT 8
    """, (req.session_id,))
    raw_history = list(cursor.fetchall())
    raw_history.reverse()
    chat_history = []
    for h in raw_history:
        role = "assistant" if h["sender"] in ["ShopperBot", "SupportBot", "TriageBot", "CommerceOS", "human_agent"] else "user"
        chat_history.append({"role": role, "content": h["content"]})

    # Save user message
    cursor.execute("""
    INSERT INTO messages (session_id, sender, content, metadata, created_at)
    VALUES (?, 'user', ?, NULL, datetime('now'))
    """, (req.session_id, req.message))
    conn.commit()
    conn.close()

    # Run Triage Supervisor Orchestration with user identity and order context
    agent_res = triage.run_triage_orchestrator(
        session_id=req.session_id,
        user_query=req.message,
        user_name=req.user_name or "Customer",
        chat_history=chat_history,
        image_base64=req.image_base64,
        user_email=req.user_email,
        user_role=req.user_role or "customer",
        order_id=req.order_id
    )

    from .text_cleaner import strip_all_markdown
    agent_name = agent_res.get("agent", "CommerceOS")
    cleaned_content = strip_all_markdown(agent_res.get("content", ""))

    # Save Agent response with rich metadata
    conn = database.get_db()
    cursor = conn.cursor()
    meta = {
        "products": agent_res.get("products", []),
        "cart_added": agent_res.get("cart_added"),
        "order": agent_res.get("order"),
        "eligibility": agent_res.get("eligibility"),
        "return_result": agent_res.get("return_result"),
        "sentiment_score": agent_res.get("sentiment_score", 3),
        "sentiment_label": agent_res.get("sentiment_label", "Neutral"),
        "triage_route": agent_res.get("triage_route"),
        "is_human_handoff": agent_res.get("is_human_handoff", False),
        "ticket_id": agent_res.get("ticket_id"),
        "latency_ms": agent_res.get("latency_ms", 0),
        "tokens": agent_res.get("tokens", {}),
        "agent": agent_name
    }
    cursor.execute("""
    INSERT INTO messages (session_id, sender, content, metadata, created_at)
    VALUES (?, ?, ?, ?, datetime('now'))
    """, (req.session_id, agent_name, cleaned_content, json.dumps(meta)))

    conn.commit()
    conn.close()

    return {
        "content": cleaned_content,
        "products": agent_res.get("products", []),
        "cart_added": agent_res.get("cart_added"),
        "order": agent_res.get("order"),
        "eligibility": agent_res.get("eligibility"),
        "return_result": agent_res.get("return_result"),
        "sentiment_score": agent_res.get("sentiment_score", 3),
        "sentiment_label": agent_res.get("sentiment_label", "Neutral"),
        "triage_route": agent_res.get("triage_route"),
        "is_human_handoff": agent_res.get("is_human_handoff", False),
        "ticket_id": agent_res.get("ticket_id"),
        "latency_ms": agent_res.get("latency_ms", 0),
        "tokens": agent_res.get("tokens", {}),
        "agent": agent_name,
        "provider": "Groq"
    }
