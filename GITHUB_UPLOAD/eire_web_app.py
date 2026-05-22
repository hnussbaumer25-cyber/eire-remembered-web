"""
ÉIRE REMEMBERED - WEB APPLICATION
Full-featured website for Irish social platform
Designed for elderly users (50-90 years) with large fonts and simple navigation
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
import requests

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Generate secure secret key

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'data', 'irelands_own.db')
STRIPE_SECRET_KEY = 'sk_test_51TZqwxECzN8KWy7DUTPcnwzlyvacRdkX7JpXtJPcavwiEDFJnuldhW3Oo8tGsD8HbgU6zal66M2Ww9WvJ1hcNYor00GP31andX'
PAYMENT_SERVICE_URL = 'http://localhost:5000'
MUSIC_STREAM_URL = 'https://eire-music-stream.onrender.com'

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def hash_password(password):
    """Hash password with SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

# ============================================================================
# AUTHENTICATION DECORATORS
# ============================================================================

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        
        db = get_db()
        user = db.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        db.close()
        
        if not user or user['role'] != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('home'))
        
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Please enter both username and password', 'danger')
            return render_template('login.html')
        
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username = ? AND password_hash = ?',
            (username, hash_password(password))
        ).fetchone()
        db.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        email = request.form.get('email', '').strip()
        
        # Validation
        if not username or not password or not email:
            flash('All fields are required', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return render_template('register.html')
        
        # Check if username exists
        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        
        if existing:
            db.close()
            flash('Username already exists', 'danger')
            return render_template('register.html')
        
        # Create user
        try:
            db.execute(
                '''INSERT INTO users (username, email, password_hash, role, created_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (username, email, hash_password(password), 'user', datetime.now().isoformat())
            )
            db.commit()
            
            # Get new user ID
            user = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            db.close()
            
            # Log them in
            session['user_id'] = user['id']
            session['username'] = username
            session['role'] = 'user'
            
            flash('Account created successfully!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            db.close()
            flash(f'Error creating account: {e}', 'danger')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))

# ============================================================================
# MAIN ROUTES
# ============================================================================

@app.route('/')
def home():
    """Homepage"""
    db = get_db()
    
    # Get latest published articles (5 most recent)
    articles = db.execute(
        '''SELECT id, title, author, category, created_at 
           FROM articles 
           WHERE status = 'published'
           ORDER BY created_at DESC 
           LIMIT 5'''
    ).fetchall()
    
    # Get active polls
    polls = db.execute(
        '''SELECT id, title, question, created_at 
           FROM polls 
           WHERE status = 'active'
           ORDER BY created_at DESC 
           LIMIT 3'''
    ).fetchall()
    
    # Get active quizzes
    quizzes = db.execute(
        '''SELECT id, title, description, created_at 
           FROM quizzes 
           WHERE status = 'active'
           ORDER BY created_at DESC 
           LIMIT 3'''
    ).fetchall()
    
    db.close()
    
    return render_template('home.html', articles=articles, polls=polls, quizzes=quizzes)

# ============================================================================
# ARTICLE ROUTES
# ============================================================================

@app.route('/articles')
def articles():
    """List all articles"""
    category = request.args.get('category', 'all')
    
    db = get_db()
    
    if category == 'all':
        articles = db.execute(
            '''SELECT id, title, author, category, created_at 
               FROM articles 
               WHERE status = 'published'
               ORDER BY created_at DESC'''
        ).fetchall()
    else:
        articles = db.execute(
            '''SELECT id, title, author, category, created_at 
               FROM articles 
               WHERE status = 'published' AND category = ?
               ORDER BY created_at DESC''',
            (category,)
        ).fetchall()
    
    db.close()
    
    return render_template('articles.html', articles=articles, category=category)

@app.route('/article/<int:article_id>')
def article_detail(article_id):
    """View single article"""
    db = get_db()
    
    article = db.execute(
        'SELECT * FROM articles WHERE id = ? AND status = "published"',
        (article_id,)
    ).fetchone()
    
    if not article:
        db.close()
        flash('Article not found', 'danger')
        return redirect(url_for('articles'))
    
    # Increment views
    db.execute('UPDATE articles SET views = views + 1 WHERE id = ?', (article_id,))
    db.commit()
    db.close()
    
    return render_template('article_detail.html', article=article)

# ============================================================================
# POLL ROUTES
# ============================================================================

@app.route('/polls')
def polls():
    """List all polls"""
    db = get_db()
    
    polls = db.execute(
        '''SELECT id, title, question, description, created_at 
           FROM polls 
           WHERE status = 'active'
           ORDER BY created_at DESC'''
    ).fetchall()
    
    db.close()
    
    return render_template('polls.html', polls=polls)

@app.route('/poll/<int:poll_id>', methods=['GET', 'POST'])
def poll_detail(poll_id):
    """View and vote on poll"""
    db = get_db()
    
    poll = db.execute('SELECT * FROM polls WHERE id = ?', (poll_id,)).fetchone()
    
    if not poll:
        db.close()
        flash('Poll not found', 'danger')
        return redirect(url_for('polls'))
    
    # Get options
    options = db.execute(
        'SELECT * FROM poll_options WHERE poll_id = ? ORDER BY id',
        (poll_id,)
    ).fetchall()
    
    # Check if user has voted
    has_voted = False
    if 'user_id' in session:
        vote = db.execute(
            'SELECT * FROM poll_votes WHERE poll_id = ? AND user_id = ?',
            (poll_id, session['user_id'])
        ).fetchone()
        has_voted = vote is not None
    
    # Handle vote submission
    if request.method == 'POST' and 'user_id' in session and not has_voted:
        option_id = request.form.get('option_id', type=int)
        
        if option_id:
            try:
                # Record vote
                db.execute(
                    'INSERT INTO poll_votes (poll_id, option_id, user_id, voted_at) VALUES (?, ?, ?, ?)',
                    (poll_id, option_id, session['user_id'], datetime.now().isoformat())
                )
                
                # Increment vote count
                db.execute(
                    'UPDATE poll_options SET votes = votes + 1 WHERE id = ?',
                    (option_id,)
                )
                
                db.commit()
                flash('Vote recorded! Thank you for participating.', 'success')
                has_voted = True
                
                # Refresh options with new counts
                options = db.execute(
                    'SELECT * FROM poll_options WHERE poll_id = ? ORDER BY id',
                    (poll_id,)
                ).fetchall()
            except Exception as e:
                flash(f'Error recording vote: {e}', 'danger')
    
    # Calculate percentages
    total_votes = sum(opt['votes'] for opt in options)
    options_with_percent = []
    for opt in options:
        percent = (opt['votes'] / total_votes * 100) if total_votes > 0 else 0
        options_with_percent.append({
            'id': opt['id'],
            'text': opt['option_text'],
            'votes': opt['votes'],
            'percent': round(percent, 1)
        })
    
    db.close()
    
    return render_template('poll_detail.html', poll=poll, options=options_with_percent, 
                          has_voted=has_voted, total_votes=total_votes)

# ============================================================================
# QUIZ ROUTES
# ============================================================================

@app.route('/quizzes')
def quizzes():
    """List all quizzes"""
    db = get_db()
    
    quizzes = db.execute(
        '''SELECT id, title, description, created_at 
           FROM quizzes 
           WHERE status = 'active'
           ORDER BY created_at DESC'''
    ).fetchall()
    
    db.close()
    
    return render_template('quizzes.html', quizzes=quizzes)

@app.route('/quiz/<int:quiz_id>', methods=['GET', 'POST'])
def quiz_detail(quiz_id):
    """Take a quiz"""
    db = get_db()
    
    quiz = db.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    
    if not quiz:
        db.close()
        flash('Quiz not found', 'danger')
        return redirect(url_for('quizzes'))
    
    # Get questions
    questions = db.execute(
        'SELECT * FROM quiz_questions WHERE quiz_id = ? ORDER BY id',
        (quiz_id,)
    ).fetchall()
    
    if request.method == 'POST':
        # Calculate score
        score = 0
        total = len(questions)
        
        for q in questions:
            user_answer = request.form.get(f'question_{q["id"]}')
            if user_answer and user_answer == q['correct_answer']:
                score += 1
        
        # Save result if logged in
        if 'user_id' in session:
            try:
                db.execute(
                    '''INSERT INTO quiz_results (quiz_id, user_id, score, total_questions, completed_at)
                       VALUES (?, ?, ?, ?, ?)''',
                    (quiz_id, session['user_id'], score, total, datetime.now().isoformat())
                )
                db.commit()
            except:
                pass
        
        db.close()
        
        percentage = round((score / total) * 100, 1) if total > 0 else 0
        
        return render_template('quiz_results.html', quiz=quiz, score=score, 
                             total=total, percentage=percentage)
    
    db.close()
    
    return render_template('quiz_detail.html', quiz=quiz, questions=questions)

# ============================================================================
# MUSIC ROUTE
# ============================================================================

@app.route('/music')
def music():
    """Music streaming page"""
    return render_template('music.html', stream_url=MUSIC_STREAM_URL)

# ============================================================================
# USER PROFILE & CREDITS
# ============================================================================

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    db = get_db()
    
    user = db.execute(
        'SELECT * FROM users WHERE id = ?',
        (session['user_id'],)
    ).fetchone()
    
    # Get user's credits
    credits = db.execute(
        'SELECT * FROM user_credits WHERE user_id = ?',
        (session['user_id'],)
    ).fetchone()
    
    # Get recent articles
    articles = db.execute(
        '''SELECT id, title, status, created_at 
           FROM articles 
           WHERE author = ?
           ORDER BY created_at DESC 
           LIMIT 5''',
        (user['username'],)
    ).fetchall()
    
    db.close()
    
    return render_template('profile.html', user=user, credits=credits, articles=articles)

# ============================================================================
# SEO ROUTES
# ============================================================================

@app.route('/robots.txt')
def robots():
    """Serve robots.txt for search engines"""
    return app.send_static_file('robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    """Serve sitemap.xml for search engines"""
    return app.send_static_file('sitemap.xml')

# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    db = get_db()
    
    # Get stats
    stats = {
        'total_users': db.execute('SELECT COUNT(*) as count FROM users').fetchone()['count'],
        'total_articles': db.execute('SELECT COUNT(*) as count FROM articles').fetchone()['count'],
        'total_polls': db.execute('SELECT COUNT(*) as count FROM polls').fetchone()['count'],
        'total_quizzes': db.execute('SELECT COUNT(*) as count FROM quizzes').fetchone()['count'],
    }
    
    db.close()
    
    return render_template('admin_dashboard.html', stats=stats)

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("=" * 80)
    print("ÉIRE REMEMBERED - WEB APPLICATION")
    print("=" * 80)
    print(f"Database: {DATABASE}")
    print(f"Music Stream: {MUSIC_STREAM_URL}")
    print()
    print("Starting server on http://localhost:8000")
    print("=" * 80)
    print()
    
    app.run(host='0.0.0.0', port=8000, debug=True)
