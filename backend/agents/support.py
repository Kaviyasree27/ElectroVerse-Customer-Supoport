import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from .. import database, llm_client, config

# --- 1. TOOL DEFINITIONS (Function Calling Schemas for SupportBot) ---
SUPPORT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Looks up order details, shipping status, carrier tracking, and purchased items for an order ID (e.g. 'ORD-1001', 'ORD-1002', 'ORD-1004').",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The exact order ID, formatted like ORD-XXXX."
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_orders",
            "description": "Retrieves all orders placed by the currently logged-in customer. Call this whenever the customer asks 'where is my order?', 'when will it arrive?', 'what did I order?', 'track my order', or does not specify an order ID.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_return_eligibility",
            "description": "Checks whether an order qualifies for a return based on the 30-day delivery window and the ₹4,000 refund threshold.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to evaluate for return."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Customer's stated reason for return (e.g., 'wrong size', 'damaged', 'changed mind')."
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_return",
            "description": "Processes an authorized return for an eligible order under ₹4,000, issuing an automated return shipping label and refund.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to process the return for."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Customer's verified reason for return."
                    }
                },
                "required": ["order_id", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_order",
            "description": "Cancels an order if it is in 'Placed' status. If the order is already 'Shipped' or 'In Transit', it cannot be cancelled directly and must be returned after delivery.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to cancel (e.g. 'ORD-1010'). If omitted, will check the customer's latest order."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for cancellation."
                    }
                },
                "required": []
            }
        }
    }
]

# --- 2. DETERMINISTIC POLICY-AS-CODE TOOLS (Python + SQLite) ---

