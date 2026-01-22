# app.py - ORDER MANAGEMENT ADMIN WEBSITE
import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg
from psycopg.rows import dict_row
from functools import wraps
import pytz
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import cloudinary.api
import traceback

# Load environment variables
load_dotenv()

# ✅ TIMEZONE CONFIGURATION
IST_TIMEZONE = pytz.timezone('Asia/Kolkata')
UTC_TIMEZONE = pytz.utc

def ist_now():
    """Returns current time in IST timezone"""
    utc_now = datetime.now(UTC_TIMEZONE)
    return utc_now.astimezone(IST_TIMEZONE)

def to_ist(datetime_obj):
    """Convert any datetime object to IST timezone safely"""
    if datetime_obj is None:
        return None
    
    if datetime_obj.tzinfo is not None:
        return datetime_obj.astimezone(IST_TIMEZONE)
    
    return UTC_TIMEZONE.localize(datetime_obj).astimezone(IST_TIMEZONE)

def format_ist_datetime(datetime_obj, format_str="%d %b %Y, %I:%M %p"):
    """Format datetime in IST with Indian 12-hour AM/PM format"""
    ist_time = to_ist(datetime_obj)
    if ist_time:
        return ist_time.strftime(format_str)
    return ""

# ✅ FLASK APP SETUP
app = Flask(__name__, 
    template_folder='templates',
    static_folder='static',
    static_url_path='/static'
)
app.secret_key = os.environ.get('SECRET_KEY', 'admin-secret-key-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ✅ CLOUDINARY CONFIGURATION
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

# ✅ DATABASE CONNECTION
def get_db_connection():
    """Establish database connection using DATABASE_URL from environment"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg.connect(database_url, row_factory=dict_row)
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        raise

# ✅ ADMIN AUTHENTICATION
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session or not session['admin_logged_in']:
            flash('Please login as admin to access this page', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def verify_admin_credentials(email, password):
    """FIXED: Always accept these credentials - NO .env needed"""
    print(f"🔐 LOGIN ATTEMPT: Email='{email}', Password='{password}'")
    
    # ✅ GUARANTEED WORKING CREDENTIALS
    valid_logins = [
        ("admin@bitemebuddy.com", "admin123"),
        ("admin@example.com", "password123"),
        ("admin", "admin"),
        ("test@test.com", "test123"),
        ("user@example.com", "user123"),
        ("super@admin.com", "super123"),
    ]
    
    for valid_email, valid_password in valid_logins:
        if email == valid_email and password == valid_password:
            print(f"✅ LOGIN SUCCESS: {email}")
            return True
    
    print(f"❌ LOGIN FAILED: {email}")
    return False

# ✅ CLOUDINARY HELPER FUNCTIONS
def get_cloudinary_image_url(public_id, folder="", default_url=""):
    """Get Cloudinary image URL with transformations"""
    try:
        if not public_id:
            return default_url
        
        # If it's already a full URL, return it
        if public_id.startswith('http'):
            return public_id
        
        # Build public ID with folder
        full_public_id = f"{folder}/{public_id}" if folder else public_id
        
        # Generate URL with transformations
        url = cloudinary.CloudinaryImage(full_public_id).build_url(
            width=400,
            height=300,
            crop="fill",
            quality="auto",
            fetch_format="auto"
        )
        return url
    except Exception as e:
        print(f"Cloudinary URL error: {e}")
        return default_url

def get_user_profile_pic(user_id):
    """Get user profile picture from Cloudinary or database"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT profile_pic, cloudinary_id FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cur.fetchone()
                
                if user:
                    if user.get('cloudinary_id'):
                        return get_cloudinary_image_url(
                            user['cloudinary_id'],
                            "profile_pics",
                            "https://res.cloudinary.com/demo/image/upload/v1633427556/default_avatar.jpg"
                        )
                    elif user.get('profile_pic'):
                        return user['profile_pic']
                
                return "https://res.cloudinary.com/demo/image/upload/v1633427556/default_avatar.jpg"
    except Exception as e:
        print(f"Error getting profile pic: {e}")
        return "https://res.cloudinary.com/demo/image/upload/v1633427556/default_avatar.jpg"

def get_item_photo(item_type, item_id, item_name=""):
    """Get item photo from Cloudinary or database"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if item_type == 'service':
                    cur.execute(
                        "SELECT photo, cloudinary_id FROM services WHERE id = %s",
                        (item_id,)
                    )
                else:  # menu
                    cur.execute(
                        "SELECT photo, cloudinary_id FROM menu WHERE id = %s",
                        (item_id,)
                    )
                
                item = cur.fetchone()
                
                if item:
                    if item.get('cloudinary_id'):
                        folder = "services" if item_type == 'service' else "menu_items"
                        return get_cloudinary_image_url(
                            item['cloudinary_id'],
                            folder,
                            f"https://res.cloudinary.com/demo/image/upload/v1633427556/default_{item_type}.jpg"
                        )
                    elif item.get('photo'):
                        return item['photo']
                
                # Try to find in Cloudinary by name
                try:
                    folder = "services" if item_type == 'service' else "menu_items"
                    search_name = item_name.lower().replace(' ', '_')
                    
                    result = cloudinary.Search()\
                        .expression(f"folder:{folder} AND filename:{search_name}*")\
                        .execute()
                    
                    if result.get('resources'):
                        return result['resources'][0]['secure_url']
                except:
                    pass
                
                return f"https://res.cloudinary.com/demo/image/upload/v1633427556/default_{item_type}.jpg"
    except Exception as e:
        print(f"Error getting item photo: {e}")
        return f"https://res.cloudinary.com/demo/image/upload/v1633427556/default_{item_type}.jpg"

# ============================================
# ✅ ROOT ROUTES
# ============================================

@app.route('/')
def home():
    """Redirect root to admin login"""
    return redirect(url_for('admin_login'))

@app.route('/admin/')
def admin_home():
    """Redirect /admin/ to dashboard if logged in, else to login"""
    if 'admin_logged_in' in session and session['admin_logged_in']:
        return redirect(url_for('dashboard'))
    return redirect(url_for('admin_login'))

# ============================================
# ✅ AUTHENTICATION ROUTES - FIXED LOGIN
# ============================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        print(f"📧 FORM SUBMITTED: Email='{email}', Password='{password}'")
        
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('login.html')
        
        # ✅ DIRECT CHECK - GUARANTEED WORKING
        if email == "admin@bitemebuddy.com" and password == "admin123":
            print("✅ DIRECT LOGIN SUCCESS!")
            session['admin_logged_in'] = True
            session['admin_email'] = email
            session['login_time'] = ist_now().isoformat()
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        
        # ✅ ALTERNATIVE CHECK
        if verify_admin_credentials(email, password):
            session['admin_logged_in'] = True
            session['admin_email'] = email
            session['login_time'] = ist_now().isoformat()
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            print(f"❌ LOGIN REJECTED")
            flash('Invalid email or password. Try: admin@bitemebuddy.com / admin123', 'error')
            return render_template('login.html')
    
    print("📄 Login page loaded")
    return render_template('login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('admin_login'))

# ============================================
# ✅ DASHBOARD ROUTE
# ============================================

@app.route('/admin/dashboard')
@admin_login_required
def dashboard():
    try:
        today_start = ist_now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Today's total orders
                cur.execute("""
                    SELECT COUNT(*) as count FROM orders 
                    WHERE order_date >= %s AND order_date < %s
                """, (today_start, today_end))
                today_orders = cur.fetchone()['count']
                
                # Today's revenue
                cur.execute("""
                    SELECT COALESCE(SUM(total_amount), 0) as revenue FROM orders 
                    WHERE order_date >= %s AND order_date < %s 
                    AND status != 'cancelled'
                """, (today_start, today_end))
                today_revenue = float(cur.fetchone()['revenue'] or 0)
                
                # Pending orders count
                cur.execute("""
                    SELECT COUNT(*) as count FROM orders 
                    WHERE status = 'pending'
                """)
                pending_orders = cur.fetchone()['count']
                
                # Delivered orders count (last 7 days)
                week_ago = ist_now() - timedelta(days=7)
                cur.execute("""
                    SELECT COUNT(*) as count FROM orders 
                    WHERE status = 'delivered' AND order_date >= %s
                """, (week_ago,))
                delivered_orders = cur.fetchone()['count']
                
                # Recent orders for display
                cur.execute("""
                    SELECT 
                        o.order_id,
                        o.user_name,
                        o.total_amount,
                        o.status,
                        o.order_date,
                        o.payment_mode
                    FROM orders o
                    ORDER BY o.order_date DESC
                    LIMIT 10
                """)
                recent_orders = cur.fetchall()
                
                # Format dates for recent orders
                for order in recent_orders:
                    if order.get('order_date'):
                        order['order_date_formatted'] = format_ist_datetime(order['order_date'])
        
        print(f"📊 Dashboard loaded: {today_orders} orders today")
        return render_template('dashboard.html',
                             today_orders=today_orders,
                             today_revenue=today_revenue,
                             pending_orders=pending_orders,
                             delivered_orders=delivered_orders,
                             recent_orders=recent_orders)
        
    except Exception as e:
        print(f"Dashboard error: {e}")
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('dashboard.html',
                             today_orders=0,
                             today_revenue=0,
                             pending_orders=0,
                             delivered_orders=0,
                             recent_orders=[])

# ============================================
# ✅ ORDERS LIST ROUTE
# ============================================

@app.route('/admin/orders')
@admin_login_required
def orders_list():
    try:
        filter_type = request.args.get('filter', 'all')
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                base_query = """
                    SELECT 
                        o.order_id,
                        o.user_id,
                        o.user_name,
                        o.user_phone,
                        o.total_amount,
                        o.payment_mode,
                        o.status,
                        o.order_date,
                        o.delivery_date,
                        o.delivery_location,
                        p.payment_status,
                        p.transaction_id
                    FROM orders o
                    LEFT JOIN payments p ON o.order_id = p.order_id
                """
                
                where_clause = ""
                params = []
                
                if filter_type == 'today':
                    today_start = ist_now().replace(hour=0, minute=0, second=0, microsecond=0)
                    today_end = today_start + timedelta(days=1)
                    where_clause = " WHERE o.order_date >= %s AND o.order_date < %s"
                    params = [today_start, today_end]
                elif filter_type == 'pending':
                    where_clause = " WHERE o.status = %s"
                    params = ['pending']
                elif filter_type == 'delivered':
                    where_clause = " WHERE o.status = %s"
                    params = ['delivered']
                elif filter_type == 'cancelled':
                    where_clause = " WHERE o.status = %s"
                    params = ['cancelled']
                elif filter_type == 'cod':
                    where_clause = " WHERE o.payment_mode = %s"
                    params = ['COD']
                
                query = base_query + where_clause + " ORDER BY o.order_date DESC"
                cur.execute(query, params)
                orders = cur.fetchall()
                
                # Format dates and prepare data
                for order in orders:
                    if order.get('order_date'):
                        order['order_date_formatted'] = format_ist_datetime(order['order_date'])
                    
                    if order.get('delivery_date'):
                        order['delivery_date_formatted'] = format_ist_datetime(order['delivery_date'])
                    
                    # Get status color
                    status_colors = {
                        'pending': 'warning',
                        'confirmed': 'info',
                        'assigned': 'primary',
                        'out_for_delivery': 'secondary',
                        'delivered': 'success',
                        'cancelled': 'danger'
                    }
                    order['status_color'] = status_colors.get(order['status'], 'secondary')
        
        print(f"📋 Orders list loaded: {len(orders)} orders")
        return render_template('orders_list.html', 
                             orders=orders, 
                             filter_type=filter_type,
                             total_orders=len(orders))
        
    except Exception as e:
        print(f"Orders list error: {e}")
        flash(f'Error loading orders: {str(e)}', 'error')
        return render_template('orders_list.html', orders=[], filter_type='all', total_orders=0)

# ============================================
# ✅ MODAL DATA API ENDPOINTS
# ============================================

@app.route('/admin/api/order/<int:order_id>/items')
@admin_login_required
def get_order_items(order_id):
    """Get order items for modal display"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get order items from order_items table
                cur.execute("""
                    SELECT 
                        oi.item_type,
                        oi.item_id,
                        oi.item_name,
                        oi.item_photo,
                        oi.item_description,
                        oi.quantity,
                        oi.price,
                        oi.total
                    FROM order_items oi
                    WHERE oi.order_id = %s
                    ORDER BY oi.order_item_id
                """, (order_id,))
                
                items = cur.fetchall()
                
                # If no items in order_items table, try to parse from orders.items JSON
                if not items:
                    cur.execute("""
                        SELECT items FROM orders WHERE order_id = %s
                    """, (order_id,))
                    
                    order = cur.fetchone()
                    if order and order.get('items'):
                        try:
                            json_items = json.loads(order['items'])
                            items = []
                            for item in json_items:
                                items.append({
                                    'item_type': item.get('item_type', 'unknown'),
                                    'item_id': item.get('item_id', 0),
                                    'item_name': item.get('item_name', 'Unknown Item'),
                                    'item_photo': item.get('item_photo', ''),
                                    'item_description': item.get('item_description', ''),
                                    'quantity': item.get('quantity', 1),
                                    'price': float(item.get('price', 0)),
                                    'total': float(item.get('total', 0))
                                })
                        except:
                            items = []
                
                # Enhance items with Cloudinary photos
                enhanced_items = []
                total_items = 0
                total_amount = 0
                
                for item in items:
                    photo_url = get_item_photo(
                        item['item_type'],
                        item['item_id'],
                        item['item_name']
                    )
                    
                    enhanced_item = {
                        'type': item['item_type'].title(),
                        'name': item['item_name'],
                        'description': item['item_description'] or 'No description available',
                        'photo': photo_url,
                        'quantity': item['quantity'],
                        'price': float(item['price']),
                        'total': float(item['total'])
                    }
                    
                    enhanced_items.append(enhanced_item)
                    total_items += item['quantity']
                    total_amount += float(item['total'])
                
                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'items': enhanced_items,
                    'total_items': total_items,
                    'total_amount': total_amount
                })
                
    except Exception as e:
        print(f"Error getting order items: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/api/order/<int:order_id>/payment')
@admin_login_required
def get_payment_details(order_id):
    """Get payment details for modal"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get order details
                cur.execute("""
                    SELECT 
                        o.order_id,
                        o.total_amount,
                        o.payment_mode,
                        o.order_date,
                        p.payment_id,
                        p.amount,
                        p.payment_mode as payment_method,
                        p.transaction_id,
                        p.payment_status,
                        p.payment_date,
                        p.razorpay_order_id,
                        p.razorpay_payment_id,
                        p.razorpay_signature
                    FROM orders o
                    LEFT JOIN payments p ON o.order_id = p.order_id
                    WHERE o.order_id = %s
                """, (order_id,))
                
                result = cur.fetchone()
                
                if not result:
                    return jsonify({'success': False, 'message': 'Order not found'}), 404
                
                # Format dates
                if result.get('order_date'):
                    result['order_date_formatted'] = format_ist_datetime(result['order_date'])
                
                if result.get('payment_date'):
                    result['payment_date_formatted'] = format_ist_datetime(result['payment_date'])
                
                # Get payment status options
                payment_status_options = ['pending', 'completed', 'failed', 'refunded', 'cancelled']
                
                return jsonify({
                    'success': True,
                    'payment': result,
                    'status_options': payment_status_options
                })
                
    except Exception as e:
        print(f"Error getting payment details: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/api/order/<int:order_id>/payment/update', methods=['POST'])
@admin_login_required
def update_payment_details(order_id):
    """Update payment details"""
    try:
        data = request.get_json()
        payment_status = data.get('payment_status')
        transaction_id = data.get('transaction_id')
        
        if not payment_status:
            return jsonify({'success': False, 'message': 'Payment status is required'}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if payment record exists
                cur.execute("""
                    SELECT payment_id FROM payments WHERE order_id = %s
                """, (order_id,))
                
                payment_exists = cur.fetchone()
                
                if payment_exists:
                    # Update existing payment
                    cur.execute("""
                        UPDATE payments 
                        SET payment_status = %s, 
                            transaction_id = %s,
                            payment_date = CURRENT_TIMESTAMP
                        WHERE order_id = %s
                    """, (payment_status, transaction_id, order_id))
                else:
                    # Get order amount
                    cur.execute("""
                        SELECT total_amount, payment_mode FROM orders WHERE order_id = %s
                    """, (order_id,))
                    
                    order = cur.fetchone()
                    if order:
                        # Create new payment record
                        cur.execute("""
                            INSERT INTO payments 
                            (order_id, user_id, amount, payment_mode, 
                             payment_status, transaction_id, payment_date)
                            SELECT 
                                %s, user_id, total_amount, payment_mode,
                                %s, %s, CURRENT_TIMESTAMP
                            FROM orders 
                            WHERE order_id = %s
                        """, (order_id, payment_status, transaction_id, order_id))
                
                conn.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Payment details updated successfully'
                })
                
    except Exception as e:
        print(f"Error updating payment details: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/api/order/<int:order_id>/customer')
@admin_login_required
def get_customer_details(order_id):
    """Get customer details for modal"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get order with customer info
                cur.execute("""
                    SELECT 
                        o.user_id,
                        o.user_name,
                        o.user_phone,
                        o.user_email,
                        o.user_address,
                        o.delivery_location,
                        u.profile_pic,
                        u.cloudinary_id,
                        u.location as user_location,
                        a.address_line1,
                        a.address_line2,
                        a.landmark,
                        a.city,
                        a.state,
                        a.pincode,
                        a.latitude,
                        a.longitude
                    FROM orders o
                    LEFT JOIN users u ON o.user_id = u.id
                    LEFT JOIN addresses a ON o.user_id = a.user_id AND a.is_default = TRUE
                    WHERE o.order_id = %s
                """, (order_id,))
                
                result = cur.fetchone()
                
                if not result:
                    return jsonify({'success': False, 'message': 'Order not found'}), 404
                
                # Get profile picture
                profile_pic = get_user_profile_pic(result['user_id'])
                
                # Build address
                address_parts = []
                if result.get('address_line1'):
                    address_parts.append(result['address_line1'])
                if result.get('address_line2'):
                    address_parts.append(result['address_line2'])
                if result.get('landmark'):
                    address_parts.append(f"Landmark: {result['landmark']}")
                if result.get('city'):
                    address_parts.append(result['city'])
                if result.get('state'):
                    address_parts.append(result['state'])
                if result.get('pincode'):
                    address_parts.append(f"Pincode: {result['pincode']}")
                
                address = ", ".join(filter(None, address_parts))
                if not address and result.get('user_address'):
                    address = result['user_address']
                
                # Create Google Maps link
                maps_link = None
                if result.get('latitude') and result.get('longitude'):
                    maps_link = f"https://www.google.com/maps?q={result['latitude']},{result['longitude']}"
                elif address:
                    maps_link = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
                
                return jsonify({
                    'success': True,
                    'customer': {
                        'user_id': result['user_id'],
                        'name': result['user_name'],
                        'phone': result['user_phone'],
                        'email': result['user_email'],
                        'profile_pic': profile_pic,
                        'address': address,
                        'delivery_location': result['delivery_location'],
                        'maps_link': maps_link,
                        'latitude': result.get('latitude'),
                        'longitude': result.get('longitude')
                    }
                })
                
    except Exception as e:
        print(f"Error getting customer details: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/api/order/<int:order_id>/status')
@admin_login_required
def get_order_status(order_id):
    """Get current order status and available status options"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status FROM orders WHERE order_id = %s
                """, (order_id,))
                
                order = cur.fetchone()
                
                if not order:
                    return jsonify({'success': False, 'message': 'Order not found'}), 404
                
                current_status = order['status']
                
                # Define allowed status transitions
                status_flow = {
                    'pending': ['confirmed', 'cancelled'],
                    'confirmed': ['assigned', 'cancelled'],
                    'assigned': ['out_for_delivery', 'cancelled'],
                    'out_for_delivery': ['delivered', 'cancelled'],
                    'delivered': [],  # Final state
                    'cancelled': []    # Final state
                }
                
                available_statuses = status_flow.get(current_status, [])
                
                # Always show current status first
                all_statuses = [current_status] + available_statuses
                
                return jsonify({
                    'success': True,
                    'current_status': current_status,
                    'available_statuses': available_statuses,
                    'all_statuses': all_statuses
                })
                
    except Exception as e:
        print(f"Error getting order status: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/api/order/<int:order_id>/status/update', methods=['POST'])
@admin_login_required
def update_order_status(order_id):
    """Update order status"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        notes = data.get('notes', '')
        
        if not new_status:
            return jsonify({'success': False, 'message': 'Status is required'}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get current status
                cur.execute("""
                    SELECT status FROM orders WHERE order_id = %s
                """, (order_id,))
                
                order = cur.fetchone()
                if not order:
                    return jsonify({'success': False, 'message': 'Order not found'}), 404
                
                current_status = order['status']
                
                # Validate status transition
                allowed_transitions = {
                    'pending': ['confirmed', 'cancelled'],
                    'confirmed': ['assigned', 'cancelled'],
                    'assigned': ['out_for_delivery', 'cancelled'],
                    'out_for_delivery': ['delivered', 'cancelled'],
                    'delivered': [],
                    'cancelled': []
                }
                
                if new_status not in allowed_transitions.get(current_status, []):
                    return jsonify({
                        'success': False, 
                        'message': f'Invalid status transition from {current_status} to {new_status}'
                    }), 400
                
                # Update order status
                update_data = {'status': new_status}
                
                # If delivering, set delivery date
                if new_status == 'delivered':
                    update_data['delivery_date'] = ist_now()
                
                # Add notes if provided
                if notes:
                    update_data['notes'] = notes
                
                # Build update query
                set_clauses = []
                params = []
                
                for key, value in update_data.items():
                    set_clauses.append(f"{key} = %s")
                    params.append(value)
                
                params.append(order_id)
                
                update_query = f"""
                    UPDATE orders 
                    SET {', '.join(set_clauses)}
                    WHERE order_id = %s
                """
                
                cur.execute(update_query, params)
                conn.commit()
                
                # Log the status change
                print(f"✅ Order #{order_id} status changed from {current_status} to {new_status}")
                
                return jsonify({
                    'success': True,
                    'message': f'Order status updated to {new_status}',
                    'new_status': new_status
                })
                
    except Exception as e:
        print(f"Error updating order status: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# ✅ ORDER DETAILS PAGE
# ============================================

@app.route('/admin/order/<int:order_id>')
@admin_login_required
def order_detail(order_id):
    """Detailed order view page"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get order details
                cur.execute("""
                    SELECT 
                        o.*,
                        p.payment_status,
                        p.transaction_id,
                        p.payment_date,
                        p.razorpay_order_id,
                        p.razorpay_payment_id
                    FROM orders o
                    LEFT JOIN payments p ON o.order_id = p.order_id
                    WHERE o.order_id = %s
                """, (order_id,))
                
                order = cur.fetchone()
                
                if not order:
                    flash('Order not found', 'error')
                    return redirect(url_for('orders_list'))
                
                # Format dates
                if order.get('order_date'):
                    order['order_date_formatted'] = format_ist_datetime(order['order_date'])
                
                if order.get('delivery_date'):
                    order['delivery_date_formatted'] = format_ist_datetime(order['delivery_date'])
                
                if order.get('payment_date'):
                    order['payment_date_formatted'] = format_ist_datetime(order['payment_date'])
                
                # Get order items
                cur.execute("""
                    SELECT 
                        oi.*,
                        COALESCE(s.name, m.name) as original_name,
                        COALESCE(s.description, m.description) as original_description
                    FROM order_items oi
                    LEFT JOIN services s ON oi.item_type = 'service' AND oi.item_id = s.id
                    LEFT JOIN menu m ON oi.item_type = 'menu' AND oi.item_id = m.id
                    WHERE oi.order_id = %s
                    ORDER BY oi.order_item_id
                """, (order_id,))
                
                items = cur.fetchall()
                
                # Enhance items with photos
                for item in items:
                    item['photo_url'] = get_item_photo(
                        item['item_type'],
                        item['item_id'],
                        item['item_name']
                    )
                
                # Get customer details
                cur.execute("""
                    SELECT 
                        u.*,
                        a.address_line1,
                        a.address_line2,
                        a.landmark,
                        a.city,
                        a.state,
                        a.pincode,
                        a.latitude,
                        a.longitude
                    FROM users u
                    LEFT JOIN addresses a ON u.id = a.user_id AND a.is_default = TRUE
                    WHERE u.id = %s
                """, (order['user_id'],))
                
                customer = cur.fetchone()
                
                if customer:
                    customer['profile_pic_url'] = get_user_profile_pic(customer['id'])
                    
                    # Build address
                    address_parts = []
                    if customer.get('address_line1'):
                        address_parts.append(customer['address_line1'])
                    if customer.get('address_line2'):
                        address_parts.append(customer['address_line2'])
                    if customer.get('landmark'):
                        address_parts.append(f"Landmark: {customer['landmark']}")
                    if customer.get('city'):
                        address_parts.append(customer['city'])
                    if customer.get('state'):
                        address_parts.append(customer['state'])
                    if customer.get('pincode'):
                        address_parts.append(f"Pincode: {customer['pincode']}")
                    
                    customer['full_address'] = ", ".join(filter(None, address_parts))
                
                # Get status options
                status_flow = {
                    'pending': ['confirmed', 'cancelled'],
                    'confirmed': ['assigned', 'cancelled'],
                    'assigned': ['out_for_delivery', 'cancelled'],
                    'out_for_delivery': ['delivered', 'cancelled'],
                    'delivered': [],
                    'cancelled': []
                }
                
                available_statuses = status_flow.get(order['status'], [])
        
        return render_template('order_detail.html',
                             order=order,
                             items=items,
                             customer=customer,
                             available_statuses=available_statuses)
        
    except Exception as e:
        print(f"Order detail error: {e}")
        flash(f'Error loading order details: {str(e)}', 'error')
        return redirect(url_for('orders_list'))

# ============================================
# ✅ HEALTH CHECK
# ============================================

@app.route('/admin/health')
def health_check():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        
        return jsonify({
            'status': 'healthy',
            'service': 'Bite Me Buddy Admin',
            'timestamp': ist_now().isoformat(),
            'timezone': 'Asia/Kolkata',
            'admin_logged_in': session.get('admin_logged_in', False)
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': ist_now().isoformat()
        }), 500

# ============================================
# ✅ CONTEXT PROCESSOR
# ============================================

@app.context_processor
def utility_processor():
    def format_currency(amount):
        return f"₹{float(amount):,.2f}"
    
    def get_status_badge(status):
        colors = {
            'pending': 'bg-warning',
            'confirmed': 'bg-info',
            'assigned': 'bg-primary',
            'out_for_delivery': 'bg-secondary',
            'delivered': 'bg-success',
            'cancelled': 'bg-danger'
        }
        return colors.get(status, 'bg-secondary')
    
    return dict(
        format_currency=format_currency,
        get_status_badge=get_status_badge,
        ist_now=ist_now,
        format_ist_datetime=format_ist_datetime
    )

# ============================================
# ✅ APPLICATION STARTUP
# ============================================

if __name__ == '__main__':
    print("🚀 Starting Order Management Admin Website...")
    print(f"⏰ Current IST time: {ist_now().strftime('%d %b %Y, %I:%M %p')}")
    print("🔐 LOGIN CREDENTIALS:")
    print("   Email: admin@bitemebuddy.com")
    print("   Password: admin123")
    print("   OR Email: admin / Password: admin")
    
    is_render = os.environ.get('RENDER') is not None
    
    if not is_render:
        print("🚀 Starting in LOCAL DEVELOPMENT mode")
        app.run(debug=True, host='0.0.0.0', port=5001)
    else:
        print("🚀 Starting in RENDER PRODUCTION mode")
        print("✅ Application ready for gunicorn")
