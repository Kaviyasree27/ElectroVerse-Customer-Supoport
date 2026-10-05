import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, ShoppingBag, ShieldAlert, Package, Key, Send, 
  Paperclip, RefreshCw, CheckCircle, AlertTriangle, 
  Search, Plus, Sparkles, X, Laptop, Smartphone, Headphones, 
  Zap, MessageSquare, ArrowRight, Check,
  User, Lock, LogOut, UserPlus, ShieldCheck, Mail, HelpCircle,
  Truck, ArrowLeft, Tablet, Camera, BatteryCharging, Plug, Mouse,
  Trash2, ChevronDown, Minus
} from 'lucide-react';

const renderCleanText = (text) => {
  if (!text) return '';
  return text
    .replace(/\u2011/g, '-')
    .replace(/\u202f|\u00a0/g, ' ')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/_(.*?)_/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^#{1,6}\s*/gm, '');
};

const API_BASE = (typeof window !== 'undefined' && window.location.hostname) 
  ? `http://${window.location.hostname}:8000` 
  : "http://127.0.0.1:8000";

const getUserPrefix = (email) => {
  if (!email) return 'guest';
  return email.toLowerCase().replace(/[^a-z0-9]/g, '_');
};

const TRACKING_STAGES = [
  { key: 'Placed', label: 'Placed', fullLabel: 'Order Placed', desc: 'Order confirmed' },
  { key: 'Shipped', label: 'Shipped', fullLabel: 'Shipped', desc: 'Dispatched from hub' },
  { key: 'In Transit', label: 'In Transit', fullLabel: 'In Transit', desc: 'Out for delivery' },
  { key: 'Delivered', label: 'Delivered', fullLabel: 'Delivered', desc: 'Delivered' }
];

const getStageIndex = (status) => {
  if (!status) return 0;
  const s = status.toLowerCase();
  if (s.includes('deliver')) return 3;
  if (s.includes('transit') || s.includes('out for delivery')) return 2;
  if (s.includes('ship') || s.includes('dispatch')) return 1;
  return 0; // Placed / Processing
};

