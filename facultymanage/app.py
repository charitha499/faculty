from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Secret key for session management

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Using Gmail's SMTP server
app.config['MAIL_PORT'] = 587                # Port for TLS encryption
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'your_app_password'    # Replace with your app password
app.config['MAIL_DEFAULT_SENDER'] = 'your_email@gmail.com'

# Initialize Flask-Mail
mail = Mail(app)

# Function to connect to the database
def connect_db():
    return sqlite3.connect("faculty.db")

# Create tables (run only once)
def create_tables():
    with connect_db() as conn:
        # Faculty table
        conn.execute('''CREATE TABLE IF NOT EXISTS faculty (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        department TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL);''')

        # Users table (now includes email and receive_notifications column)
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        receive_notifications INTEGER DEFAULT 1);''')

        # Notifications table
        conn.execute('''CREATE TABLE IF NOT EXISTS notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subject TEXT NOT NULL,
                        body TEXT NOT NULL,
                        recipient_email TEXT NOT NULL,
                        date_sent TIMESTAMP DEFAULT CURRENT_TIMESTAMP);''')

# Function to send notification email to both admin and users who have opted in
def send_notification_email(name, department, email):
    admin_email = "admin_email@example.com"  # Replace with your admin's email address
    subject = "New Faculty Added"
    body = f"""
    Hello Admin,

    A new faculty member has been added to the system:

    Name: {name}
    Department: {department}
    Email: {email}

    Regards,
    Faculty Management System
    """

    try:
        # Send email to admin
        msg = Message(subject, recipients=[admin_email])
        msg.body = body
        mail.send(msg)
        print("Notification email sent to admin.")

        # Fetch users who have opted in for notifications and send them the notification
        with connect_db() as conn:
            cursor = conn.execute("SELECT email FROM users WHERE receive_notifications = 1")
            users = cursor.fetchall()

            for user in users:
                user_email = user[0]
                user_msg = Message(subject, recipients=[user_email])
                user_msg.body = body
                mail.send(user_msg)
                print(f"Notification email sent to {user_email}.")

        # Store the notification in the database
        with connect_db() as conn:
            conn.execute("INSERT INTO notifications (subject, body, recipient_email) VALUES (?, ?, ?)",
                         (subject, body, admin_email))
            conn.commit()
    except Exception as e:
        print(f"Error sending email: {e}")

# Home Page - Login required
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with connect_db() as conn:
        # Fetch all faculties
        cursor = conn.execute("SELECT * FROM faculty")
        faculties = cursor.fetchall()

        # Fetch distinct departments
        cursor = conn.execute("SELECT DISTINCT department FROM faculty")
        departments = cursor.fetchall()

        # Count the total number of faculty members
        cursor = conn.execute("SELECT COUNT(*) FROM faculty")
        faculty_count = cursor.fetchone()[0]

    return render_template('index.html', faculties=faculties, departments=departments, faculty_count=faculty_count)

# Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with connect_db() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE username=?", (username,))
            user = cursor.fetchone()
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('home'))
        flash("Invalid username or password", "error")
    return render_template('login.html')

# Signup Page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        # Hash the password before storing
        hashed_password = generate_password_hash(password)

        with connect_db() as conn:
            # Insert new user into the users table
            conn.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                         (username, hashed_password, email))
            conn.commit()

        flash("You have signed up successfully! You can now log in.", "success")
        return redirect(url_for('login'))

    return render_template('signup.html')

# Add a new faculty (or update if email already exists)
@app.route('/add', methods=['GET', 'POST'])
def add_faculty():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        email = request.form['email']

        with connect_db() as conn:
            # Use INSERT OR REPLACE to replace an existing record if email already exists
            conn.execute("INSERT OR REPLACE INTO faculty (id, name, department, email) "
                         "VALUES ((SELECT id FROM faculty WHERE email = ?), ?, ?, ?)",
                         (email, name, department, email))

        # Call the function to send a notification email to both admin and users who have opted in
        send_notification_email(name, department, email)

        flash("Faculty added or updated successfully, and admin has been notified.", "success")
        return redirect(url_for('home'))

    return render_template('add_faculty.html')

# Update faculty details
@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update_faculty(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with connect_db() as conn:
        cursor = conn.execute("SELECT * FROM faculty WHERE id=?", (id,))
        faculty = cursor.fetchone()
    if not faculty:
        return "Faculty not found", 404

    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        email = request.form['email']
        with connect_db() as conn:
            conn.execute("UPDATE faculty SET name=?, department=?, email=? WHERE id=?",
                         (name, department, email, id))
        return redirect(url_for('home'))
    return render_template('update_faculty.html', faculty=faculty)

# Delete faculty
@app.route('/delete/<int:id>')
def delete_faculty(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with connect_db() as conn:
        conn.execute("DELETE FROM faculty WHERE id=?", (id,))
    return redirect(url_for('home'))

# Department-wise faculty list
@app.route('/department/<string:department>')
def department_faculty(department):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    with connect_db() as conn:
        cursor = conn.execute("SELECT * FROM faculty WHERE department=?", (department,))
        faculties = cursor.fetchall()
    return render_template('department_faculty.html', department=department, faculties=faculties)

# View notifications
@app.route('/notifications')
def view_notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with connect_db() as conn:
        cursor = conn.execute("SELECT * FROM notifications ORDER BY date_sent DESC")
        notifications = cursor.fetchall()

    return render_template('notifications.html', notifications=notifications)

# User Settings Page - Subscribe/Unsubscribe from Notifications
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with connect_db() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
        user = cursor.fetchone()

    if request.method == 'POST':
        # Get the checkbox value for notification preferences
        receive_notifications = request.form.get('receive_notifications') == 'on'
        with connect_db() as conn:
            conn.execute("UPDATE users SET receive_notifications=? WHERE id=?",
                         (receive_notifications, user[0]))
            conn.commit()
        flash("Your notification preferences have been updated.", "success")

    return render_template('settings.html', user=user)

# Logout route
@app.route('/logout')
def logout():
    # Clear the session
    session.pop('user_id', None)
    session.pop('username', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    create_tables()  # Initialize tables
    app.run(debug=True)
