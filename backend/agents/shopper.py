import json
import sqlite3
from typing import List, Dict, Any, Optional
from .. import database, llm_client, config

# --- 1. TOOL DEFINITIONS (Function Calling Schemas) ---
SHOPPER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Searches the 50 store products by keyword, category, and budget in Indian Rupees (₹). Call this whenever a customer asks for recommendations, products, or mentions specs/budget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Product search keywords (e.g., 'macbook', 'iphone', 'airpods', 'charger', 'mouse', 'headphones', 'laptop')."
                    },
                    "category": {
                        "type": "string",
                        "enum": ["Laptops", "Phones", "Headphones", "Electronics"],
                        "description": "Specific store category to narrow search (Laptops, Phones, Headphones, Electronics)."
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum budget in Indian Rupees (₹) (e.g. 500, 3000, 40000)."
                    },
                    "min_price": {
                        "type": "number",
                        "description": "Minimum budget in Indian Rupees (₹)."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": "Retrieves comprehensive specifications, stock availability, and specs for a specific product ID (e.g., 'LAP-001', 'SHOE-010').",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The exact product ID to look up."
                    }
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": "Adds a specific product to the customer's active shopping cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The product ID to add to cart."
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Quantity to add (default 1)."
                    }
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "Places an order and checks out items from the customer's cart, or directly buys a specified product. Call this when customer says 'place order', 'order this', 'checkout', 'buy now', or 'confirm order'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "Optional product ID to purchase directly if cart is empty."
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Quantity to order (default 1)."
                    }
                },
                "required": []
            }
        }
    }
]

# --- 2. DETERMINISTIC TOOL IMPLEMENTATIONS (Python + SQLite) ---

def tool_search_catalog(query: str = "", category: Optional[str] = None, max_price: Optional[float] = None, min_price: Optional[float] = None) -> List[Dict[str, Any]]:
    """Executes deterministic SQL query against the real 50-product database."""
    conn = database.get_db()
    cursor = conn.cursor()

    # Intelligent Category Auto-Detection from query
    q_lower = (query or "").lower()
    if not category:
        if any(w in q_lower for w in ["laptop", "macbook", "notebook", "computer", "pc"]):
            category = "Laptops"
        elif any(w in q_lower for w in ["shoe", "shoes", "sneaker", "sneakers", "boot", "boots", "footwear", "loafer", "runner"]):
            category = "Footwear"
        elif any(w in q_lower for w in ["headphone", "headphones", "earbud", "earbuds", "watch", "speaker", "soundbar", "monitor", "webcam"]):
            category = "Electronics"
        elif any(w in q_lower for w in ["hoodie", "jacket", "shirt", "pants", "cargo", "leggings", "tee", "apparel"]):
            category = "Apparel"
        elif any(w in q_lower for w in ["bag", "backpack", "wallet", "bottle", "case", "duffel"]):
            category = "Accessories"

    conditions = []
    params = []

    if category:
        conditions.append("LOWER(category) = LOWER(?)")
        params.append(category)

    if max_price is not None:
        conditions.append("price <= ?")
        params.append(max_price)

    if min_price is not None:
        conditions.append("price >= ?")
        params.append(min_price)

    # Keywords filtering
    sql = "SELECT id, name, category, price, currency, stock, description, specs, image_url FROM products"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    # If query has specific words (like 8GB or student)
    key_words = [w for w in q_lower.split() if w not in ["a", "an", "the", "for", "with", "in", "me", "show", "find", "i", "need", "want", "under", "rs", "rupees", "inr", "laptop", "laptops", "shoe", "shoes"]]
    
    cursor.execute(sql + " ORDER BY price ASC", params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        try:
            d["specs"] = json.loads(d["specs"]) if isinstance(d["specs"], str) else d["specs"]
        except Exception:
            pass
        results.append(d)

    # If key_words present, score products that match the keywords first (e.g. "8GB" or "RAM")
    if key_words and results:
        scored = []
        for prod in results:
            text_haystack = f"{prod['name']} {prod['description']} {json.dumps(prod['specs'])}".lower()
            score = sum(1 for kw in key_words if kw in text_haystack)
            scored.append((score, prod))
        # Sort by score descending, then price ascending
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [x[1] for x in scored]

    return results[:5]

def tool_get_product_details(product_id: str) -> Optional[Dict[str, Any]]:
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        try:
            d["specs"] = json.loads(d["specs"])
        except Exception:
            pass
        return d
    return None

def tool_add_to_cart(session_id: str, product_id: str, quantity: int = 1) -> Dict[str, Any]:
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        conn.close()
        return {"success": False, "error": f"Product {product_id} not found."}

    cursor.execute("""
    INSERT INTO cart_items (session_id, product_id, quantity, added_at)
    VALUES (?, ?, ?, datetime('now'))
    """, (session_id, product_id, quantity))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "product_id": product_id,
        "name": product["name"],
        "price": product["price"],
        "quantity": quantity,
        "message": f"Added {quantity}x {product['name']} to cart."
    }