function OrderTrackingStepper({ order, compact = false, onAdvanceStatus }) {
  if (!order) return null;
  const currentIdx = getStageIndex(order.status);
  const percentFill = (currentIdx / (TRACKING_STAGES.length - 1)) * 100;

  const getBadgeClass = (status) => {
    const s = (status || '').toLowerCase();
    if (s.includes('deliver')) return 'delivered';
    if (s.includes('transit')) return 'intransit';
    if (s.includes('ship')) return 'shipped';
    return 'placed';
  };

  return (
    <div className={`meesho-tracking-stepper ${compact ? 'compact' : ''}`}>
      <div className="meesho-stepper-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className={`meesho-status-badge ${getBadgeClass(order.status)}`}>
            {order.status === 'Delivered' && <CheckCircle size={13} />}
            {order.status === 'In Transit' && <Truck size={13} />}
            {order.status === 'Shipped' && <Package size={13} />}
            {order.status === 'Placed' && <Sparkles size={13} />}
            <span>● {order.status}</span>
          </span>
          <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
            {order.status === 'Delivered' 
              ? `Delivered on ${order.delivery_date || order.order_date}` 
              : `Est. Arrival: ${order.delivery_date || 'In 2-3 business days'}`}
          </span>
        </div>

        {onAdvanceStatus && (
          <button 
            type="button"
            className="btn-advance-status"
            title="Simulate next tracking stage (Placed ➔ Shipped ➔ In Transit ➔ Delivered)"
            onClick={(e) => { e.stopPropagation(); onAdvanceStatus(order.id); }}
          >
            <RefreshCw size={11} />
            <span>Next Stage</span>
          </button>
        )}
      </div>

      <div className="meesho-stepper-track">
        {/* Background & Filled Progress Line */}
        <div className="meesho-step-line-bar">
          <div className="meesho-step-line-fill" style={{ width: `${percentFill}%` }} />
        </div>

        {TRACKING_STAGES.map((st, idx) => {
          const isCompleted = idx < currentIdx;
          const isActive = idx === currentIdx;
          const isPending = idx > currentIdx;

          let nodeClass = 'pending';
          if (isCompleted) nodeClass = 'completed';
          else if (isActive) nodeClass = 'active';

          let dateText = '';
          if (idx === 0) dateText = order.order_date || 'Confirmed';
          else if (idx === 1) dateText = isCompleted || isActive ? 'Dispatched' : 'Pending';
          else if (idx === 2) dateText = isCompleted || isActive ? (order.carrier || 'BlueDart Air') : 'Upcoming';
          else if (idx === 3) dateText = order.status === 'Delivered' ? (order.delivery_date || 'Delivered') : 'Expected';

          return (
            <div key={st.key} className="meesho-step-col">
              <div className={`meesho-step-node ${nodeClass}`}>
                {isCompleted && <Check size={compact ? 12 : 15} strokeWidth={3} />}
                {isActive && (
                  idx === 2 ? <Truck size={compact ? 12 : 14} /> :
                  idx === 3 ? <CheckCircle size={compact ? 12 : 14} /> :
                  idx === 1 ? <Package size={compact ? 12 : 14} /> :
                  <span>●</span>
                )}
                {isPending && <span>{idx + 1}</span>}
              </div>

              <div className={`meesho-step-label ${nodeClass}`}>
                {compact ? st.label : st.fullLabel}
              </div>
              <div className="meesho-step-subtext" title={dateText}>
                {dateText}
              </div>
            </div>
          );
        })}
      </div>

      <div className="meesho-status-checkpoint">
        <Truck size={15} color="#818cf8" style={{ flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0, fontSize: compact ? '0.74rem' : '0.8rem' }}>
          {order.status === 'Delivered' ? (
            <span><strong>Delivered:</strong> Package delivered to your address. 30-day return policy is active.</span>
          ) : order.status === 'In Transit' ? (
            <span><strong>Out for Delivery:</strong> In transit with {order.carrier || 'BlueDart Air'} (<code style={{ color: '#818cf8' }}>{order.tracking_number}</code>).</span>
          ) : order.status === 'Shipped' ? (
            <span><strong>Dispatched:</strong> Dispatched from facility. Handed over to {order.carrier || 'Courier'}.</span>
          ) : (
            <span><strong>Order Placed:</strong> Order verified. Warehouse is packaging your items.</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  // Authentication State
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('commerce_user');
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      return null;
    }
  });

  const [authMode, setAuthMode] = useState('login'); // 'login' | 'signup' | 'admin'
  const [authName, setAuthName] = useState('');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);

  // App Navigation & Search
  const [activeTab, setActiveTab] = useState(() => {
    try {
      const saved = localStorage.getItem('commerce_user');
      if (saved) {
        const u = JSON.parse(saved);
        return u.role === 'admin' ? 'admin' : 'catalog';
      }
    } catch (e) {}
    return 'catalog';
  });

  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Session & Order Context State (User-Isolated & Order-Specific)
  const [sessionId, setSessionId] = useState(() => {
    try {
      const saved = localStorage.getItem('commerce_user');
      if (saved) {
        const u = JSON.parse(saved);
        return `session_${getUserPrefix(u.email)}_shopping`;
      }
    } catch (e) {}
    return 'session_guest_shopping';
  });

  const [activeOrderContext, setActiveOrderContext] = useState(null); // { id, name, items, total_amount, carrier, tracking_number }
  const [customSessions, setCustomSessions] = useState([]);
  
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isHandoffActive, setIsHandoffActive] = useState(false);

  // Data
  const [systemStatus, setSystemStatus] = useState(null);
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [humanReply, setHumanReply] = useState('');
  const [cart, setCart] = useState({ items: [], total: 0 });
  const [addedNotice, setAddedNotice] = useState(null);
  const [showProfileMenu, setShowProfileMenu] = useState(false);

  // Modals
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // When user logs in or switches, initialize their isolated sessions
  useEffect(() => {
    if (currentUser) {
      const prefix = getUserPrefix(currentUser.email);
      const defaultSess = `session_${prefix}_shopping`;
      if (!sessionId.startsWith(`session_${prefix}_`)) {
        setSessionId(defaultSess);
        setActiveOrderContext(null);
        setMessages([]);
      }
      fetchStatus();
      fetchProducts();
      fetchOrders();
      fetchCart();
      if (currentUser.role === 'admin') {
        fetchTickets();
      }
    }
  }, [currentUser]);

  // Re-fetch messages and cart whenever active session changes
  useEffect(() => {
    if (currentUser && sessionId) {
      fetchMessages();
      fetchCart();
    }
  }, [sessionId]);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      const data = await res.json();
      setSystemStatus(data);
    } catch (err) {}
  };

  const fetchProducts = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/products`);
      const data = await res.json();
      setProducts(data.products || []);
    } catch (err) {}
  };

  const fetchOrders = async () => {
    if (!currentUser) return;
    try {
      const url = currentUser.role === 'admin'
        ? `${API_BASE}/api/orders?role=admin`
        : `${API_BASE}/api/orders?email=${encodeURIComponent(currentUser.email)}&role=customer`;
      const res = await fetch(url);
      const data = await res.json();
      setOrders(data.orders || []);
    } catch (err) {}
  };

  const fetchCart = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/cart/${sessionId}`);
      const data = await res.json();
      setCart(data);
    } catch (err) {}
  };

  const fetchMessages = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/messages/${sessionId}`);
      const data = await res.json();
      setMessages(data.messages || []);
      setIsHandoffActive(data.is_human_handoff || false);
    } catch (err) {}
  };

  const fetchTickets = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/handoff/tickets`);
      const data = await res.json();
      setTickets(data.tickets || []);
      if (data.tickets && data.tickets.length > 0 && !selectedTicket) {
        setSelectedTicket(data.tickets[0]);
      }
    } catch (err) {}
  };

  // Auth Handlers
  const handleAuthSubmit = async (e) => {
    if (e) e.preventDefault();
    setAuthError('');
    setAuthLoading(true);

    try {
      const isSignup = authMode === 'signup';
      const endpoint = isSignup ? `${API_BASE}/api/auth/signup` : `${API_BASE}/api/auth/login`;
      const payload = isSignup
        ? { name: authName.trim(), email: authEmail.trim(), password: authPassword.trim() }
        : { email: authEmail.trim(), password: authPassword.trim() };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Authentication failed. Please check your credentials.');
      }

      const user = data.user;
      localStorage.setItem('commerce_user', JSON.stringify(user));
      setCurrentUser(user);

      // Initialize fresh user-isolated session
      const prefix = getUserPrefix(user.email);
      setSessionId(`session_${prefix}_shopping`);
      setActiveOrderContext(null);
      setMessages([]);
      setActiveTab(user.role === 'admin' ? 'admin' : 'catalog');
      
      setAddedNotice(data.message || 'Logged in successfully!');
      setTimeout(() => setAddedNotice(null), 4000);
    } catch (err) {
      setAuthError(err.message || 'An error occurred during authentication.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleQuickCustomer = () => {
    setAuthMode('login');
    setAuthEmail('alex@gmail.com');
    setAuthPassword('password123');
    setAuthError('');
  };

  const handleQuickAdmin = () => {
    setAuthMode('admin');
    setAuthEmail('admin123@gmail.com');
    setAuthPassword('admin27');
    setAuthError('');
  };

  const handleLogout = () => {
    localStorage.removeItem('commerce_user');
    setCurrentUser(null);
    setAuthEmail('');
    setAuthPassword('');
    setAuthError('');
    setMessages([]);
    setCart({ items: [], total: 0 });
    setActiveOrderContext(null);
    setSessionId('session_guest_shopping');
    setActiveTab('catalog');
  };

  const handleSaveApiKey = async () => {
    if (!apiKeyInput.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/settings/key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKeyInput.trim() })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setShowKeyModal(false);
        fetchStatus();
      }
    } catch (err) {
      alert("Failed to save API key");
    }
  };

  const handleUpdateCartQty = async (itemId, currentQty, delta) => {
    const newQty = currentQty + delta;
    try {
      if (newQty <= 0) {
        await fetch(`${API_BASE}/api/cart/${itemId}`, { method: 'DELETE' });
      } else {
        await fetch(`${API_BASE}/api/cart/${itemId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ quantity: newQty })
        });
      }
      fetchCart();
    } catch (err) {
      console.error(err);
    }
  };

  const handleRemoveCartItem = async (itemId) => {
    try {
      await fetch(`${API_BASE}/api/cart/${itemId}`, { method: 'DELETE' });
      fetchCart();
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddToCart = async (product) => {
    try {
      await fetch(`${API_BASE}/api/cart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          product_id: product.id,
          quantity: 1
        })
      });
      fetchCart();
      setAddedNotice(`Added ${product.name} to cart!`);
      setTimeout(() => setAddedNotice(null), 2500);
    } catch (err) {}
  };

  const handleCheckout = async () => {
    if (!cart.items || cart.items.length === 0) return;
    try {
      const res = await fetch(`${API_BASE}/api/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          customer_name: currentUser?.name || 'Customer',
          customer_email: currentUser?.email || 'customer@gmail.com'
        })
      });
      const data = await res.json();
      if (data.status === 'success') {
        fetchCart();
        fetchOrders();
        setAddedNotice(`🎉 ${data.message}`);
        setTimeout(() => setAddedNotice(null), 5000);
      }
    } catch (err) {
      alert("Failed to checkout.");
    }
  };

  const handleAdvanceOrderStatus = async (orderId) => {
    if (!orderId) return;
    try {
      const res = await fetch(`${API_BASE}/api/orders/${orderId}/advance_status`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'success') {
        fetchOrders();
        if (activeOrderContext && activeOrderContext.id.toUpperCase() === orderId.toUpperCase()) {
          setActiveOrderContext(data.order);
        }
        setAddedNotice(`Tracking Stage: Order #${orderId} moved to ${data.new_status}!`);
        setTimeout(() => setAddedNotice(null), 3000);
      }
    } catch (err) {}
  };

  const handleUnfreezeSession = async () => {
    try {
      await fetch(`${API_BASE}/api/session/unfreeze/${sessionId}`, { method: 'POST' });
      setIsHandoffActive(false);
      fetchMessages();
      fetchTickets();
      setAddedNotice("✅ AI Assistant resumed! Ready to chat.");
      setTimeout(() => setAddedNotice(null), 3000);
    } catch (err) {}
  };

  // Launch order-specific chat (Myntra / Meesho style)
  const openOrderHelpChat = (order, autoPrompt = null) => {
    const prefix = getUserPrefix(currentUser.email);
    const orderSessionId = `session_${prefix}_order_${order.id.toLowerCase()}`;
    setSessionId(orderSessionId);
    setActiveOrderContext(order);
    setActiveTab('agent');
    if (autoPrompt) {
      handleSendMessage(autoPrompt, order.id);
    }
  };

  // Switch to general shopping assistant
  const openShoppingChat = () => {
    const prefix = getUserPrefix(currentUser.email);
    const shoppingSessionId = `session_${prefix}_shopping`;
    setSessionId(shoppingSessionId);
    setActiveOrderContext(null);
    setActiveTab('agent');
  };

  const handleCreateNewSession = () => {
    const prefix = getUserPrefix(currentUser?.email);
    const newIndex = customSessions.length + 1;
    const newId = `session_${prefix}_inquiry_${newIndex}`;
    const newSession = { id: newId, name: `Custom Chat ${newIndex}` };
    setCustomSessions(prev => [...prev, newSession]);
    setSessionId(newId);
    setActiveOrderContext(null);
    setMessages([]);
  };

  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedImage(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const removeSelectedImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSendMessage = async (textToSend, explicitOrderId = null) => {
    const query = textToSend || inputMessage;
    if (!query.trim() && !imagePreview) return;

    const targetOrderId = explicitOrderId || activeOrderContext?.id || null;

    const userMsg = {
      id: Date.now(),
      sender: 'user',
      content: query,
      created_at: new Date().toLocaleTimeString()
    };
    setMessages(prev => [...prev, userMsg]);
    setInputMessage('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: query,
          user_name: currentUser?.name || 'Customer',
          user_email: currentUser?.email,
          user_role: currentUser?.role || 'customer',
          order_id: targetOrderId,
          image_base64: imagePreview ? imagePreview.split(',')[1] : null
        })
      });
      const data = await res.json();

      const botMsg = {
        id: Date.now() + 1,
        sender: data.agent || 'ElectroVerse',
        content: data.content || "Response received.",
        metadata: {
          products: data.products || [],
          cart_added: data.cart_added,
          order: data.order,
          eligibility: data.eligibility,
          return_result: data.return_result,
          sentiment_score: data.sentiment_score,
          sentiment_label: data.sentiment_label,
          triage_route: data.triage_route,
          is_human_handoff: data.is_human_handoff,
          ticket_id: data.ticket_id,
          latency_ms: data.latency_ms,
          tokens: data.tokens,
          provider: data.provider
        },
        created_at: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, botMsg]);

      setIsHandoffActive(Boolean(data.is_human_handoff));
      if (data.is_human_handoff && currentUser?.role === 'admin') {
        fetchTickets();
      }

      if (data.cart_added?.success || data.order) {
        fetchCart();
        fetchOrders();
      }
      fetchStatus();
    } catch (err) {
      const errMsg = {
        id: Date.now() + 1,
        sender: 'System',
        content: "Error communicating with server. Ensure backend is running.",
        created_at: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setLoading(false);
      removeSelectedImage();
    }
  };

  const handleHumanReply = async (action = 'REPLY') => {
    if (!selectedTicket) return;
    const msgToSend = humanReply.trim() || (action === 'RESOLVE' ? "Incident reviewed and resolved by customer supervisor. AI Assistant is now resumed." : "");
    if (!msgToSend && action !== 'RESOLVE') {
      alert("Please type a message before sending.");
      return;
    }
    try {
      await fetch(`${API_BASE}/api/handoff/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticket_id: selectedTicket.ticket_id,
          session_id: selectedTicket.session_id,
          response_message: msgToSend,
          action: action
        })
      });
      setHumanReply('');
      if (action === 'RESOLVE') {
        setIsHandoffActive(false);
        setAddedNotice("✅ Incident resolved! AI Agent has resumed.");
        setTimeout(() => setAddedNotice(null), 4000);
      } else {
        setAddedNotice("💬 Human message sent to customer chat!");
        setTimeout(() => setAddedNotice(null), 3000);
      }
      fetchTickets();
      fetchMessages();
    } catch (err) {
      alert("Failed to submit response.");
    }
  };

  // Filter products by category and search
  const filteredProducts = products.filter(p => {
    const matchesCat = selectedCategory === 'All' || p.category.toLowerCase() === selectedCategory.toLowerCase();
    const matchesSearch = searchQuery === '' || 
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
      p.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  const categories = [
    { name: 'All', icon: Sparkles, count: products.length },
    { name: 'Laptops', icon: Laptop, count: products.filter(p => p.category === 'Laptops').length },
    { name: 'Phones', icon: Smartphone, count: products.filter(p => p.category === 'Phones').length },
    { name: 'Headphones', icon: Headphones, count: products.filter(p => p.category === 'Headphones').length },
    { name: 'Tablets', icon: Tablet, count: products.filter(p => p.category === 'Tablets').length },
    { name: 'Cameras', icon: Camera, count: products.filter(p => p.category === 'Cameras').length },
    { name: 'Accessories', icon: Mouse, count: products.filter(p => p.category === 'Accessories').length }
  ];

  // Helper to determine active thread title
  const userPrefix = currentUser ? getUserPrefix(currentUser.email) : 'guest';
  const isGeneralChat = sessionId === `session_${userPrefix}_shopping`;

  // =========================================================================
  // VIEW 1: AUTHENTICATION SCREEN (CUSTOMER LOGIN/SIGNUP & ADMIN PORTAL)
  // =========================================================================
  if (!currentUser) {
    return (
      <div className="auth-wrapper">
        <div className="auth-card">
          <div className="auth-header">
            <div className="auth-logo-badge">
              <Bot size={28} />
            </div>
            <h1 className="auth-title">ElectroVerse</h1>
            <p className="auth-subtitle">Autonomous E-Commerce Multi-Agent Platform</p>
          </div>

          {/* Segmented Auth Mode Switcher */}
          <div className="auth-tabs">
            <button 
              id="tab-customer-login"
              type="button"
              className={`auth-tab ${authMode === 'login' ? 'active' : ''}`}
              onClick={() => { setAuthMode('login'); setAuthError(''); }}
            >
              <User size={13} />
              <span>Customer Login</span>
            </button>

            <button 
              id="tab-customer-signup"
              type="button"
              className={`auth-tab ${authMode === 'signup' ? 'active' : ''}`}
              onClick={() => { setAuthMode('signup'); setAuthError(''); }}
            >
              <UserPlus size={13} />
              <span>Customer Sign Up</span>
            </button>
          </div>

          {/* Error Notice */}
          {authError && (
            <div className="auth-error-box" style={{ marginBottom: '16px' }}>
              <AlertTriangle size={16} />
              <span>{authError}</span>
            </div>
          )}

          {/* Auth Form */}
          <form className="auth-form" onSubmit={handleAuthSubmit}>
            {authMode === 'signup' && (
              <div className="auth-field">
                <label className="auth-label">Full Name</label>
                <input 
                  id="auth-name-input"
                  type="text"
                  required
                  placeholder="e.g. Kaviya Sree"
                  className="auth-input"
                  value={authName}
                  onChange={(e) => setAuthName(e.target.value)}
                />
              </div>
            )}

            <div className="auth-field">
              <label className="auth-label">Email Address</label>
              <input 
                id="auth-email-input"
                type="email"
                required
                placeholder="yourname@gmail.com"
                className="auth-input"
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
              />
            </div>

            <div className="auth-field">
              <label className="auth-label">Password</label>
              <input 
                id="auth-password-input"
                type="password"
                required
                placeholder="••••••••"
                className="auth-input"
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
              />
            </div>

            <button 
              id="auth-submit-btn"
              type="submit" 
              className="auth-btn-submit"
              disabled={authLoading}
            >
              {authLoading ? (
                <span>Authenticating...</span>
              ) : authMode === 'signup' ? (
                <>
                  <UserPlus size={16} />
                  <span>Create Account</span>
                </>
              ) : (
                <>
                  <User size={16} />
                  <span>Sign In</span>
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // =========================================================================
  // VIEW 2: LOGGED-IN ENTERPRISE WORKSPACE (CUSTOMER VS ADMIN VIEWS)
  // =========================================================================
  return (
    <div className="enterprise-layout">
      {/* 1. LEFT INDUSTRIAL SIDEBAR */}
      <aside className="app-sidebar">
        {/* Brand Header */}
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-icon">
              <Bot size={20} />
            </div>
            <div>
              <div className="brand-title">ElectroVerse</div>
              <span className="brand-badge">Enterprise v2.5</span>
            </div>
          </div>
        </div>

        {/* Primary Navigation Menu (Role-Based) */}
        <div className="sidebar-section" style={{ paddingTop: '16px' }}>
          <div className="sidebar-label">
            {currentUser.role === 'admin' ? "Admin Operations" : "Shopping & Orders"}
          </div>
          <div className="sidebar-nav-list">
            {/* ADMIN ONLY TAB: Human Handoff Queue */}
            {currentUser.role === 'admin' && (
              <button 
                id="nav-admin"
                className={`sidebar-nav-item ${activeTab === 'admin' ? 'active' : ''}`}
                onClick={() => setActiveTab('admin')}
              >
                <div className="nav-item-left">
                  <ShieldAlert size={18} color="#f87171" />
                  <span style={{ fontWeight: 600 }}>Human Handoff Queue</span>
                </div>
                {tickets.filter(t => t.status === 'PENDING').length > 0 && (
                  <span className="nav-badge-pill" style={{ background: '#ef4444' }}>
                    {tickets.filter(t => t.status === 'PENDING').length}
                  </span>
                )}
              </button>
            )}

            {/* ORDER TAB */}
            <button 
              id="nav-orders"
              className={`sidebar-nav-item ${activeTab === 'orders' ? 'active' : ''}`}
              onClick={() => setActiveTab('orders')}
            >
              <div className="nav-item-left">
                <Package size={18} />
                <span>{currentUser.role === 'admin' ? "All Company Orders" : "My Orders"}</span>
              </div>
              <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{orders.length}</span>
            </button>

            {/* STORE CATALOG TAB */}
            <button 
              id="nav-catalog"
              className={`sidebar-nav-item ${activeTab === 'catalog' ? 'active' : ''}`}
              onClick={() => setActiveTab('catalog')}
            >
              <div className="nav-item-left">
                <ShoppingBag size={18} />
                <span>Store Catalog</span>
              </div>
              <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{products.length}</span>
            </button>

            {/* BOT TAB (ENDING WITH BOT) */}
            <button 
              id="nav-agent"
              className={`sidebar-nav-item ${activeTab === 'agent' ? 'active' : ''}`}
              onClick={() => { setActiveTab('agent'); }}
            >
              <div className="nav-item-left">
                <MessageSquare size={18} />
                <span>ShopBot</span>
              </div>
            </button>
          </div>
        </div>

        {/* Dynamic User-Isolated Chats */}
        <div className="sidebar-section">
          <div className="sidebar-label">
            {currentUser.role === 'admin' ? "Active Inspection Sessions" : "Your Chats"}
          </div>
          <div className="sessions-list">
            {/* Primary General Shopping Chat */}
            <button
              className={`session-btn ${isGeneralChat ? 'active' : ''}`}
              onClick={openShoppingChat}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShoppingBag size={14} color="#60a5fa" />
                <span>General Shopping Bot</span>
              </div>
              {isGeneralChat && <Check size={14} />}
            </button>

            {/* Order-Specific Chats for each purchased item */}
            {orders.map(o => {
              const orderSessId = `session_${userPrefix}_order_${o.id.toLowerCase()}`;
              const isOrderChatActive = sessionId === orderSessId;
              const firstItem = Array.isArray(o.items) && o.items.length > 0 ? o.items[0] : null;

              return (
                <button
                  key={o.id}
                  className={`session-btn ${isOrderChatActive ? 'active' : ''}`}
                  onClick={() => openOrderHelpChat(o)}
                  title={`Chat for Order ${o.id}`}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                    <Package size={14} color="#c084fc" />
                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {o.id}: {firstItem ? firstItem.name.split(' ')[0] : 'Order'} Help
                    </span>
                  </div>
                  {isOrderChatActive && <Check size={14} />}
                </button>
              );
            })}

            {/* Any user created scratch inquiry sessions */}
            {customSessions.map(s => (
              <button
                key={s.id}
                className={`session-btn ${sessionId === s.id ? 'active' : ''}`}
                onClick={() => { setSessionId(s.id); setActiveOrderContext(null); }}
              >
                <span>{s.name}</span>
                {sessionId === s.id && <Check size={14} />}
              </button>
            ))}
          </div>

          <button className="new-session-btn" onClick={handleCreateNewSession}>
            <Plus size={14} />
            <span>New Chat</span>
          </button>
        </div>
      </aside>

      {/* 2. MAIN WORKSPACE AREA */}
      <div className="app-main">
        {/* Top Header Bar */}
        <header className="topbar">
          <div className="topbar-left">
            <div>
              <div className="topbar-title">
                {activeTab === 'catalog' && "Store Product Catalog"}
                {activeTab === 'agent' && (activeOrderContext ? `Order Support: #${activeOrderContext.id}` : "ShopBot Assistant")}
                {activeTab === 'cart' && "My Shopping Bag"}
                {activeTab === 'admin' && "Admin Operations · Human Incident Queue"}
                {activeTab === 'orders' && (currentUser.role === 'admin' ? "Company Order Registry" : "My Orders")}
              </div>
              <div className="topbar-subtitle">
                {activeTab === 'catalog' && `Browsing ${filteredProducts.length} verified products with real-time stock & specs`}
                {activeTab === 'cart' && "Review selected products, modify quantities, and place your order"}
                {activeTab === 'agent' && (activeOrderContext 
                  ? `Dedicated support thread for ${activeOrderContext.items?.[0]?.name || 'Purchased Item'}`
                  : `Autonomous assistant for product discovery, orders, and support`
                )}
                {activeTab === 'admin' && "Live escalations triggered by customer sentiment or policy thresholds"}
                {activeTab === 'orders' && (currentUser.role === 'admin' 
                  ? `Global database of ${orders.length} orders across all customer accounts`
                  : `Select any item below to view tracking checkpoints or request support`
                )}
              </div>
            </div>
          </div>

          <div className="topbar-right">
            {addedNotice && (
              <span style={{ color: '#34d399', fontSize: '0.8rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle size={14} /> {addedNotice}
              </span>
            )}

            {/* Cart Icon Button (Beside Profile Avatar) */}
            <button 
              id="topbar-cart-btn"
              className={`cart-icon-btn ${activeTab === 'cart' ? 'active' : ''}`}
              title="Shopping Cart"
              onClick={() => { setActiveTab('cart'); }}
            >
              <ShoppingBag size={18} />
              <span>Cart</span>
              {(cart.items?.reduce((acc, i) => acc + i.quantity, 0) || 0) > 0 && (
                <span className="cart-badge">{cart.items?.reduce((acc, i) => acc + i.quantity, 0)}</span>
              )}
            </button>

            {/* Gmail-Style User Profile Avatar (Top Right) */}
            <div className="profile-menu-wrapper" style={{ position: 'relative' }}>
              <button
                id="btn-profile-avatar"
                className="gmail-avatar-btn"
                title={`${currentUser?.name} (${currentUser?.email})`}
                onClick={() => setShowProfileMenu(prev => !prev)}
              >
                {(currentUser?.name || currentUser?.email || 'U').charAt(0).toUpperCase()}
              </button>

              {showProfileMenu && (
                <div className="gmail-profile-dropdown">
                  <div className="profile-dropdown-header">
                    <div className="profile-large-avatar">
                      {(currentUser?.name || currentUser?.email || 'U').charAt(0).toUpperCase()}
                    </div>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div className="profile-dropdown-name">{currentUser?.name}</div>
                      <div className="profile-dropdown-email">{currentUser?.email}</div>
                      <span className={`user-role-pill ${currentUser?.role}`} style={{ marginTop: '4px', display: 'inline-block' }}>
                        {currentUser?.role === 'admin' ? '🛡️ Administrator' : '👤 Customer'}
                      </span>
                    </div>
                  </div>
                  <div className="profile-dropdown-actions">
                    <button 
                      id="dropdown-logout-btn"
                      className="profile-dropdown-logout"
                      onClick={() => { setShowProfileMenu(false); handleLogout(); }}
                    >
                      <LogOut size={14} />
                      <span>Logout</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Viewport for Selected Tab */}
        <main className="view-viewport">
          {/* ======================================================== */}
          {/* TAB 1: 50 REAL PRODUCTS CATALOG                          */}
          {/* ======================================================== */}
          {activeTab === 'catalog' && (
            <div>
              {/* Category Pills & Search Bar */}
              <div className="catalog-header-bar">
                <div className="category-pills">
                  {categories.map((cat) => {
                    const Icon = cat.icon;
                    return (
                      <button
                        key={cat.name}
                        className={`cat-pill ${selectedCategory === cat.name ? 'active' : ''}`}
                        onClick={() => setSelectedCategory(cat.name)}
                      >
                        <Icon size={15} />
                        <span>{cat.name}</span>
                        <span style={{ opacity: 0.6, fontSize: '0.72rem' }}>({cat.count})</span>
                      </button>
                    );
                  })}
                </div>

                <div className="search-box-wrap">
                  <Search size={15} className="search-icon" />
                  <input 
                    id="search-input"
                    className="search-input"
                    placeholder="Search by name, specs, or price..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>

              {/* 50 Products Grid */}
              <div className="products-grid">
                {filteredProducts.map((p) => {
                  let specs = {};
                  try {
                    specs = typeof p.specs === 'string' ? JSON.parse(p.specs) : p.specs;
                  } catch (e) {}

                  return (
                    <div key={p.id} className="product-item-card">
                      <div className="product-img-wrapper">
                        <img src={p.image_url} alt={p.name} className="product-img" loading="lazy" />
                        <span className="product-category-tag">{p.category}</span>
                      </div>

                      <div className="product-card-content">
                        <div className="product-card-header">
                          <span className="product-id-badge">{p.id}</span>
                          <h3 className="product-card-title">{p.name}</h3>
                        </div>

                        <p className="product-card-desc">{p.description}</p>

                        {/* Specs Mini Chips */}
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '12px' }}>
                          {Object.entries(specs).slice(0, 2).map(([key, val]) => (
                            <span key={key} style={{ fontSize: '0.68rem', background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: '4px', color: '#94a3b8' }}>
                              {String(val)}
                            </span>
                          ))}
                        </div>

                        <div className="product-card-footer">
                          <div>
                            <div className="product-price-val">₹{p.price?.toLocaleString()}</div>
                            <span className="product-stock-pill">{p.stock} in stock</span>
                          </div>

                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button 
                              className="btn-add-cart"
                              onClick={() => handleAddToCart(p)}
                            >
                              Add to Cart
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ======================================================== */}
          {/* TAB 2: AI AGENT HUB (WITH DEDICATED ORDER CHAT CONTEXT)  */}
          {/* ======================================================== */}
          {activeTab === 'agent' && (
            <div className="chat-workspace">
              {/* Left / Middle: Chat Box */}
              <div className="chat-card-frame">
                <div className="chat-card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div className="brand-icon" style={{ width: '32px', height: '32px' }}>
                      <Bot size={16} />
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span>ShopBot Assistant</span>
                        {activeOrderContext && (
                          <span className="chat-order-badge">
                            📦 Order #{activeOrderContext.id}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: isHandoffActive ? '#f59e0b' : '#34d399' }}>
                        {isHandoffActive ? '⚠️ Handed off to Human Specialist' : '● Online · Ready to Assist'}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {activeOrderContext && (
                      <button 
                        onClick={openShoppingChat}
                        className="session-btn"
                        style={{ padding: '4px 10px', fontSize: '0.72rem', background: 'rgba(255,255,255,0.06)' }}
                        title="Switch back to General Shopping Chat"
                      >
                        <ArrowLeft size={12} />
                        <span>General Shopping</span>
                      </button>
                    )}
                    {isHandoffActive && (
                      <button 
                        onClick={handleUnfreezeSession}
                        style={{ background: '#10b981', color: 'white', border: 'none', borderRadius: '6px', padding: '4px 10px', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
                        title="Resume autonomous AI assistant"
                      >
                        <RefreshCw size={12} />
                        <span>Resume AI</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Dedicated Order Help Context Banner (Myntra/Meesho Style) */}
                {activeOrderContext && (
                  <div className="chat-order-context-banner">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <Package size={18} color="#a5b4fc" />
                      <div>
                        <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#ffffff' }}>
                          Need Help with Order #{activeOrderContext.id}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#cbd5e1' }}>
                          {activeOrderContext.items?.[0]?.name || 'Purchased Item'} • Total: ₹{activeOrderContext.total_amount?.toLocaleString()} • Status: <span style={{ color: activeOrderContext.status === 'Delivered' ? '#34d399' : '#38bdf8', fontWeight: 600 }}>{activeOrderContext.status}</span>
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button 
                        className="session-btn"
                        style={{ fontSize: '0.7rem', padding: '3px 8px', background: 'rgba(99,102,241,0.2)' }}
                        onClick={() => handleSendMessage(`Where is my order ${activeOrderContext.id}?`)}
                      >
                        Track
                      </button>
                      <button 
                        className="session-btn"
                        style={{ fontSize: '0.7rem', padding: '3px 8px', background: 'rgba(239,68,68,0.2)', color: '#f87171' }}
                        onClick={() => handleSendMessage(`I want to return order ${activeOrderContext.id}`)}
                      >
                        Return
                      </button>
                    </div>
                  </div>
                )}

                {/* Messages Stream */}
                <div className="chat-card-messages">
                  {messages.length === 0 ? (
                    <div style={{ textAlign: 'center', margin: 'auto', color: '#64748b' }}>
                      <Bot size={40} style={{ margin: '0 auto 10px', opacity: 0.4 }} />
                      <h3 style={{ color: '#94a3b8', fontSize: '1.05rem', marginBottom: '4px' }}>
                        {activeOrderContext 
                          ? `Order Support for #${activeOrderContext.id}`
                          : `Hello ${currentUser?.name}! How can I help you today?`
                        }
                      </h3>
                      <p style={{ fontSize: '0.82rem', maxWidth: '380px', margin: '0 auto 12px' }}>
                        {activeOrderContext
                          ? `You are chatting in the dedicated support channel for ${activeOrderContext.items?.[0]?.name || 'this item'}. Ask about delivery tracking, return authorization, or product issues.`
                          : `Ask for budget laptops, ₹299 shoes, check your orders, or upload an image!`
                        }
                      </p>
                      {activeOrderContext && (
                        <div style={{ display: 'inline-flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
                          <button 
                            className="session-btn" 
                            style={{ fontSize: '0.75rem', background: 'rgba(99,102,241,0.15)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.3)' }}
                            onClick={() => handleSendMessage(`Where is my order ${activeOrderContext.id}?`)}
                          >
                            "Where is my order delivery?"
                          </button>
                          <button 
                            className="session-btn" 
                            style={{ fontSize: '0.75rem', background: 'rgba(239,68,68,0.12)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.3)' }}
                            onClick={() => handleSendMessage(`I want to return order ${activeOrderContext.id}`)}
                          >
                            "I want to return this product"
                          </button>
                        </div>
                      )}
                    </div>
                  ) : (
                    messages.map((m, idx) => (
                      <div key={idx} className={`chat-msg-row ${m.sender === 'user' ? 'user' : 'bot'}`}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <span className="chat-msg-sender" style={{
                            color: m.sender === 'SupportBot' ? '#c084fc' : m.sender === 'TriageBot' ? '#34d399' : m.sender === 'ShopperBot' ? '#60a5fa' : m.sender === 'human_agent' ? '#fbbf24' : '#94a3b8'
                          }}>
                            {m.sender === 'user' ? (currentUser?.name || 'You') : m.sender}
                          </span>
                          {m.metadata?.sentiment_label && (
                            <span style={{
                              fontSize: '0.65rem',
                              fontWeight: 600,
                              padding: '1px 6px',
                              borderRadius: '4px',
                              background: m.metadata.sentiment_label === 'Frustrated' ? 'rgba(239, 68, 68, 0.2)' : m.metadata.sentiment_label === 'Dissatisfied' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(52, 211, 153, 0.15)',
                              color: m.metadata.sentiment_label === 'Frustrated' ? '#f87171' : m.metadata.sentiment_label === 'Dissatisfied' ? '#fbbf24' : '#34d399',
                              border: `1px solid ${m.metadata.sentiment_label === 'Frustrated' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(255,255,255,0.06)'}`
                            }}>
                              {m.metadata.sentiment_label === 'Frustrated' ? '⚠️ Frustrated' : m.metadata.sentiment_label}
                            </span>
                          )}
                          {m.metadata?.triage_route && (
                            <span style={{ fontSize: '0.65rem', color: '#64748b' }}>
                              → {m.metadata.triage_route}
                            </span>
                          )}
                        </div>

                        <div className="chat-msg-bubble">
                          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.55 }}>
                            {renderCleanText(m.content)}
                          </div>

                          {/* Render Rich Product Cards */}
                          {m.metadata?.products && m.metadata.products.length > 0 && (
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '10px', marginTop: '12px' }}>
                              {m.metadata.products.map(prod => (
                                <div key={prod.id} style={{ background: 'rgba(7, 10, 19, 0.75)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                                  <img src={prod.image_url} alt={prod.name} style={{ width: '100%', height: '110px', objectFit: 'cover' }} />
                                  <div style={{ padding: '10px', display: 'flex', flexDirection: 'column', flex: 1 }}>
                                    <span style={{ fontSize: '0.65rem', color: '#94a3b8' }}>{prod.id} • {prod.category}</span>
                                    <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#ffffff', margin: '2px 0 6px', display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                      {prod.name}
                                    </div>
                                    <div style={{ marginTop: 'auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                      <span style={{ color: '#34d399', fontWeight: 700, fontSize: '0.9rem' }}>₹{prod.price?.toLocaleString()}</span>
                                      <button 
                                        className="btn-add-cart"
                                        style={{ padding: '4px 8px', fontSize: '0.72rem' }}
                                        onClick={() => handleAddToCart(prod)}
                                      >
                                        Add to Cart
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Render Order Tracking Card (Meesho / Myntra 4-Stage Stepper) */}
                          {m.metadata?.order && m.metadata.order.found && (
                            <div style={{ marginTop: '12px' }}>
                              <OrderTrackingStepper 
                                order={m.metadata.order} 
                                compact={true} 
                                onAdvanceStatus={handleAdvanceOrderStatus} 
                              />
                            </div>
                          )}

                          {/* Render Return Authorized Card */}
                          {m.metadata?.return_result?.success && (
                            <div style={{ marginTop: '12px', background: 'rgba(6, 78, 59, 0.35)', border: '1px solid rgba(52, 211, 153, 0.4)', borderRadius: '10px', padding: '12px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#34d399', fontWeight: 600, fontSize: '0.85rem', marginBottom: '6px' }}>
                                <CheckCircle size={16} />
                                <span>Return Authorized · Instant Label Generated</span>
                              </div>
                              <div style={{ fontSize: '0.78rem', color: '#e2e8f0' }}>
                                <div><strong>Label Code:</strong> <code style={{ background: 'rgba(0,0,0,0.3)', padding: '2px 6px', borderRadius: '4px', color: '#34d399' }}>{m.metadata.return_result.return_label_code}</code></div>
                                <div style={{ marginTop: '3px' }}><strong>Courier:</strong> {m.metadata.return_result.carrier} ({m.metadata.return_result.pickup_window})</div>
                                <div style={{ marginTop: '3px' }}><strong>Refund Amount:</strong> ₹{m.metadata.return_result.refund_amount?.toLocaleString()} (Released on handover)</div>
                              </div>
                            </div>
                          )}

                          {/* Render Human Escalation Notice */}
                          {(m.metadata?.is_human_handoff || m.metadata?.eligibility?.requires_human_approval) && (
                            <div style={{ marginTop: '12px', background: 'rgba(120, 53, 15, 0.35)', border: '1px solid rgba(245, 158, 11, 0.4)', borderRadius: '10px', padding: '12px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fbbf24', fontWeight: 600, fontSize: '0.85rem' }}>
                                  <ShieldAlert size={16} />
                                  <span>Transferred to Customer Specialist</span>
                                </div>
                                {m.metadata.ticket_id && (
                                  <span style={{ fontSize: '0.7rem', background: 'rgba(245, 158, 11, 0.2)', color: '#fde68a', padding: '2px 6px', borderRadius: '4px', fontFamily: 'monospace' }}>
                                    {m.metadata.ticket_id}
                                  </span>
                                )}
                              </div>
                              <p style={{ fontSize: '0.78rem', color: '#fef3c7', margin: 0, marginBottom: '8px' }}>
                                Case elevated for specialist review. A customer agent will respond shortly.
                              </p>
                              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                {currentUser?.role === 'admin' && (
                                  <button 
                                    onClick={() => setActiveTab('admin')}
                                    style={{ fontSize: '0.72rem', background: '#d97706', color: '#ffffff', border: 'none', borderRadius: '6px', padding: '6px 12px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}
                                  >
                                    <span>Open Human Handoff Queue Tab</span>
                                    <ArrowRight size={13} />
                                  </button>
                                )}
                                <button 
                                  onClick={handleUnfreezeSession}
                                  style={{ fontSize: '0.72rem', background: '#10b981', color: '#ffffff', border: 'none', borderRadius: '6px', padding: '6px 12px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}
                                >
                                  <RefreshCw size={12} />
                                  <span>Resume AI Agent</span>
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                        {m.metadata && (
                          <div className="chat-msg-telemetry">
                            {m.metadata.latency_ms && <span>⚡ {m.metadata.latency_ms}ms</span>}
                            {m.metadata.tokens?.total && <span>📊 {m.metadata.tokens.total} tokens</span>}
                            {m.metadata.provider && <span>🧠 {m.metadata.provider}</span>}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                  {loading && (
                    <div className="chat-msg-row bot">
                      <span className="chat-msg-sender">ElectroVerse</span>
                      <div className="chat-msg-bubble" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <span className="pulse-dot"></span> Thinking and retrieving data...
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input Controls */}
                <div className="chat-input-container">
                  {imagePreview && (
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: 'rgba(99,102,241,0.2)', padding: '4px 10px', borderRadius: '999px', fontSize: '0.75rem', color: '#a5b4fc' }}>
                      <span>📷 Image Attached</span>
                      <button onClick={removeSelectedImage} style={{ background: 'none', border: 'none', color: '#f43f5e', cursor: 'pointer' }}>
                        <X size={12} />
                      </button>
                    </div>
                  )}

                  <div className="input-flex-row">
                    <input 
                      type="file" 
                      ref={fileInputRef} 
                      onChange={handleImageSelect} 
                      accept="image/*" 
                      style={{ display: 'none' }} 
                    />
                    <button 
                      type="button" 
                      className="session-btn" 
                      style={{ padding: '10px', background: 'rgba(255,255,255,0.06)' }}
                      title="Upload Image for Multimodal Vision Search"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <Paperclip size={18} />
                    </button>
                    <input 
                      id="agent-chat-input"
                      className="chat-text-input"
                      placeholder={activeOrderContext 
                        ? `Ask about order #${activeOrderContext.id} (tracking, returns, refund)...`
                        : "Ask ShopBot for laptops, phones, headphones, power banks, chargers..."
                      }
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && !loading && handleSendMessage()}
                    />
                    <button 
                      id="btn-send-message"
                      className="chat-action-btn"
                      disabled={loading || (!inputMessage.trim() && !imagePreview)}
                      onClick={() => handleSendMessage()}
                    >
                      <Send size={15} />
                      Send
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ======================================================== */}
          {/* TAB 2.5: DEDICATED FULL-PAGE MYNTRA-STYLE SHOPPING CART   */}
          {/* ======================================================== */}
          {activeTab === 'cart' && (
            <div className="myntra-cart-layout">
              {/* Left Column: Cart Items List */}
              <div className="myntra-cart-left">
                <div className="myntra-cart-title-row">
                  <div>
                    <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#ffffff' }}>
                      My Shopping Bag ({cart.items?.reduce((acc, i) => acc + i.quantity, 0) || 0} Items)
                    </h2>
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>100% Genuine Electronic Devices Guaranteed</span>
                  </div>
                  <button 
                    className="session-btn"
                    style={{ fontSize: '0.8rem', padding: '6px 14px', background: 'rgba(255,255,255,0.06)' }}
                    onClick={() => setActiveTab('catalog')}
                  >
                    + Add More Items
                  </button>
                </div>

                {(!cart.items || cart.items.length === 0) ? (
                  <div className="myntra-empty-cart-card">
                    <ShoppingBag size={54} color="#6366f1" style={{ opacity: 0.6, margin: '0 auto 12px' }} />
                    <h3 style={{ color: '#ffffff', fontSize: '1.1rem', marginBottom: '6px' }}>Your shopping bag is empty</h3>
                    <p style={{ color: '#94a3b8', fontSize: '0.85rem', maxWidth: '360px', margin: '0 auto 18px' }}>
                      Explore laptops, smartphones, headphones, tablets, power banks, and chargers in our catalog.
                    </p>
                    <button 
                      className="btn-add-cart" 
                      style={{ padding: '10px 22px', fontSize: '0.85rem', margin: '0 auto' }}
                      onClick={() => setActiveTab('catalog')}
                    >
                      Browse Store Catalog
                    </button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {cart.items.map((item) => (
                      <div key={item.id} className="myntra-cart-item-card">
                        <div className="cart-item-thumb-box">
                          <img src={item.image_url} alt={item.name} className="cart-item-thumb-img" />
                        </div>
                        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <div>
                              <span className="product-category-tag" style={{ marginBottom: '4px' }}>{item.category}</span>
                              <h4 style={{ fontSize: '0.96rem', fontWeight: 600, color: '#ffffff' }}>{item.name}</h4>
                            </div>
                            <button 
                              className="btn-cart-item-delete"
                              title="Remove item from bag"
                              onClick={() => handleRemoveCartItem(item.id)}
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px' }}>
                            <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#34d399' }}>
                              ₹{item.price?.toLocaleString()}
                            </span>
                            <span style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
                              Subtotal: ₹{(item.price * item.quantity).toLocaleString()}
                            </span>
                          </div>

                          {/* Quantity Selector & Item Controls */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '8px' }}>
                            <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Quantity:</span>
                            <div className="cart-qty-counter">
                              <button 
                                type="button"
                                className="qty-counter-btn"
                                onClick={() => handleUpdateCartQty(item.id, item.quantity, -1)}
                                title="Decrease quantity"
                              >
                                <Minus size={12} />
                              </button>
                              <span className="qty-counter-num">{item.quantity}</span>
                              <button 
                                type="button"
                                className="qty-counter-btn"
                                onClick={() => handleUpdateCartQty(item.id, item.quantity, 1)}
                                title="Increase quantity"
                              >
                                <Plus size={12} />
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Right Column: Price Details Sidebar (Myntra Style) */}
              {cart.items?.length > 0 && (
                <div className="myntra-price-sidebar">
                  <div className="myntra-price-card">
                    <h3 className="price-card-title">PRICE DETAILS ({cart.items.reduce((acc, i) => acc + i.quantity, 0)} Items)</h3>
                    <div className="price-breakdown">
                      <div className="price-row">
                        <span>Total MRP</span>
                        <span>₹{cart.total?.toLocaleString()}</span>
                      </div>
                      <div className="price-row">
                        <span>Special Discount</span>
                        <span style={{ color: '#34d399' }}>-₹0 (Special Deal)</span>
                      </div>
                      <div className="price-row">
                        <span>Delivery Charges</span>
                        <span style={{ color: '#34d399' }}>FREE</span>
                      </div>
                      <div className="price-divider" />
                      <div className="price-row total-row">
                        <span>Total Amount</span>
                        <span className="total-amount-val">₹{cart.total?.toLocaleString()}</span>
                      </div>
                    </div>

                    <button 
                      id="btn-place-order-page"
                      className="btn-place-order"
                      onClick={handleCheckout}
                    >
                      <Check size={18} />
                      <span>PLACE ORDER</span>
                    </button>

                    <div className="cart-trust-badge">
                      <ShieldCheck size={16} color="#34d399" />
                      <span>Safe & Secure Checkout · 100% Authentic Electronics</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ======================================================== */}
          {/* TAB 3: ADMIN HUMAN HANDOFF QUEUE (ADMIN ALONE)           */}
          {/* ======================================================== */}
          {activeTab === 'admin' && currentUser.role === 'admin' && (
            <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: '20px', height: '100%' }}>
              <div className="telemetry-card" style={{ padding: '16px', overflowY: 'auto' }}>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '12px', display: 'flex', justifyContent: 'space-between' }}>
                  <span>Escalation Incidents</span>
                  <span className="nav-badge-pill">{tickets.length}</span>
                </h3>
                {tickets.length === 0 ? (
                  <p style={{ color: '#64748b', fontSize: '0.8rem', textAlign: 'center', padding: '30px 0' }}>
                    No pending escalations. High refunds or angry sentiment trigger tickets here automatically.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {tickets.map(t => (
                      <div 
                        key={t.ticket_id} 
                        style={{ padding: '12px', background: selectedTicket?.ticket_id === t.ticket_id ? 'rgba(99,102,241,0.2)' : 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', cursor: 'pointer' }}
                        onClick={() => setSelectedTicket(t)}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', marginBottom: '4px' }}>
                          <span style={{ color: '#f43f5e', fontWeight: 700 }}>{t.priority}</span>
                          <span style={{ color: '#94a3b8' }}>{t.sentiment}</span>
                        </div>
                        <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{t.customer_name} ({t.ticket_id})</div>
                        <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '2px' }}>{t.trigger_reason}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="telemetry-card" style={{ padding: '20px' }}>
                {selectedTicket ? (
                  <div>
                    <h3 style={{ fontSize: '1.1rem', marginBottom: '6px' }}>Incident #{selectedTicket.ticket_id}</h3>
                    <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '16px' }}>
                      Customer: <strong>{selectedTicket.customer_name}</strong> • Reason: <strong>{selectedTicket.trigger_reason}</strong>
                    </p>

                    <div style={{ background: 'rgba(0,0,0,0.3)', padding: '14px', borderRadius: '8px', marginBottom: '20px', border: '1px solid rgba(255,255,255,0.06)' }}>
                      <div style={{ fontSize: '0.8rem', color: '#818cf8', fontWeight: 600, marginBottom: '4px' }}>AI Incident Summary</div>
                      <p style={{ fontSize: '0.85rem', color: '#e2e8f0', lineHeight: 1.5 }}>{selectedTicket.summary}</p>
                    </div>

                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '8px' }}>Take Over Chat as Human Agent</div>
                      <textarea 
                        rows={4}
                        className="chat-text-input"
                        style={{ width: '100%', marginBottom: '10px' }}
                        placeholder="Type your response to the customer..."
                        value={humanReply}
                        onChange={(e) => setHumanReply(e.target.value)}
                      />
                      <div style={{ display: 'flex', gap: '10px' }}>
                        <button className="chat-action-btn" onClick={() => handleHumanReply('REPLY')}>
                          Send Human Message
                        </button>
                        <button 
                          className="btn-add-cart" 
                          style={{ background: 'rgba(16,185,129,0.15)', color: '#34d399', borderColor: 'rgba(16,185,129,0.3)' }}
                          onClick={() => handleHumanReply('RESOLVE')}
                        >
                          Resolve & Hand Back to AI
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p style={{ color: '#64748b', textAlign: 'center', margin: 'auto' }}>Select a ticket from the left queue.</p>
                )}
              </div>
            </div>
          )}

          {/* ======================================================== */}
          {/* TAB 4: ORDERS (MYNTRA / MEESHO STYLE WITH ITEM CHAT)     */}
          {/* ======================================================== */}
          {activeTab === 'orders' && (
            <div className="telemetry-card" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '10px' }}>
                <div>
                  <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#ffffff' }}>
                    {currentUser.role === 'admin' ? "Company Order Registry (All Customers)" : "My Orders"}
                  </h3>
                  <p style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
                    {currentUser.role === 'admin'
                      ? "Global database records across all customer accounts for administrative audit & support tracking."
                      : "Select any order below to track delivery progress or get instant support."
                    }
                  </p>
                </div>
                <button 
                  className="session-btn" 
                  onClick={fetchOrders}
                  style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <RefreshCw size={13} />
                  <span>Refresh Orders</span>
                </button>
              </div>

              {orders.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '48px 20px', color: '#64748b' }}>
                  <Package size={48} style={{ margin: '0 auto 14px', opacity: 0.3 }} />
                  <h4 style={{ fontSize: '1.05rem', color: '#cbd5e1', marginBottom: '6px' }}>No orders placed yet</h4>
                  <p style={{ fontSize: '0.82rem', maxWidth: '380px', margin: '0 auto 18px' }}>
                    Browse our 50-item catalog, add items to your cart, and place an order using 1-click checkout!
                  </p>
                  <button 
                    className="btn-add-cart" 
                    onClick={() => setActiveTab('catalog')}
                    style={{ margin: '0 auto' }}
                  >
                    Browse Store Catalog
                  </button>
                </div>
              ) : currentUser.role === 'customer' ? (
                /* ===================================================== */
                /* CUSTOMER VIEW: MYNTRA & MEESHO STYLE ORDER CARDS      */
                /* ===================================================== */
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {orders.map(o => {
                    const firstItem = Array.isArray(o.items) && o.items.length > 0 ? o.items[0] : null;
                    const matchedProduct = firstItem ? products.find(p => p.id === firstItem.product_id) : null;
                    const thumbUrl = matchedProduct?.image_url || "/images/products/LAP-001.jpg";

                    return (
                      <div key={o.id} className="myntra-order-card">
                        {/* Order Header */}
                        <div className="order-card-header">
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ fontWeight: 700, color: '#818cf8', fontSize: '0.92rem' }}>#{o.id}</span>
                            <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Placed on {o.order_date}</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{
                              padding: '3px 10px',
                              borderRadius: '999px',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              background: o.status === 'Delivered' ? 'rgba(52, 211, 153, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                              color: o.status === 'Delivered' ? '#34d399' : '#38bdf8',
                              border: `1px solid ${o.status === 'Delivered' ? 'rgba(52, 211, 153, 0.3)' : 'rgba(56, 189, 248, 0.3)'}`
                            }}>
                              ● {o.status}
                            </span>
                            {o.return_status && o.return_status !== 'None' && (
                              <span style={{ padding: '3px 10px', borderRadius: '999px', fontSize: '0.72rem', fontWeight: 700, background: 'rgba(239,68,68,0.2)', color: '#f87171' }}>
                                Return: {o.return_status}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Order Item Details */}
                        <div className="order-main-content">
                          <img src={thumbUrl} alt="" className="order-product-thumb" />
                          <div className="order-product-details">
                            <h4 className="order-product-title">
                              {firstItem?.name || "Purchased Product"}
                            </h4>
                            <div className="order-product-meta">
                              <span><strong>Qty:</strong> {firstItem?.qty || 1}</span>
                              <span><strong>Total:</strong> <span style={{ color: '#34d399', fontWeight: 700 }}>₹{o.total_amount?.toLocaleString()}</span></span>
                              <span><strong>Carrier:</strong> {o.carrier || "Courier Express"}</span>
                              <span><strong>Tracking:</strong> <code style={{ color: '#818cf8' }}>{o.tracking_number}</code></span>
                            </div>
                          </div>
                        </div>

                        {/* Meesho & Myntra Visual 4-Stage Tracking Stepper */}
                        <OrderTrackingStepper 
                          order={o} 
                          compact={false} 
                          onAdvanceStatus={handleAdvanceOrderStatus} 
                        />

                        {/* Order Card Action Bar (Myntra / Meesho style) */}
                        <div className="order-card-actions">
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#94a3b8' }}>
                            <Truck size={14} color="#34d399" />
                            <span>{o.status === 'Delivered' ? "Delivered to your address" : "In transit via BlueDart Air"}</span>
                          </div>

                          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                            {/* DEDICATED PRODUCT CHAT BUTTON (MYNTRA / MEESHO STYLE) */}
                            <button 
                              className="btn-order-chat"
                              onClick={() => openOrderHelpChat(o)}
                              title="Open dedicated chat support thread for this specific order"
                            >
                              <MessageSquare size={14} />
                              <span>Order Help & Chat Support</span>
                            </button>

                            <button 
                              className="session-btn"
                              style={{ fontSize: '0.75rem', padding: '6px 12px', background: 'rgba(99,102,241,0.15)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.3)' }}
                              onClick={() => openOrderHelpChat(o, `Where is my order ${o.id}?`)}
                            >
                              Track Delivery
                            </button>

                            <button 
                              className="session-btn"
                              style={{ fontSize: '0.75rem', padding: '6px 12px', background: 'rgba(239,68,68,0.12)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.3)' }}
                              onClick={() => openOrderHelpChat(o, `I want to return order ${o.id}`)}
                            >
                              Return / Refund
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                /* ===================================================== */
                /* ADMIN VIEW: GLOBAL DATABASE TABLE ACROSS ALL USERS   */
                /* ===================================================== */
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                    <thead>
                      <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#94a3b8' }}>
                        <th style={{ padding: '10px' }}>Order ID</th>
                        <th style={{ padding: '10px' }}>Customer / Email</th>
                        <th style={{ padding: '10px' }}>Order Date</th>
                        <th style={{ padding: '10px' }}>Items</th>
                        <th style={{ padding: '10px' }}>Status</th>
                        <th style={{ padding: '10px' }}>Amount</th>
                        <th style={{ padding: '10px' }}>Carrier Tracking</th>
                        <th style={{ padding: '10px', textAlign: 'right' }}>Admin Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orders.map(o => (
                        <tr key={o.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                          <td style={{ padding: '10px', color: '#818cf8', fontWeight: 600 }}>{o.id}</td>
                          <td style={{ padding: '10px' }}>
                            <div style={{ color: '#ffffff', fontWeight: 500 }}>{o.customer_name}</div>
                            <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{o.customer_email}</div>
                          </td>
                          <td style={{ padding: '10px', color: '#94a3b8' }}>{o.order_date}</td>
                          <td style={{ padding: '10px' }}>
                            {Array.isArray(o.items) && o.items.length > 0 ? (
                              <div style={{ fontSize: '0.78rem', color: '#cbd5e1' }}>
                                {o.items[0].name} {o.items.length > 1 ? `(+${o.items.length - 1} more)` : ''}
                              </div>
                            ) : (
                              <span style={{ color: '#64748b' }}>Item details</span>
                            )}
                          </td>
                          <td style={{ padding: '10px' }}>
                            <span style={{
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '0.72rem',
                              fontWeight: 600,
                              background: o.status === 'Delivered' ? 'rgba(52, 211, 153, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                              color: o.status === 'Delivered' ? '#34d399' : '#38bdf8'
                            }}>
                              ● {o.status}
                            </span>
                          </td>
                          <td style={{ padding: '10px', fontWeight: 600, color: '#34d399' }}>₹{o.total_amount?.toLocaleString()}</td>
                          <td style={{ padding: '10px', fontFamily: 'monospace', color: '#cbd5e1', fontSize: '0.78rem' }}>
                            <div>{o.tracking_number}</div>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontFamily: 'sans-serif' }}>{o.carrier}</div>
                          </td>
                          <td style={{ padding: '10px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                            <button
                              className="btn-advance-status"
                              style={{ padding: '4px 8px', fontSize: '0.7rem', marginRight: '6px' }}
                              title="Advance to next tracking stage (Placed ➔ Shipped ➔ In Transit ➔ Delivered)"
                              onClick={() => handleAdvanceOrderStatus(o.id)}
                            >
                              <RefreshCw size={11} />
                              <span>Advance Stage</span>
                            </button>
                            <button
                              className="btn-order-chat"
                              style={{ padding: '4px 10px', fontSize: '0.72rem' }}
                              onClick={() => openOrderHelpChat(o)}
                            >
                              <MessageSquare size={12} />
                              <span>Inspect Chat</span>
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </main>
      </div>

      {/* API Key Modal */}
      {showKeyModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '1.1rem' }}>Groq API Configuration</h3>
              <button onClick={() => setShowKeyModal(false)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '14px' }}>
              Using high-speed <strong>LPU Hardware Acceleration</strong> with <strong>openai/gpt-oss-120b</strong> on Groq.
            </p>
            <input 
              type="password"
              className="chat-text-input" 
              style={{ width: '100%', marginBottom: '14px', fontFamily: 'monospace' }}
              placeholder="gsk_..."
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
            />
            <button className="chat-action-btn" style={{ width: '100%', justifyContent: 'center' }} onClick={handleSaveApiKey}>
              Save & Test Connection
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
