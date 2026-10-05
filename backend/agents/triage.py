import json
import re
import time
from typing import Dict, Any, List, Optional
from .. import database, llm_client, config
from . import shopper, support

# --- 1. TRIAGE SUPERVISOR SYSTEM PROMPT ---
TRIAGE_SYSTEM_PROMPT = """You are TriageBot, the AI Supervisor and Sentiment Sentinel for CommerceOS.

YOUR MISSION:
Analyze the customer's message, classify their intent, score their sentiment, and decide the routing path.

ROUTING DESTINATIONS:
1. "SHOPPER" -> When customer asks about products, laptops, shoes, clothes, specs, prices, recommendations, budget, or wants to add items to cart.
2. "SUPPORT" -> When customer asks about existing orders, tracking numbers, shipping status, delivery dates, 30-day return policy, or refund requests.
3. "ESCALATE_HUMAN" -> When customer is angry/furious, expresses strong dissatisfaction, threatens chargeback, or explicitly asks for a human ("agent", "representative", "manager", "real person").
4. "GENERAL" -> General greetings ("hello", "who are you?"), store policies overview, or polite chit-chat.

SENTIMENT SCORING (1 to 5):
- 1: Extremely Frustrated / Angry / Furious / Threatening
- 2: Dissatisfied / Impatient / Annoyed
- 3: Neutral / Informational / Inquiring
- 4: Satisfied / Polite / Interested
- 5: Delighted / Enthusiastic

STRICT OUTPUT FORMAT:
You MUST respond with a valid JSON object only (no markdown fences, no explanatory text outside JSON):
{
  "route": "SHOPPER" | "SUPPORT" | "ESCALATE_HUMAN" | "GENERAL",
  "sentiment_score": <int 1-5>,
  "sentiment_label": "Frustrated" | "Dissatisfied" | "Neutral" | "Satisfied" | "Delighted",
  "escalation_needed": <true/false>,
  "escalation_reason": "<string or null>",
  "executive_summary": "<concise 1-sentence summary of customer status for human agent>",
  "direct_response": "<string response if route is GENERAL or ESCALATE_HUMAN, otherwise null>"
}
"""

