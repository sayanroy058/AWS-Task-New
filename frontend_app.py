from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Backend API URL
API_URL = 'http://localhost:5001/api'

# Routes
@app.route('/')
def home():
    # Fetch products from backend API
    response = requests.get('http://localhost:5001/products')
    products = response.json().get('products', [])
    
    # Fetch exchange rates from the API
    exchange_response = requests.get('https://v6.exchangerate-api.com/v6/919bb0c364d3ce45f2fc9bda/latest/USD')
    exchange_data = exchange_response.json()
    conversion_rates = exchange_data.get('conversion_rates', {})
    
    return render_template('home.html', products=products, conversion_rates=conversion_rates)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = {
            'username': request.form['username'],
            'password': request.form['password']
        }
        response = requests.post(f'{API_URL}/login', json=data)
        
        if response.status_code == 200:
            user_data = response.json()
            session['user_id'] = user_data['user_id']
            session['username'] = user_data['username']
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = {
            'username': request.form['username'],
            'email': request.form['email'],
            'password': request.form['password']
        }
        response = requests.post(f'{API_URL}/register', json=data)
        
        if response.status_code == 201:
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash(response.json().get('error', 'Registration failed'), 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash('Please login to view cart', 'error')
        return redirect(url_for('login'))
    
    response = requests.get(f'{API_URL}/cart', params={'user_id': session['user_id']})
    cart_items = response.json().get('cart_items', [])
    return render_template('cart.html', cart_items=cart_items)

@app.route('/cart/add/<product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash('Please login to add items to cart', 'error')
        return redirect(url_for('login'))
    
    data = {
        'user_id': session['user_id'],
        'product_id': product_id,
        'quantity': int(request.form.get('quantity', 1))
    }
    
    response = requests.post(f'{API_URL}/cart/add', json=data)
    if response.status_code == 200:
        flash('Item added to cart!', 'success')
    else:
        flash('Failed to add item to cart', 'error')
    
    return redirect(url_for('cart'))

@app.route('/cart/update/<cart_item_id>', methods=['POST'])
def update_cart_item(cart_item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    data = {
        'cart_item_id': cart_item_id,
        'quantity': int(request.form['quantity'])
    }
    
    response = requests.put(f'{API_URL}/cart/update', json=data)
    if response.status_code == 200:
        flash('Cart updated successfully!', 'success')
    else:
        flash('Failed to update cart', 'error')
    
    return redirect(url_for('cart'))

@app.route('/cart/remove/<cart_item_id>')
def remove_from_cart(cart_item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    response = requests.delete(f'{API_URL}/cart/remove', params={'cart_item_id': cart_item_id})
    if response.status_code == 200:
        flash('Item removed from cart!', 'success')
    else:
        flash('Failed to remove item from cart', 'error')
    
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET'])
def checkout():
    if 'user_id' not in session:
        flash('Please login to checkout', 'error')
        return redirect(url_for('login'))
    
    response = requests.get(f'{API_URL}/cart', params={'user_id': session['user_id']})
    cart_items = response.json().get('cart_items', [])
    
    if not cart_items:
        flash('Your cart is empty', 'error')
        return redirect(url_for('cart'))
    
    return render_template('checkout.html', cart_items=cart_items)

@app.route('/place-order', methods=['POST'])
def place_order():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get form data
    shipping_info = {
        'firstName': request.form.get('firstName'),
        'lastName': request.form.get('lastName'),
        'address': request.form.get('address'),
        'city': request.form.get('city'),
        'state': request.form.get('state'),
        'zip': request.form.get('zip'),
        'phone': request.form.get('phone')
    }
    
    # Send checkout request to backend
    data = {
        'user_id': session['user_id'],
        'shipping_info': shipping_info
    }
    
    response = requests.post(f'{API_URL}/checkout', json=data)
    
    if response.status_code == 200:
        order_data = response.json()
        order_id = order_data.get('order_id')
        
        # Get order details
        order_response = requests.get(f'{API_URL}/orders/{order_id}')
        if order_response.status_code == 200:
            order = order_response.json()
            # Rename 'items' to 'order_items' to avoid conflict with dict.items() method
            order['order_items'] = order['items']
            del order['items']
            
            # Calculate subtotal from order items
            subtotal = sum(item['price'] for item in order['order_items'])
            
            # Add missing fields needed by the template
            order['subtotal'] = subtotal
            order['shipping'] = 5.0  # Same as in backend_api.py
            order['tax'] = subtotal * 0.1  # Same as in backend_api.py
            
            return render_template('order_confirmation.html', order=order)
        
        flash('Order placed successfully!', 'success')
        return render_template('order_confirmation.html')
    else:
        flash('Failed to place order. Please try again.', 'error')
        return redirect(url_for('checkout'))

# Create templates directory
def create_templates():
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)

if __name__ == '__main__':
    create_templates()
    app.run(port=5000, debug=True)