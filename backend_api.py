from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'ecommerce.db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DATABASE_PATH}'
app.config['SECRET_KEY'] = 'your-secret-key-here'

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    cart_items = db.relationship('CartItem', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    rentprice = db.Column(db.Float)
    size = db.Column(db.String(50))
    image = db.Column(db.String(255))
    rating_rate = db.Column(db.Float)
    rating_count = db.Column(db.Integer)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.String(100), db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product')

# Authentication Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    user = User(username=data['username'], email=data['email'])
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    
    if user and user.check_password(data['password']):
        return jsonify({
            'message': 'Login successful',
            'user_id': user.id,
            'username': user.username
        })
    
    return jsonify({'error': 'Invalid username or password'}), 401

# Cart Routes
@app.route('/api/cart', methods=['GET'])
def get_cart():
    user_id = request.args.get('user_id')
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    
    # Fetch all products from external API
    url = 'http://shopa.beauty:5000/freelancer/products'
    response = requests.get(url)
    
    if response.status_code != 200:
        return jsonify({'error': 'Failed to fetch products'}), 500
    
    products = {p['_id']: p for p in response.json()}
    
    items = []
    for item in cart_items:
        # Get product details from external API data
        product = products.get(item.product_id)
        if product:
            items.append({
                'id': item.id,
                'product': {
                    'id': item.product_id,
                    'title': product['title'],
                    'price': product['price'],
                    'image': product['image']
                },
                'quantity': item.quantity,
                'added_at': item.added_at.isoformat()
            })
    
    return jsonify({'cart_items': items})

@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    user_id = data['user_id']
    product_id = data['product_id']
    quantity = data.get('quantity', 1)
    
    # Verify product exists in external API
    url = f'http://shopa.beauty:5000/freelancer/products'
    response = requests.get(url)
    
    if response.status_code != 200:
        return jsonify({'error': 'Failed to fetch products'}), 500
    
    products = response.json()
    product_exists = any(p['_id'] == product_id for p in products)
    
    if not product_exists:
        return jsonify({'error': 'Product not found'}), 404
    
    existing_item = CartItem.query.filter_by(
        user_id=user_id,
        product_id=product_id
    ).first()
    
    if existing_item:
        existing_item.quantity += quantity
    else:
        cart_item = CartItem(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(cart_item)
    
    db.session.commit()
    return jsonify({'message': 'Item added to cart successfully'})

@app.route('/api/cart/update', methods=['PUT'])
def update_cart_item():
    data = request.get_json()
    cart_item = CartItem.query.get(data['cart_item_id'])
    
    if not cart_item:
        return jsonify({'error': 'Cart item not found'}), 404
    
    cart_item.quantity = data['quantity']
    db.session.commit()
    
    return jsonify({'message': 'Cart item updated successfully'})

@app.route('/api/cart/remove', methods=['DELETE'])
def remove_from_cart():
    cart_item_id = request.args.get('cart_item_id')
    cart_item = CartItem.query.get(cart_item_id)
    
    if not cart_item:
        return jsonify({'error': 'Cart item not found'}), 404
    
    db.session.delete(cart_item)
    db.session.commit()
    
    return jsonify({'message': 'Item removed from cart successfully'})

# Product Routes
@app.route('/products', methods=['GET'])
def get_products():
    search = request.args.get('search')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 5))
    
    try:
        # Fetch products directly from external API
        url = 'http://shopa.beauty:5000/freelancer/products'
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        all_products = response.json()
        
        # Wrap the products in a 'products' object
        return jsonify({'products': all_products})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Failed to fetch products', 'details': str(e)}), 500
    except ValueError as e:
        return jsonify({'error': 'Invalid JSON response from external API', 'details': str(e)}), 500
    
    # Filter products if search parameter is provided
    if search:
        all_products = [p for p in all_products if search.lower() in p['title'].lower()]
    
    # Calculate pagination
    total = len(all_products)
    pages = (total + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total)
    
    # Get products for current page
    paged_products = all_products[start_idx:end_idx]
    
    # Format products for response
    result = [{
        'id': product['_id'],
        'title': product['title'],
        'category': product['category'],
        'description': product['description'],
        'price': product['price'],
        'rentprice': product['rentprice'],
        'size': product['size'],
        'image': product['image'],
        'rating': {
            'rate': product['rating']['rate'],
            'count': product['rating']['count']
        }
    } for product in paged_products]

    return jsonify({
        'products': result,
        'total': total,
        'pages': pages,
        'current_page': page
    })

# Fetch Products from External API (kept for reference but not used anymore)
@app.route('/fetch-products', methods=['GET'])
def fetch_products():
    url = 'http://shopa.beauty:5000/freelancer/products'
    response = requests.get(url)
    if response.status_code != 200:
        return jsonify({'error': 'Failed to fetch products'}), 500
    
    products = response.json()
    return jsonify({'message': 'Products fetched successfully', 'count': len(products)}), 200

# Order model for checkout process
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')
    shipping_address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.String(100), nullable=False)
    product_title = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1)

# Checkout and Order Routes
@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.get_json()
    user_id = data['user_id']
    shipping_info = data['shipping_info']
    
    # Get cart items
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400
    
    # Fetch products from external API
    url = 'http://shopa.beauty:5000/freelancer/products'
    response = requests.get(url)
    
    if response.status_code != 200:
        return jsonify({'error': 'Failed to fetch products'}), 500
    
    products = {p['_id']: p for p in response.json()}
    
    # Calculate order total
    subtotal = 0
    order_items = []
    
    for item in cart_items:
        product = products.get(item.product_id)
        if not product:
            continue
            
        item_total = product['price'] * item.quantity
        subtotal += item_total
        
        order_items.append({
            'product_id': item.product_id,
            'product_title': product['title'],
            'price': item_total,
            'quantity': item.quantity
        })
    
    # Add shipping and tax
    shipping = 5.0
    tax = subtotal * 0.1
    total = subtotal + shipping + tax
    
    # Create order
    shipping_address = f"{shipping_info['address']}, {shipping_info['city']}, {shipping_info['state']} {shipping_info['zip']}"
    
    order = Order(
        user_id=user_id,
        total=total,
        shipping_address=shipping_address
    )
    
    db.session.add(order)
    db.session.flush()
    
    # Add order items
    for item_data in order_items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item_data['product_id'],
            product_title=item_data['product_title'],
            price=item_data['price'],
            quantity=item_data['quantity']
        )
        db.session.add(order_item)
    
    # Clear cart
    for item in cart_items:
        db.session.delete(item)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Order placed successfully',
        'order_id': order.id,
        'total': total
    })

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    order_items = [{
        'id': item.id,
        'product_id': item.product_id,
        'product_title': item.product_title,
        'price': item.price,
        'quantity': item.quantity
    } for item in order.items]
    
    return jsonify({
        'id': order.id,
        'user_id': order.user_id,
        'total': order.total,
        'status': order.status,
        'shipping_address': order.shipping_address,
        'created_at': order.created_at.isoformat(),
        'items': order_items
    })

# Create database
def create_database():
    if not os.path.exists(DATABASE_PATH):
        with app.app_context():
            db.create_all()
            print('Database created successfully.')

if __name__ == '__main__':
    create_database()
    app.run(port=5001, debug=True)