def classify_and_triage(
    user_query: str,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Supervisor classifier at temperature 0.0 for deterministic routing and sentiment analysis.
    """
    messages = [{"role": "system", "content": TRIAGE_SYSTEM_PROMPT}]

    if chat_history:
        for m in chat_history[-4:]:
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

    messages.append({"role": "user", "content": f"Customer Message: {user_query}"})

    # Call LLM at temperature 0.0
    start_time = time.time()
    resp = llm_client.call_llm(
        messages=messages,
        temperature=config.TEMPERATURE_TRIAGE,
        max_tokens=400
    )
    raw_content = resp.get("content", "").strip()

    # Clean JSON output if model returned code fences
    cleaned_json = raw_content
    if "```json" in cleaned_json:
        cleaned_json = cleaned_json.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned_json:
        cleaned_json = cleaned_json.split("```")[1].split("```")[0].strip()

    decision = None
    try:
        decision = json.loads(cleaned_json)
    except Exception:
        # Fallback heuristic classifier if JSON parsing failed
        q_lower = user_query.lower()
        if any(w in q_lower for w in ["human", "agent", "manager", "scam", "cheat", "terrible", "worst", "sue", "lawyer"]):
            decision = {
                "route": "ESCALATE_HUMAN",
                "sentiment_score": 1,
                "sentiment_label": "Frustrated",
                "escalation_needed": True,
                "escalation_reason": "Customer expressed strong dissatisfaction or requested human agent.",
                "executive_summary": "Customer demands human escalation.",
                "direct_response": "I understand your frustration. I am escalating your request directly to a senior customer specialist right now."
            }
        elif any(w in q_lower for w in ["ord-", "order", "track", "tracking", "status", "delivery", "delivered", "return", "refund"]):
            decision = {
                "route": "SUPPORT",
                "sentiment_score": 3,
                "sentiment_label": "Neutral",
                "escalation_needed": False,
                "escalation_reason": None,
                "executive_summary": "Customer inquiry regarding order status or return.",
                "direct_response": None
            }
        else:
            decision = {
                "route": "SHOPPER",
                "sentiment_score": 4,
                "sentiment_label": "Satisfied",
                "escalation_needed": False,
                "escalation_reason": None,
                "executive_summary": "Product discovery inquiry.",
                "direct_response": None
            }

    decision["triage_latency_ms"] = int((time.time() - start_time) * 1000)
    return decision

# --- 2. MULTI-AGENT SUPERVISOR ORCHESTRATOR ---
def run_triage_orchestrator(
    session_id: str,
    user_query: str,
    user_name: str = "Customer",
    chat_history: Optional[List[Dict[str, str]]] = None,
    image_base64: Optional[str] = None,
    user_email: Optional[str] = None,
    user_role: Optional[str] = "customer",
    order_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point for CommerceOS multi-agent system:
    1. Evaluates session lock (if human agent is already chatting).
    2. Runs TriageBot classifier (intent + sentiment + escalation check).
    3. Handles Human Handoff dispatch and ticket creation.
    4. Delegates to ShopperBot or SupportBot with order context.
    5. Returns unified payload for UI rendering.
    """
    conn = database.get_db()
    cursor = conn.cursor()

    # Step 1: Check if session is already handed off to human
    cursor.execute("SELECT is_human_handoff, handoff_reason FROM sessions WHERE session_id = ?", (session_id,))
    sess_row = cursor.fetchone()
    if sess_row and sess_row["is_human_handoff"]:
        # Check customer intent: if they are asking an order or product inquiry, automatically resume AI!
        pre_triage = classify_and_triage(user_query, chat_history)
        if pre_triage.get("route") in ["SHOPPER", "SUPPORT", "GENERAL"]:
            cursor.execute("UPDATE sessions SET is_human_handoff = 0 WHERE session_id = ?", (session_id,))
            cursor.execute("UPDATE handoff_tickets SET status = 'RESOLVED' WHERE session_id = ? AND status = 'PENDING'", (session_id,))
            conn.commit()
        else:
            conn.close()
            return {
                "content": "A human specialist is currently assigned to your case. They will assist you shortly, or click 'Resume AI' above if you want to switch back to the AI assistant.",
                "agent": "HumanEscalationSentinel",
                "is_human_handoff": True,
                "sentiment_score": 2,
                "sentiment_label": "Frustrated",
                "triage_route": "ESCALATE_HUMAN",
                "latency_ms": 10
            }

    # Step 2: Run Triage Supervisor Classification
    triage = classify_and_triage(user_query, chat_history)
    route = triage.get("route", "SHOPPER")

    # If this is a dedicated order support chat session, default inquiries to SupportBot
    if order_id and route != "ESCALATE_HUMAN":
        route = "SUPPORT"

    sentiment_score = triage.get("sentiment_score", 3)
    sentiment_label = triage.get("sentiment_label", "Neutral")
    escalation_needed = triage.get("escalation_needed", False) or (sentiment_score <= 2)

    # Step 3: Check for Escalation Condition
    if route == "ESCALATE_HUMAN" or escalation_needed:
        ticket_id = f"TICK-{int(time.time())}"
        reason = triage.get("escalation_reason") or "Negative sentiment / user requested human agent."
        summary = triage.get("executive_summary") or f"Customer {user_name} escalated session due to frustration: '{user_query}'"

        cursor.execute("""
        INSERT OR REPLACE INTO handoff_tickets (ticket_id, session_id, customer_name, sentiment, priority, trigger_reason, summary, status, created_at)
        VALUES (?, ?, ?, ?, 'HIGH', ?, ?, 'PENDING', datetime('now'))
        """, (ticket_id, session_id, user_name, sentiment_label, reason, summary))

        cursor.execute("""
        UPDATE sessions SET is_human_handoff = 1, handoff_reason = ? WHERE session_id = ?
        """, (reason, session_id))
        conn.commit()
        conn.close()

        bot_reply = triage.get("direct_response") or (
            f"I have flagged this conversation for a human specialist. Ticket **{ticket_id}** has been created. "
            f"A representative will review your request shortly."
        )

        return {
            "content": bot_reply,
            "agent": "TriageBot",
            "ticket_id": ticket_id,
            "is_human_handoff": True,
            "sentiment_score": sentiment_score,
            "sentiment_label": sentiment_label,
            "triage_route": "ESCALATE_HUMAN",
            "executive_summary": summary,
            "latency_ms": triage.get("triage_latency_ms", 0)
        }

    # Step 4: Dispatch to Specialist Agent
    conn.close()
    if route == "SUPPORT":
        support_res = support.run_support_agent(
            session_id=session_id,
            user_query=user_query,
            chat_history=chat_history,
            image_base64=image_base64,
            user_email=user_email,
            user_role=user_role,
            order_id=order_id
        )

        # High-value refund policy escalation check
        eligibility = support_res.get("eligibility") or {}
        if eligibility.get("requires_human_approval"):
            conn = database.get_db()
            cursor = conn.cursor()
            ticket_id = f"TICK-{int(time.time())}"
            order_id = eligibility.get("order_id", "Unknown")
            amt = eligibility.get("total_amount", 0.0)
            reason = f"High-Value Refund Request for {order_id} (₹{amt:,.2f} > ₹4,000 threshold)"
            summary = f"Customer requested return for {order_id} (₹{amt:,.2f}). Requires manager authorization under policy guardrail."

            cursor.execute("""
            INSERT OR REPLACE INTO handoff_tickets (ticket_id, session_id, customer_name, sentiment, priority, trigger_reason, summary, status, created_at)
            VALUES (?, ?, ?, 'Frustrated', 'HIGH', ?, ?, 'PENDING', datetime('now'))
            """, (ticket_id, session_id, user_name, reason, summary))

            cursor.execute("""
            UPDATE sessions SET is_human_handoff = 1, handoff_reason = ? WHERE session_id = ?
            """, (reason, session_id))
            conn.commit()
            conn.close()

            support_res["is_human_handoff"] = True
            support_res["ticket_id"] = ticket_id

        support_res["sentiment_score"] = sentiment_score
        support_res["sentiment_label"] = sentiment_label
        support_res["triage_route"] = "SUPPORT"
        support_res["latency_ms"] = triage.get("triage_latency_ms", 0) + support_res.get("latency_ms", 0)
        return support_res

    elif route == "GENERAL":
        return {
            "content": triage.get("direct_response") or "Hello! I am CommerceOS AI. I can help you search our catalog of 50 products across 5 categories, track your existing orders, or process returns under our 30-day policy. What would you like to do?",
            "agent": "TriageBot",
            "sentiment_score": sentiment_score,
            "sentiment_label": sentiment_label,
            "triage_route": "GENERAL",
            "latency_ms": triage.get("triage_latency_ms", 0)
        }

    else:
        # Default route: SHOPPER
        shopper_res = shopper.run_shopper_agent(
            session_id=session_id,
            user_query=user_query,
            chat_history=chat_history,
            image_base64=image_base64,
            user_name=user_name,
            user_email=user_email
        )
        shopper_res["sentiment_score"] = sentiment_score
        shopper_res["sentiment_label"] = sentiment_label
        shopper_res["triage_route"] = "SHOPPER"
        shopper_res["latency_ms"] = triage.get("triage_latency_ms", 0) + shopper_res.get("latency_ms", 0)
        return shopper_res