def tool_place_order(
    session_id: str,
    user_name: str = "Customer",
    user_email: str = "customer@gmail.com",
    product_id: Optional[str] = None,
    quantity: int = 1
) -> Dict[str, Any]:
    """Places an order from the user's cart or directly for a product."""
    import random
    import re
    from datetime import datetime, timedelta

    conn = database.get_db()
    cursor = conn.cursor()

    # 1. Fetch cart items for this session
    cursor.execute("""
    SELECT c.product_id, c.quantity, p.name, p.price, p.image_url
    FROM cart_items c
    JOIN products p ON c.product_id = p.id
    WHERE c.session_id = ?
    """, (session_id,))
    rows = cursor.fetchall()

    items = []
    total = 0.0

    if rows:
        for r in rows:
            items.append({
                "product_id": r["product_id"],
                "name": r["name"],
                "qty": r["quantity"],
                "price": r["price"],
                "image_url": r["image_url"]
            })
            total += r["price"] * r["quantity"]
    elif product_id:
        cursor.execute("SELECT id, name, price, image_url FROM products WHERE UPPER(id) = ?", (product_id.strip().upper(),))
        prod = cursor.fetchone()
        if prod:
            qty = max(1, quantity)
            items.append({
                "product_id": prod["id"],
                "name": prod["name"],
                "qty": qty,
                "price": prod["price"],
                "image_url": prod["image_url"]
            })
            total = prod["price"] * qty
        else:
            conn.close()
            return {"success": False, "error": f"Product '{product_id}' not found in catalog."}
    else:
        conn.close()
        return {"success": False, "error": "Your shopping cart is currently empty. Please add an item first or tell me which product you'd like to order."}

    # 2. Determine next order ID
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

    # 3. Create tracking and timeline (Initial state: 'Placed')
    tracking_no = f"BLUEDART-{random.randint(1000000, 9999999)}"
    today_dt = datetime.now()
    today_str = today_dt.strftime("%Y-%m-%d")
    delivery_str = (today_dt + timedelta(days=3)).strftime("%Y-%m-%d")

    cursor.execute("""
    INSERT INTO orders (id, customer_name, customer_email, order_date, delivery_date, status, tracking_number, carrier, items, total_amount, currency, return_status)
    VALUES (?, ?, ?, ?, ?, 'Placed', ?, 'BlueDart Express', ?, ?, '₹', 'None')
    """, (new_order_id, user_name or "Customer", user_email or "customer@gmail.com", today_str, delivery_str, tracking_no, json.dumps(items), total))

    # Clear user's session cart
    cursor.execute("DELETE FROM cart_items WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

    order_obj = {
        "id": new_order_id,
        "customer_name": user_name,
        "customer_email": user_email,
        "order_date": today_str,
        "delivery_date": delivery_str,
        "status": "Placed",
        "tracking_number": tracking_no,
        "carrier": "BlueDart Express",
        "items": items,
        "total_amount": total,
        "currency": "₹",
        "return_status": "None",
        "found": True
    }

    return {
        "success": True,
        "order_id": new_order_id,
        "total": total,
        "tracking_number": tracking_no,
        "order": order_obj,
        "message": f"Order #{new_order_id} placed successfully! Tracking Number: {tracking_no}. Estimated delivery by {delivery_str}."
    }

# --- 3. SHOPPERBOT SYSTEM PROMPT (Engineered Grounding & ReAct) ---
SHOPPER_SYSTEM_PROMPT = """You are ShopperBot, an expert personal shopping assistant for CommerceOS.

YOUR RESPONSIBILITIES:
1. Help customers discover, compare, and purchase products from our electronic devices store catalog across 4 categories: Laptops, Phones, Headphones, and Electronics (like mouse, airpods, charger, adapter).
2. Prices are strictly in Indian Rupees (₹).
3. Whenever a customer asks for a product, recommendation, or budget search, YOU MUST CALL the `search_catalog` tool.
4. When a user asks to add an item to their cart, call the `add_to_cart` tool.
5. When a user says 'place order', 'buy now', 'order this', 'checkout', or 'confirm order', YOU MUST CALL the `place_order` tool to immediately create the order under their account and return their tracking details!

CRITICAL PLAIN TEXT RULE:
- NEVER use markdown formatting under any circumstances!
- DO NOT use bolding or asterisks (NO **word** or *word*).
- DO NOT use markdown tables or pipe symbols (|).
- DO NOT use markdown hashtags (# or ##).
- Write in 100% natural, clean, conversational human sentences only.

STRICT ZERO-HALLUCINATION GUARDRAILS:
- You are STRICTLY FORBIDDEN from inventing products or fabricating prices that do not exist in the database.
- You can ONLY recommend products that were returned directly by the `search_catalog` tool in this turn.
- If a customer asks for an item outside our catalog, truthfully inform them what is available and offer the closest electronic alternative.
- Mention product names and exact prices (₹) naturally in sentences without markdown asterisks.

TONE & STYLE:
- Enthusiastic, knowledgeable, clear, and concise (2-4 sentences max per response).
- Highlight key features (RAM, processor, battery, ANC, camera) that match the customer's specific needs.
"""

# --- 4. RUN SHOPPERBOT (Autonomous Robust ReAct Loop) ---
def run_shopper_agent(
    session_id: str,
    user_query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    image_base64: Optional[str] = None,
    user_name: Optional[str] = "Customer",
    user_email: Optional[str] = "customer@gmail.com"
) -> Dict[str, Any]:
    """
    Executes the autonomous ReAct cycle with robust multi-turn tool handling:
    1. Reason on user intent & call tools
    2. Execute Python SQLite tools
    3. Pass tools schema to second turn to prevent 'tool choice is none' errors
    4. Synthesize final grounded answer and return structured product cards
    """
    messages = [{"role": "system", "content": SHOPPER_SYSTEM_PROMPT}]

    # Include recent chat history (sliding memory buffer)
    if chat_history:
        for m in chat_history[-6:]:
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

    # Multimodal Vision: If image provided, analyze visual features first
    image_attributes = ""
    if image_base64:
        vision_res = llm_client.analyze_image_with_vision(
            image_base64,
            prompt="Identify this product. State its category (Laptops, Footwear, Electronics, Apparel, or Accessories), color, style, and key visual attributes in 1 concise sentence."
        )
        image_attributes = vision_res.get("description", "")
        augmented_query = f"{user_query}\n[Customer attached image. Visual Analysis: {image_attributes}]"
        messages.append({"role": "user", "content": augmented_query})
    else:
        messages.append({"role": "user", "content": user_query})

    # Step 1: Initial LLM call with Tools
    llm_resp = llm_client.call_llm(
        messages=messages,
        temperature=config.TEMPERATURE_SHOPPER,
        tools=SHOPPER_TOOLS,
        tool_choice="auto"
    )

    matched_products = []
    cart_added_info = None
    placed_order_info = None
    tool_calls = llm_resp.get("tool_calls", [])

    if tool_calls:
        # Append assistant's tool call message
        messages.append({
            "role": "assistant",
            "content": llm_resp.get("content", "") or "",
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])}
                } for tc in tool_calls
            ]
        })

        for tc in tool_calls:
            tool_name = tc["name"]
            args = tc["arguments"]
            tool_result = None

            if tool_name == "search_catalog":
                tool_result = tool_search_catalog(
                    query=args.get("query", ""),
                    category=args.get("category"),
                    max_price=args.get("max_price"),
                    min_price=args.get("min_price")
                )
                matched_products.extend(tool_result)

            elif tool_name == "get_product_details":
                tool_result = tool_get_product_details(args.get("product_id", ""))
                if tool_result:
                    matched_products.append(tool_result)

            elif tool_name == "add_to_cart":
                tool_result = tool_add_to_cart(
                    session_id=session_id,
                    product_id=args.get("product_id", ""),
                    quantity=args.get("quantity", 1)
                )
                cart_added_info = tool_result

            elif tool_name == "place_order":
                tool_result = tool_place_order(
                    session_id=session_id,
                    user_name=user_name,
                    user_email=user_email,
                    product_id=args.get("product_id"),
                    quantity=args.get("quantity", 1)
                )
                if tool_result.get("order"):
                    placed_order_info = tool_result.get("order")

            # Append Tool Observation back to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(tool_result or {})
            })

        # Deduplicate matched products by ID
        seen = set()
        unique_products = []
        for p in matched_products:
            if p["id"] not in seen:
                seen.add(p["id"])
                unique_products.append(p)
        matched_products = unique_products

        # Step 3: Synthesis turn - Always pass tools so Groq never throws "Tool choice is none"
        synth_prompt = "Synthesize an enthusiastic confirmation for the order with order ID, carrier, tracking number, and delivery date." if placed_order_info else "Synthesize a friendly recommendation for the user highlighting the product names, specs, and prices in ₹. Do not call further tools."
        messages.append({
            "role": "user",
            "content": synth_prompt
        })
        final_resp = llm_client.call_llm(
            messages=messages,
            temperature=config.TEMPERATURE_SHOPPER,
            tools=SHOPPER_TOOLS
        )
        content = final_resp.get("content", "")
        latency = llm_resp.get("latency_ms", 0) + final_resp.get("latency_ms", 0)
        tokens = final_resp.get("tokens", {})

        # Fail-safe guardrail
        if placed_order_info and ("LLM Inference Error" in content or not content.strip()):
            content = f"Congratulations {user_name}! Your order #{placed_order_info['id']} has been placed successfully! Total: ₹{placed_order_info['total_amount']:,.2f}. Carrier: {placed_order_info['carrier']} (Tracking: {placed_order_info['tracking_number']}). Estimated delivery by {placed_order_info['delivery_date']}."
        elif ("LLM Inference Error" in content or not content.strip()) and matched_products:
            items_desc = ", ".join([f"{p['name']} (₹{p['price']:,.2f})" for p in matched_products[:3]])
            content = f"Here are the top options matching your request from our catalog: {items_desc}. You can click Add to Cart on any product card below."

    else:
        # No tool called (e.g. greeting or general query)
        content = llm_resp.get("content", "")
        latency = llm_resp.get("latency_ms", 0)
        tokens = llm_resp.get("tokens", {})

    from ..text_cleaner import strip_all_markdown
    clean_content = strip_all_markdown(content)

    return {
        "content": clean_content,
        "products": matched_products,
        "cart_added": cart_added_info,
        "order": placed_order_info,
        "latency_ms": latency,
        "tokens": tokens,
        "agent": "ShopperBot"
    }
