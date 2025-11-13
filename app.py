import os
import sqlite3
import hashlib
import pickle
import joblib
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g

# ==========================================================
# 🔧 Flask Configuration
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.secret_key = "loan_eligibility_secret"


# ==========================================================
# 🗄️ Database Setup
# ==========================================================
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")

def get_db():
    """Get or create a SQLite connection per request"""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    """Create required tables if they don't exist"""
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            message TEXT
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS interested_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            bank TEXT,
            loan_type TEXT,
            rate TEXT,
            docs TEXT
        );
        """)
    print("✅ Database initialized successfully!")

init_db()


# ==========================================================
# 🤖 Load ML Model
# ==========================================================
model_path = os.path.join(BASE_DIR, "trained_model", "loan_model.pkl")
features_path = os.path.join(BASE_DIR, "trained_model", "model_features.pkl")

def load_model_safely(path):
    try:
        model = joblib.load(open(path, "rb"))
        print("✅ Model loaded with joblib")
        return model
    except:
        with open(path, "rb") as f:
            model = pickle.load(f)
        print("✅ Model loaded with pickle")
        return model

model = load_model_safely(model_path)
with open(features_path, "rb") as f:
    model_features = pickle.load(f)


# ==========================================================
# 🌐 ROUTES
# ==========================================================
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        conn = get_db()
        conn.execute("INSERT INTO contacts (name, email, message) VALUES (?, ?, ?)",
                     (name, email, message))
        conn.commit()
        flash("✅ Your message has been sent successfully!", "success")
        return redirect(url_for('contact'))
    return render_template('contact.html')


# ==========================================================
# 👤 SIGNUP / LOGIN / LOGOUT
# ==========================================================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()

        conn = get_db()
        try:
            conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                         (name, email, password))
            conn.commit()
            flash("🎉 Account created! Please log in.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("⚠️ Email already exists!", "danger")

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        conn = get_db()
        cursor = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()

        if user:
            session['user'] = user['name']
            session['email'] = user['email']
            flash(f"Welcome back, {user['name']} 👋", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("❌ Invalid email or password.", "danger")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))


# ==========================================================
# 💰 LOAN ELIGIBILITY
# ==========================================================
@app.route('/eligibility_form')
def eligibility_form():
    return render_template('eligibility_form.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        gender_male = "1" if request.form.get("gender") == "Male" else "0"
        married_yes = "1" if request.form.get("married") == "Yes" else "0"
        education_graduate = "1" if request.form.get("education") == "Graduate" else "0"
        self_employed_yes = "1" if request.form.get("self_employed") == "Yes" else "0"

        data = {
            "Gender": gender_male,
            "Married": married_yes,
            "Dependents": int(request.form.get("dependents")),
            "Education": education_graduate,
            "Self_Employed": self_employed_yes,
            "ApplicantIncome": float(request.form.get("applicant_income")),
            "CoapplicantIncome": float(request.form.get("coapplicant_income")),
            "LoanAmount": float(request.form.get("loan_amount")),
            "Loan_Amount_Term": float(request.form.get("loan_term")),
            "Credit_History": float(request.form.get("credit_score")),
            "Property_Area_Rural": 1 if request.form.get("property_area") == "Rural" else 0,
            "Property_Area_Semiurban": 1 if request.form.get("property_area") == "Semiurban" else 0,
            "Property_Area_Urban": 1 if request.form.get("property_area") == "Urban" else 0,
            "Age": float(request.form.get("age"))
        }

        input_data = [data.get(f, 0) for f in model_features]
        prediction = model.predict([input_data])[0]

        if prediction == 1:
            result = "Eligible"
            message = "🎉 Congratulations! You are eligible for a loan."
            chance = "High"
            eligible_banks = [
                {"bank": "HDFC Bank", "type": "Home Loan", "rate": "8.5%", "docs": "ID Proof, Property Papers"},
                {"bank": "ICICI Bank", "type": "Personal Loan", "rate": "10.2%", "docs": "ID Proof, Salary Slips"},
                {"bank": "SBI Bank", "type": "Education Loan", "rate": "9.1%", "docs": "ID Proof, Admission Letter"}
            ]
        else:
            result = "Not Eligible"
            message = "⚠️ Unfortunately, you are not eligible right now."
            chance = "Low"
            eligible_banks = []

        return render_template(
            'result.html',
            result=result,
            message=message,
            chance=chance,
            eligible_banks=eligible_banks
        )

    except Exception as e:
        print("❌ Prediction Error:", e)
        return f"Error: {str(e)}"


# ==========================================================
# ⭐ INTERESTED LOANS (PERSISTENT)
# ==========================================================
@app.route('/add_interest', methods=['POST'])
def add_interest():
    """Save a loan to user's interested list (in database)"""
    if 'email' not in session:
        return jsonify({"error": "Please log in first"}), 401

    loan_data = request.get_json()
    user_email = session['email']

    conn = get_db()
    conn.execute("""
        INSERT INTO interested_loans (user_email, bank, loan_type, rate, docs)
        VALUES (?, ?, ?, ?, ?)
    """, (user_email, loan_data.get('bank'), loan_data.get('loan_type'),
          loan_data.get('rate'), loan_data.get('docs')))
    conn.commit()

    return jsonify({"message": "✅ Loan added to your interests!"})


@app.route('/interested')
def interested():
    if 'email' not in session:
        flash("Please log in to view your saved loans.", "warning")
        return redirect(url_for('login'))

    user_email = session['email']
    conn = get_db()
    cursor = conn.execute("SELECT bank, loan_type, rate, docs FROM interested_loans WHERE user_email=?", (user_email,))
    interested_loans = cursor.fetchall()

    return render_template('interested.html', interested_loans=interested_loans)


@app.route('/remove_interest', methods=['POST'])
def remove_interest():
    if 'email' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    bank = request.form['bank']
    loan_type = request.form['loan_type']
    user_email = session['email']

    conn = get_db()
    conn.execute("""
        DELETE FROM interested_loans
        WHERE user_email=? AND bank=? AND loan_type=?
    """, (user_email, bank, loan_type))
    conn.commit()

    flash("✅ Loan removed from your interests.", "info")
    return redirect(url_for('interested'))


@app.route('/dashboard')
def dashboard():
    summary = {
        "eligible_count": 3,
        "not_eligible_count": 1,
    }

    user_email = session.get('email')
    interested_count = 0
    if user_email:
        conn = get_db()
        cursor = conn.execute("SELECT COUNT(*) FROM interested_loans WHERE user_email=?", (user_email,))
        interested_count = cursor.fetchone()[0]

    summary["interested_count"] = interested_count

    recent_checks = [
        {"date": "2025-11-03", "loan_type": "Home Loan", "result": "Eligible", "banks": "HDFC, ICICI"},
        {"date": "2025-11-01", "loan_type": "Personal Loan", "result": "Not Eligible", "banks": "-"}
    ]

    conn = get_db()
    cursor = conn.execute("SELECT bank, loan_type, rate, docs FROM interested_loans WHERE user_email=?", (user_email,))
    interested_loans = cursor.fetchall()

    return render_template('dashboard.html', summary=summary, recent_checks=recent_checks, interested_loans=interested_loans)


# ==========================================================
# 🚀 RUN
# ==========================================================
if __name__ == '__main__':
    print("🌍 Flask app running at: http://127.0.0.1:5000/")
    app.run(debug=True)
