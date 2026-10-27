import os
import random
from datetime import datetime, date
from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'ace.tumandao7@gmail.com'
app.config['MAIL_PASSWORD'] = 'wzbdjcrcaillksjr'
app.config['MAIL_DEFAULT_SENDER'] = 'Rent-Track@gmail.com'

mail = Mail(app)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='Customer')
    seller_status = db.Column(db.String(20), default='None')  
    shop_name = db.Column(db.String(100), nullable=True)
    shop_details = db.Column(db.Text, nullable=True)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_email = db.Column(db.String(120), nullable=True) 
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)

class Rental(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(20), unique=True, nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.String(20), nullable=False)
    return_date = db.Column(db.String(20), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Active')

@app.route('/')
def index():
    items = Item.query.limit(4).all()
    return render_template('index.html', items=items)

@app.route('/catalog')
@app.route('/catalog/<category>')
def catalog(category=None):
    query = Item.query
    search_query = request.args.get('search', '').strip()
    if category:
        query = query.filter(Item.category.ilike(f"%{category}%"))
    if search_query:
        query = query.filter(
            db.or_(
                Item.name.ilike(f"%{search_query}%"),
                Item.category.ilike(f"%{search_query}%"),
                Item.size.ilike(f"%{search_query}%")
            )
        )
    items = query.all()
    return render_template('catalog.html', items=items, category=category, search_query=search_query)

@app.route('/item/<int:id>')
def item_detail(id):
    item = Item.query.get_or_404(id)
    return render_template('item_detail.html', item=item)

@app.route('/cart')
def cart():
    if 'user_email' not in session:
        return redirect(url_for('login')) 
        
    cart_items = session.get('cart', [])
    total = sum(item['price'] for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/cart/add/<int:id>', methods=['GET', 'POST'])
def add_to_cart(id):
    if 'user_email' not in session:
        return redirect(url_for('login'))

    item = Item.query.get_or_404(id)
    if 'cart' not in session:
        session['cart'] = []
    
    session['cart'].append({
        'id': item.id,
        'name': item.name,
        'size': item.size,
        'price': item.price,
        'image_url': item.image_url
    })
    session.modified = True
    return redirect(url_for('cart'))

@app.route('/cart/remove/<int:id>')
def remove_from_cart(id):
    if 'cart' in session:
        session['cart'] = [item for item in session['cart'] if item['id'] != id]
        session.modified = True
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    cart_items = session.get('cart', [])
    total = sum(item['price'] for item in cart_items)

    if request.method == 'POST':
        start_date = request.form.get('start_date')
        return_date = request.form.get('return_date')
        email = request.form.get('customer_email') or request.form.get('email')
        shipping_address = request.form.get('shipping_address', 'Standard Delivery')

        item_names = ", ".join([item['name'] for item in cart_items])
        trans_id = f"#TR-{random.randint(1000, 9999)}"

        new_rental = Rental(
            transaction_id=trans_id,
            customer_email=email,
            item_name=item_names,
            start_date=start_date if start_date else str(date.today()),
            return_date=return_date if return_date else str(date.today()),
            total_amount=total,
            status='Active'
        )
        db.session.add(new_rental)
        db.session.commit()

        try:
            item_details = "\n".join([f"- {item['name']} (Size: {item['size']}) - P{item['price']}" for item in cart_items])
            msg = Message(
                subject=f'RentTrack - Rental Order Confirmation ({trans_id})',
                recipients=[email],
                body=f"Hello,\n\nThank you for renting with RentTrack! Transaction ID: {trans_id}\n\nShipping Address:\n{shipping_address}\n\nOrdered Items:\n{item_details}\n\nTotal Amount: P{total}\n\nWe will notify you once your items are out for delivery."
            )
            mail.send(msg)
        except Exception as e:
            print(f"Email sending skipped/failed on cloud: {e}")

        session.pop('cart', None)
        return render_template('order_success.html', email=email)

    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/profile')
def profile():
    if 'user_email' not in session:
        flash('Please log in to view your profile.', 'info')
        return redirect(url_for('login'))
        
    user = User.query.filter_by(email=session['user_email']).first()
    if not user:
        session.clear()
        return redirect(url_for('login'))
        
    rentals = Rental.query.filter_by(customer_email=user.email).order_by(Rental.id.desc()).all()
    today = date.today()
    for r in rentals:
        if r.status != 'Returned':
            try:
                ret_date = datetime.strptime(r.return_date, '%Y-%m-%d').date()
                if today > ret_date:
                    r.computed_status = 'Overdue'
                    r.badge_class = 'bg-danger text-white'
                elif (ret_date - today).days <= 2:
                    r.computed_status = 'Due Soon'
                    r.badge_class = 'bg-warning text-dark'
                else:
                    r.computed_status = 'Active'
                    r.badge_class = 'bg-success text-white'
            except Exception:
                r.computed_status = r.status
                r.badge_class = 'bg-secondary text-white'
        else:
            r.computed_status = 'Returned'
            r.badge_class = 'bg-secondary text-white'
            
    return render_template('profile.html', user=user, rentals=rentals)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_email' in session:
        return redirect(url_for('profile'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        if user and (check_password_hash(user.password, password) or user.password == password):
            session['user_email'] = user.email
            session['user_role'] = user.role
            
            flash('Login successful! Welcome back.', 'success')
            
            if user.role == 'Admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'Seller':
                return redirect(url_for('seller_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid email or password!', 'danger')
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email is already registered!', 'danger') 
            return redirect(url_for('register'))
            
        new_user = User(email=email, password=password, role='Customer', seller_status='None')
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/apply-seller', methods=['GET', 'POST'])
def apply_seller():
    if 'user_email' not in session:
        return redirect(url_for('login'))
        
    user = User.query.filter_by(email=session['user_email']).first()
    
    if request.method == 'POST':
        user.shop_name = request.form['shop_name']
        user.shop_details = request.form['shop_details']
        user.seller_status = 'Pending'
        db.session.commit()
        return redirect(url_for('apply_seller'))
        
    return render_template('apply_seller.html', user=user)

@app.route('/admin/dashboard')
def admin_dashboard():
    rentals = Rental.query.all()
    active_rentals_count = Rental.query.filter_by(status='Active').count()
    overdue_count = 0 
    total_revenue = sum(r.total_amount for r in rentals)
    
    return render_template('admin/dashboard.html', 
                           rentals=rentals, 
                           active_count=active_rentals_count, 
                           overdue_count=overdue_count, 
                           total_revenue=total_revenue)

@app.route('/admin/rentals')
def admin_rentals():
    rentals = Rental.query.all()
    today = date.today()
    for r in rentals:
        if r.status != 'Returned':
            try:
                ret_date = datetime.strptime(r.return_date, '%Y-%m-%d').date()
                if today > ret_date:
                    r.computed_status = 'Overdue'
                    r.badge_class = 'bg-danger text-white'
                elif (ret_date - today).days <= 2:
                    r.computed_status = 'Due Soon'
                    r.badge_class = 'bg-warning text-dark'
                else:
                    r.computed_status = 'Active'
                    r.badge_class = 'bg-success text-white'
            except Exception:
                r.computed_status = r.status
                r.badge_class = 'bg-secondary text-white'
        else:
            r.computed_status = 'Returned'
            r.badge_class = 'bg-secondary text-white'
    return render_template('admin/rentals.html', rentals=rentals)

@app.route('/admin/rentals/return/<int:id>')
def mark_returned(id):
    rental = Rental.query.get_or_404(id)
    rental.status = 'Returned'
    db.session.commit()
    return redirect(url_for('admin_rentals'))

@app.route('/admin/sellers')
def admin_sellers():
    pending_sellers = User.query.filter_by(seller_status='Pending').all()
    approved_sellers = User.query.filter_by(role='Seller').all()
    return render_template('admin/manage_sellers.html', pending_sellers=pending_sellers, approved_sellers=approved_sellers)

@app.route('/admin/sellers/approve/<int:id>')
def approve_seller(id):
    user = User.query.get_or_404(id)
    user.seller_status = 'Approved'
    user.role = 'Seller'
    db.session.commit()
    return redirect(url_for('admin_sellers'))

@app.route('/admin/sellers/reject/<int:id>')
def reject_seller(id):
    user = User.query.get_or_404(id)
    user.seller_status = 'None'
    user.shop_name = None
    user.shop_details = None
    db.session.commit()
    return redirect(url_for('admin_sellers'))

@app.route('/admin/sellers/delete/<int:id>')
def delete_approved_seller(id):
    user = User.query.get_or_404(id)
    Item.query.filter_by(seller_email=user.email).delete()
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin_sellers'))

@app.route('/seller/dashboard')
def seller_dashboard():
    if 'user_email' not in session or session.get('user_role') != 'Seller':
        return redirect(url_for('login'))
    items = Item.query.filter_by(seller_email=session['user_email']).all()
    return render_template('seller/dashboard.html', items=items)

@app.route('/seller/items/add', methods=['GET', 'POST'])
def seller_add_item():
    if 'user_email' not in session or session.get('user_role') != 'Seller':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        size = request.form['size']
        price = float(request.form['price'])
        
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = 'uploads/' + filename

        new_item = Item(seller_email=session['user_email'], name=name, category=category, size=size, price=price, image_url=image_url)
        db.session.add(new_item)
        db.session.commit()
        return redirect(url_for('seller_dashboard'))
    return render_template('seller/add_item.html')

@app.route('/seller/items/edit/<int:id>', methods=['GET', 'POST'])
def seller_edit_item(id):
    if 'user_email' not in session or session.get('user_role') != 'Seller':
        return redirect(url_for('login'))
        
    item = Item.query.filter_by(id=id, seller_email=session['user_email']).first_or_404()
    if request.method == 'POST':
        item.name = request.form['name']
        item.category = request.form['category']
        item.size = request.form['size']
        item.price = float(request.form['price'])
        
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                item.image_url = 'uploads/' + filename

        db.session.commit()
        return redirect(url_for('seller_dashboard'))
    return render_template('seller/edit_item.html', item=item)

@app.route('/seller/items/delete/<int:id>')
def seller_delete_item(id):
    if 'user_email' not in session or session.get('user_role') != 'Seller':
        return redirect(url_for('login'))
        
    item = Item.query.filter_by(id=id, seller_email=session['user_email']).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('seller_dashboard'))

@app.route('/seller/rentals')
def seller_rentals():
    if 'user_email' not in session or session.get('user_role') != 'Seller':
        return redirect(url_for('login'))
        
    seller_email = session['user_email']
    seller_items = Item.query.filter_by(seller_email=seller_email).all()
    seller_item_names = [item.name for item in seller_items]
    
    all_rentals = Rental.query.all()
    filtered_rentals = []
    
    today = date.today()
    for r in all_rentals:
        is_seller_item = any(name.strip() in r.item_name for name in seller_item_names)
        if is_seller_item:
            if r.status != 'Returned':
                try:
                    ret_date = datetime.strptime(r.return_date, '%Y-%m-%d').date()
                    if today > ret_date:
                        r.computed_status = 'Overdue'
                        r.badge_class = 'bg-danger text-white'
                    elif (ret_date - today).days <= 2:
                        r.computed_status = 'Due Soon'
                        r.badge_class = 'bg-warning text-dark'
                    else:
                        r.computed_status = 'Active'
                        r.badge_class = 'bg-success text-white'
                except Exception:
                    r.computed_status = r.status
                    r.badge_class = 'bg-secondary text-white'
            else:
                r.computed_status = 'Returned'
                r.badge_class = 'bg-secondary text-white'
            
            filtered_rentals.append(r)
            
    return render_template('seller/rentals.html', rentals=filtered_rentals)

@app.route('/seller/rentals/return/<int:id>')
def seller_mark_returned(id):
    if 'user_email' not in session or session.get('user_role') != 'Seller':
        return redirect(url_for('login'))
        
    rental = Rental.query.get_or_404(id)
    rental.status = 'Returned'
    db.session.commit()
    return redirect(url_for('seller_rentals'))

with app.app_context():
    db.create_all()
    admin_email = "admin@renttrack.com" 
    admin_user = User.query.filter_by(email=admin_email).first()
    if not admin_user:
        hashed_password = generate_password_hash("admin123") 
        new_admin = User(email=admin_email, password=hashed_password, role='Admin', seller_status='None')
        db.session.add(new_admin)
        db.session.commit()
        print("Admin account created successfully!")

if __name__ == '__main__':
    app.run(debug=True)