def tool_get_customer_orders(user_email: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all orders placed by the given customer email."""
    if not user_email:
        return []
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE LOWER(customer_email) = ? ORDER BY order_date DESC", (user_email.strip().lower(),))
    rows = cursor.fetchall()
    conn.close()

    orders = []
    for r in rows:
        d = dict(r)
        try:
            d["items"] = json.loads(d["items"]) if isinstance(d["items"], str) else d["items"]
        except Exception:
            pass
        d["found"] = True
        orders.append(d)
    return orders

def tool_lookup_order(order_id: str, user_email: Optional[str] = None, user_role: Optional[str] = "customer") -> Dict[str, Any]:
    """Retrieves order record directly from the database and enforces user isolation guardrail."""
    clean_id = (order_id or "").strip().upper()
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE UPPER(id) = ?", (clean_id,))
    row = cursor.fetchone()
    conn.close()

    user_orders = tool_get_customer_orders(user_email) if user_email else []

    if not row:
        return {
            "found": False,
            "error": f"No order found with ID '{order_id}'.",
            "user_orders": user_orders,
            "my_latest_order": user_orders[0] if user_orders else None
        }

    d = dict(row)
    order_email = (d.get("customer_email") or "").strip().lower()

    # CUSTOMER PRIVACY GUARDRAIL: Customers can ONLY see their own orders!
    if user_role != "admin" and user_email:
        req_email = user_email.strip().lower()
        if order_email != req_email:
            return {
                "found": False,
                "access_denied": True,
                "error": f"🔒 Privacy Guardrail: Order '{order_id}' belongs to another customer's account ({d.get('customer_email')}). For privacy and security, you can only track orders placed with your signed-in account ({user_email}).",
                "user_orders": user_orders,
                "has_user_orders": len(user_orders) > 0,
                "my_latest_order": user_orders[0] if user_orders else None
            }

    try:
        d["items"] = json.loads(d["items"]) if isinstance(d["items"], str) else d["items"]
    except Exception:
        pass
    d["found"] = True
    return d

def tool_check_return_eligibility(order_id: str, reason: str = "Return requested", user_email: Optional[str] = None, user_role: Optional[str] = "customer") -> Dict[str, Any]:
    """
    DETERMINISTIC BUSINESS POLICY GUARDRAIL:
    1. Status must be 'Delivered'.
    2. Must be within 30 days of delivery.
    3. Refund amount cap: If total > ₹4,000 ($50 threshold), requires human authorization.
    """
    order = tool_lookup_order(order_id, user_email=user_email, user_role=user_role)
    if not order.get("found"):
        return {"eligible": False, "reason": order.get("error")}

    status = order.get("status")
    if status != "Delivered":
        return {
            "eligible": False,
            "order_id": order_id,
            "status": status,
            "policy_rule": "Items must be delivered before initiating a return.",
            "tracking_number": order.get("tracking_number"),
            "carrier": order.get("carrier")
        }

    delivery_date_str = order.get("delivery_date")
    if not delivery_date_str:
        return {"eligible": False, "reason": "Delivery date not recorded for this order."}

    try:
        delivery_date = datetime.strptime(delivery_date_str, "%Y-%m-%d")
        days_since = (datetime.now() - delivery_date).days
    except Exception:
        days_since = 0

    total_amount = order.get("total_amount", 0.0)

    # Policy Check 1: 30-Day Window Cutoff
    if days_since > config.RETURN_POLICY_DAYS:
        return {
            "eligible": False,
            "order_id": order_id,
            "days_since_delivery": days_since,
            "policy_rule": f"Order was delivered {days_since} days ago, which exceeds our strict {config.RETURN_POLICY_DAYS}-day return policy cutoff.",
            "total_amount": total_amount,
            "decision": "BLOCKED_BY_POLICY"
        }

    # Policy Check 2: Financial Threshold Cap (₹4,000 / $50)
    MAX_AUTO_INR = 4000.00
    if total_amount > MAX_AUTO_INR:
        return {
            "eligible": True,
            "requires_human_approval": True,
            "order_id": order_id,
            "total_amount": total_amount,
            "days_since_delivery": days_since,
            "decision": "REQUIRES_HUMAN_APPROVAL",
            "policy_rule": f"Return is within the 30-day window, but total amount (₹{total_amount:,.2f}) exceeds our automated threshold of ₹{MAX_AUTO_INR:,.2f}. Must be escalated to a human supervisor."
        }

    # Low-Risk: Auto-Eligible
    return {
        "eligible": True,
        "requires_human_approval": False,
        "order_id": order_id,
        "days_since_delivery": days_since,
        "total_amount": total_amount,
        "decision": "AUTO_ELIGIBLE",
        "policy_rule": f"Order is within {days_since} days of delivery and within automated refund limit."
    }

def tool_process_return(order_id: str, reason: str, user_email: Optional[str] = None, user_role: Optional[str] = "customer") -> Dict[str, Any]:
    """Processes return and creates instant return shipping label if eligible."""
    eligibility = tool_check_return_eligibility(order_id, reason, user_email=user_email, user_role=user_role)
    if not eligibility.get("eligible"):
        return {"success": False, "message": eligibility.get("policy_rule") or eligibility.get("reason")}

    if eligibility.get("requires_human_approval"):
        return {
            "success": False,
            "requires_human_approval": True,
            "message": eligibility.get("policy_rule")
        }

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET return_status = 'Approved' WHERE UPPER(id) = ?", (order_id.upper(),))
    conn.commit()
    conn.close()

    label_code = f"RET-LABEL-{order_id[-4:]}-EXPRESS"
    return {
        "success": True,
        "order_id": order_id,
        "return_label_code": label_code,
        "refund_amount": eligibility.get("total_amount"),
        "carrier": "BlueDart Return Pickup",
        "pickup_window": "Next Business Day (10:00 AM - 2:00 PM)",
        "message": f"Return authorized. Instant return label {label_code} generated. A full refund of ₹{eligibility.get('total_amount'):,.2f} will be released once handed over to the courier."
    }

def tool_cancel_order(order_id: Optional[str] = None, reason: str = "Customer requested", user_email: Optional[str] = None, user_role: Optional[str] = "customer") -> Dict[str, Any]:
    """Cancels an order if it is in 'Placed' status and belongs to the customer."""
    conn = database.get_db()
    cursor = conn.cursor()

    target_id = (order_id or "").strip().upper()
    if not target_id and user_email:
        cursor.execute("SELECT id FROM orders WHERE LOWER(customer_email) = ? ORDER BY order_date DESC LIMIT 1", (user_email.strip().lower(),))
        row = cursor.fetchone()
        if row:
            target_id = row["id"]

    if not target_id:
        conn.close()
        return {"success": False, "message": "No order found to cancel."}

    cursor.execute("SELECT * FROM orders WHERE UPPER(id) = ?", (target_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return {"success": False, "message": f"Order {target_id} not found."}

    d = dict(order)
    order_email = (d.get("customer_email") or "").strip().lower()

    if user_role != "admin" and user_email:
        if order_email != user_email.strip().lower():
            conn.close()
            return {"success": False, "access_denied": True, "message": f"Order {target_id} belongs to another account."}

    current_status = d.get("status", "Placed")
    if current_status == "Cancelled":
        conn.close()
        return {"success": False, "order_id": target_id, "status": "Cancelled", "message": f"Order {target_id} is already cancelled."}

    if current_status in ["In Transit", "Shipped"]:
        conn.close()
        return {
            "success": False,
            "order_id": target_id,
            "status": current_status,
            "message": f"Order {target_id} is currently '{current_status}' and already dispatched with BlueDart Express. Orders in transit cannot be cancelled mid-delivery. Once delivered, you can request an instant return and full refund within 30 days."
        }

    if current_status == "Delivered":
        conn.close()
        return {
            "success": False,
            "order_id": target_id,
            "status": "Delivered",
            "message": f"Order {target_id} was already delivered. You can initiate a return and refund instead."
        }

    # Status is Placed -> cancel successfully!
    cursor.execute("UPDATE orders SET status = 'Cancelled' WHERE UPPER(id) = ?", (target_id,))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "order_id": target_id,
        "status": "Cancelled",
        "refund_amount": d.get("total_amount", 0.0),
        "message": f"Order {target_id} has been successfully cancelled! If any payment was deducted, a full refund of ₹{d.get('total_amount', 0.0):,.2f} will be returned to your original payment method within 24 hours."
    }

# --- 3. SUPPORTBOT SYSTEM PROMPT (Strict Guardrails & Determinism) ---
SUPPORT_SYSTEM_PROMPT = """You are SupportBot, a customer care and order resolution specialist for CommerceOS.

YOUR RESPONSIBILITIES:
1. Provide accurate delivery updates and carrier tracking for customer orders.
2. When a customer asks "where is my order?", "when will it arrive?", "when will it come?", or "track my package":
   - Call `get_my_orders` to retrieve orders placed with their signed-in account.
   - Report their order ID, item name, current status, carrier, tracking number, and delivery date in natural plain text.
3. When a customer asks to CANCEL an order:
   - Call `cancel_order`.
   - If the order was Placed, confirm that it has been cancelled and their refund will be returned.
   - If the order is Shipped or In Transit, explain clearly that it is already with the courier and cannot be cancelled mid-transit, but can be returned after delivery.
4. When a customer asks to RETURN an order:
   - Call `check_return_eligibility` or `process_return`.
5. If a customer inquires about an order ID that belongs to another person:
   - Politely explain that the order belongs to another account, and share their own active order details instead.

STRICT PLAIN TEXT & NO MARKDOWN TABLES RULE:
- NEVER use markdown tables under any circumstances (NEVER output lines with pipes '|' or '|---|' tables).
- NEVER use non-breaking hyphens or unicode dashes (use standard hyphens only).
- Write in clean, friendly, natural plain English sentences. For example:
  "Hi Abhi! Your order ORD-1010 for DailyComfort Casual Slip-on Loafers was placed on October 5, 2026. It is currently Placed and scheduled to arrive on October 8, 2026 via BlueDart Express (Tracking: BLUEDART-6193647)."
- Keep your reply effortless and comfortable to read.

STRICT BUSINESS GUARDRAILS:
- Never guess order statuses, tracking numbers, or dates. Rely solely on tool output.
- Customer Privacy: Customers cannot view orders belonging to other accounts.
- 30-Day Return Limit: If delivered over 30 days ago, inform them the return window has closed.
- High-Value Cap: Any refund request over ₹4,000 ($50) must be escalated to a human manager.
"""

# --- 4. RUN SUPPORTBOT (Deterministic Multi-turn ReAct Loop) ---
def run_support_agent(
    session_id: str,
    user_query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    image_base64: Optional[str] = None,
    user_email: Optional[str] = None,
    user_role: Optional[str] = "customer",
    order_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes SupportBot ReAct loop at temperature = 0.0 for strict determinism.
    Supports multi-step tool calling (e.g., lookup_order -> process_return).
    """
    messages = [{"role": "system", "content": SUPPORT_SYSTEM_PROMPT}]

    if chat_history:
        for m in chat_history[-6:]:
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

    order_ctx = f"[Order Context: Dedicated Thread for {order_id.upper()}]\n" if (order_id and order_id.upper() not in user_query.upper()) else ""
    
    # Ground the agent with user's signed-in identity and existing orders
    user_orders = tool_get_customer_orders(user_email) if user_email else []
    user_info_ctx = f"[User Session: Logged in as '{user_email}']\n" if user_email else ""
    if user_orders:
        orders_summary = ", ".join([f"#{o['id']} ({o['status']}, Carrier: {o.get('carrier')}, Tracking: {o.get('tracking_number')})" for o in user_orders[:3]])
        user_info_ctx += f"[Customer Account Orders: {orders_summary}]\n"

    augmented_query = f"{order_ctx}{user_info_ctx}{user_query}"

    # If user provided image of damage, analyze with vision
    if image_base64:
        vision_res = llm_client.analyze_image_with_vision(
            image_base64,
            prompt="Inspect this item image for physical damage, scratches, cracks, or defects. Summarize findings in 1 concise sentence."
        )
        augmented_query = f"{augmented_query}\n[Damage Inspection Analysis: {vision_res.get('description', '')}]"

    messages.append({"role": "user", "content": augmented_query})

    order_data = None
    eligibility_data = None
    return_result = None
    total_latency = 0
    total_tokens = {"prompt": 0, "completion": 0, "total": 0}
    final_content = ""

    # ReAct Loop: up to 3 turns
    for step in range(3):
        llm_resp = llm_client.call_llm(
            messages=messages,
            temperature=config.TEMPERATURE_SUPPORT,  # 0.0: zero randomness for policy
            tools=SUPPORT_TOOLS,
            tool_choice="auto"
        )
        total_latency += llm_resp.get("latency_ms", 0)
        tok = llm_resp.get("tokens", {})
        total_tokens["total"] += tok.get("total", 0)

        tool_calls = llm_resp.get("tool_calls", [])
        if not tool_calls:
            # Agent decided no further tools needed; synthesized final answer
            final_content = llm_resp.get("content", "")
            break

        # Record assistant tool call turn
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
            result = None

            if tool_name == "get_my_orders":
                orders_list = tool_get_customer_orders(user_email)
                result = {
                    "success": True,
                    "orders": orders_list,
                    "count": len(orders_list),
                    "latest_order": orders_list[0] if orders_list else None
                }
                if orders_list and not order_data:
                    order_data = orders_list[0]

            elif tool_name == "lookup_order":
                result = tool_lookup_order(args.get("order_id", ""), user_email=user_email, user_role=user_role)
                if result.get("found"):
                    order_data = result
                elif result.get("my_latest_order") and not order_data:
                    order_data = result.get("my_latest_order")

            elif tool_name == "check_return_eligibility":
                result = tool_check_return_eligibility(args.get("order_id", ""), args.get("reason", "Customer request"), user_email=user_email, user_role=user_role)
                eligibility_data = result
                if not order_data:
                    order_data = tool_lookup_order(args.get("order_id", ""), user_email=user_email, user_role=user_role)

            elif tool_name == "process_return":
                result = tool_process_return(args.get("order_id", ""), args.get("reason", "Customer request"), user_email=user_email, user_role=user_role)
                return_result = result
                if not order_data:
                    order_data = tool_lookup_order(args.get("order_id", ""), user_email=user_email, user_role=user_role)

            elif tool_name == "cancel_order":
                result = tool_cancel_order(
                    order_id=args.get("order_id"),
                    reason=args.get("reason", "Customer requested cancellation"),
                    user_email=user_email,
                    user_role=user_role
                )

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result or {})
            })

    # If loop ended and final_content is still empty, synthesize
    if not final_content.strip():
        messages.append({
            "role": "user",
            "content": "Synthesize a concise, clear response in plain, natural sentences (do NOT use markdown tables or pipes). If access was denied due to privacy, state that clearly, but provide their own order details if found. Be polite and specific. Do not call further tools."
        })
        final_resp = llm_client.call_llm(
            messages=messages,
            temperature=config.TEMPERATURE_SUPPORT,
            tools=SUPPORT_TOOLS
        )
        final_content = final_resp.get("content", "")
        total_latency += final_resp.get("latency_ms", 0)
        tok = final_resp.get("tokens", {})
        total_tokens["total"] += tok.get("total", 0)

    # Fallback synthesis guardrail if output had an error
    if "LLM Inference Error" in final_content or not final_content.strip():
        if order_data and order_data.get("found"):
            final_content = f"Order {order_data['id']} is currently {order_data['status']}. Carrier: {order_data.get('carrier')}, Tracking: {order_data.get('tracking_number')}, Total: ₹{order_data.get('total_amount'):,.2f}."
        elif user_orders:
            latest = user_orders[0]
            order_data = latest
            final_content = f"I checked your account ({user_email}) and found your order {latest['id']}. It is currently {latest['status']} with {latest.get('carrier', 'BlueDart')} (Tracking: {latest.get('tracking_number')})."
        elif order_data and order_data.get("access_denied"):
            final_content = order_data.get("error", "🔒 Access Denied: You do not have permission to view this order.")
        elif return_result and return_result.get("success"):
            final_content = f"Return approved for {return_result['order_id']}! Return label: {return_result.get('return_label_code')}. Courier pickup scheduled via {return_result.get('carrier')}."
        elif eligibility_data:
            final_content = eligibility_data.get("policy_rule", "Return eligibility verified.")

    # Clean plain text: remove bold, italic, tables, non-breaking hyphens and all markdown
    from ..text_cleaner import strip_all_markdown
    clean_content = strip_all_markdown(final_content)

    # STRICT USER EXPERIENCE GUARDRAIL:
    # Only attach order data for the Meesho/Myntra visual tracking stepper when the customer
    # explicitly asks about order location, arrival date, or tracking (e.g. "where is my order", "when will it arrive/come").
    # DO NOT attach the tracking stepper for cancellation requests, returns, or general questions!
    q_lower = user_query.lower()
    is_cancel_intent = any(w in q_lower for w in ["cancel", "cancellation", "stop order", "don't want", "dont want"])
    is_return_intent = any(w in q_lower for w in ["return", "refund", "exchange", "damaged", "broken", "wrong size"])
    is_tracking_intent = (
        any(w in q_lower for w in [
            "where is", "when will", "arrive", "arrival", "reach", "come", 
            "track", "tracking", "status", "delivery", "shipping status", "where's", "whens"
        ])
        and not is_cancel_intent 
        and not is_return_intent
    )

    final_tracking_order = None
    if is_tracking_intent and (order_data or user_orders):
        final_tracking_order = order_data if (order_data and order_data.get("found")) else (user_orders[0] if user_orders else None)

    return {
        "content": clean_content,
        "order": final_tracking_order,
        "eligibility": eligibility_data,
        "return_result": return_result,
        "latency_ms": total_latency,
        "tokens": total_tokens,
        "agent": "SupportBot"
    }
