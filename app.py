from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
from datetime import datetime, date
import threading, time
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SESSION_TYPE'] = 'filesystem'
DB = 'task_manager.db'

# ================= DATABASE =================

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# ================= INIT =================

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            color TEXT,
            weight INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category_id INTEGER,
            title TEXT,
            priority TEXT CHECK(priority IN ('High','Medium','Low')),
            risk TEXT CHECK(risk IN ('Critical','Important','Normal')),
            deadline DATE,
            completed INTEGER DEFAULT 0,
            overdue INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            owner_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER,
            user_id INTEGER,
            role TEXT CHECK(role IN ('admin','member')),
            PRIMARY KEY (group_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS group_invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            inviter_id INTEGER,
            invitee_id INTEGER,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','accepted','rejected'))
        );
        CREATE TABLE IF NOT EXISTS group_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            title TEXT,
            priority TEXT CHECK(priority IN ('High','Medium','Low')),
            risk TEXT CHECK(risk IN ('Critical','Important','Normal')),
            deadline DATE,
            completed INTEGER DEFAULT 0
        );
        ''')
        db.commit()
        print("Database initialized successfully!")

# ================= AUTH =================

def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*a, **kw)
    return wrap

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            return render_template('register.html', error='Username and password required')
        
        try:
            db = get_db()
            db.execute('INSERT INTO users (username, password) VALUES (?,?)', (
                username,
                generate_password_hash(password)
            ))
            db.commit()
            
            user = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
            session['user_id'] = user['id']
            session['username'] = username
            return redirect(url_for('dashboard'))
            
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Username already exists')
    
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        
        return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ================= PRIORITY SYSTEM =================

def calculate_urgency(task):
    """Calculate urgency score for a task (higher = more urgent)"""
    priority_weights = {'High': 5, 'Medium': 3, 'Low': 1}
    risk_weights = {'Critical': 5, 'Important': 3, 'Normal': 1}
    
    priority = task.get('priority', 'Low')
    risk = task.get('risk', 'Normal')
    weight = task.get('weight', 1)
    
    deadline_str = task.get('deadline')
    if not deadline_str:
        days_until = 999
    else:
        try:
            deadline_date = datetime.strptime(deadline_str, '%Y-%m-%d').date()
            days_until = (deadline_date - date.today()).days
        except (ValueError, TypeError):
            days_until = 999
    
    priority_score = priority_weights.get(priority, 1) * 3
    risk_score = risk_weights.get(risk, 1) * 3
    category_score = weight * 2
    deadline_score = max(0, 10 - days_until) * 4 if days_until >= 0 else 10 * 4
    
    return priority_score + risk_score + category_score + deadline_score

# ================= CATEGORIES/STATISTICS =================

@app.route('/categories')
@login_required
def categories():
    """Show categories management page"""
    db = get_db()
    categories = db.execute('SELECT * FROM categories WHERE user_id=? ORDER BY weight DESC', 
                           (session['user_id'],)).fetchall()
    
    # Get category statistics
    category_stats = db.execute('''
        SELECT 
            c.name as category_name,
            c.color,
            COUNT(t.id) as task_count,
            SUM(CASE WHEN t.completed=1 THEN 1 ELSE 0 END) as completed_count
        FROM categories c
        LEFT JOIN tasks t ON c.id = t.category_id AND t.user_id=?
        WHERE c.user_id=?
        GROUP BY c.id
        ORDER BY c.weight DESC
    ''', (session['user_id'], session['user_id'])).fetchall()
    
    return render_template('categories.html', 
                          categories=categories, 
                          category_stats=category_stats)

@app.route('/category/add', methods=['POST'])
@login_required
def add_category():
    name = request.form.get('name', '').strip()
    color = request.form.get('color', '#007bff')
    weight = int(request.form.get('weight', 1))
    
    if name:
        db = get_db()
        db.execute('INSERT INTO categories (user_id, name, color, weight) VALUES (?,?,?,?)',
                   (session['user_id'], name, color, weight))
        db.commit()
        flash('Category added successfully!', 'success')
    
    return redirect(url_for('categories'))

@app.route('/category/<int:category_id>/delete', methods=['POST'])
@login_required
def delete_category(category_id):
    db = get_db()
    
    # Check if category belongs to user
    category = db.execute('SELECT id FROM categories WHERE id=? AND user_id=?', 
                         (category_id, session['user_id'])).fetchone()
    
    if category:
        # Update tasks to remove category reference
        db.execute('UPDATE tasks SET category_id=NULL WHERE category_id=? AND user_id=?',
                  (category_id, session['user_id']))
        # Delete category
        db.execute('DELETE FROM categories WHERE id=?', (category_id,))
        db.commit()
        flash('Category deleted successfully!', 'success')
    
    return redirect(url_for('categories'))

# Add this new API route for category chart data
@app.route('/api/stats/categories')
@login_required
def stats_categories():
    db = get_db()
    rows = db.execute('''
        SELECT 
            COALESCE(c.name, 'No Category') as category,
            COUNT(t.id) as count
        FROM tasks t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.user_id=?
        GROUP BY t.category_id
    ''', (session['user_id'],)).fetchall()
    return jsonify({r['category']: r['count'] for r in rows})

# ================= TASKS =================

@app.route('/tasks')
@login_required
def tasks():
    db = get_db()
    
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    priority_filter = request.args.get('priority', '')
    category_filter = request.args.get('category', '')
    
    # Build base query
    query = '''
        SELECT t.*, c.name as category_name, c.color, IFNULL(c.weight, 1) as weight
        FROM tasks t 
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.user_id=?
    '''
    params = [session['user_id']]
    
    # Apply filters
    if status_filter == 'pending':
        query += ' AND t.completed=0'
    elif status_filter == 'completed':
        query += ' AND t.completed=1'
    elif status_filter == 'overdue':
        query += ' AND t.completed=0 AND t.overdue=1'
    
    if priority_filter:
        query += ' AND t.priority=?'
        params.append(priority_filter)
    
    if category_filter:
        query += ' AND t.category_id=?'
        params.append(int(category_filter))
    
    query += ' ORDER BY t.completed ASC, t.deadline ASC'
    
    tasks = db.execute(query, params).fetchall()
    
    # Calculate urgency for each task
    task_list = []
    for task in tasks:
        task_dict = dict(task)
        task_dict['urgency'] = calculate_urgency(task_dict)
        task_list.append(task_dict)

    # Sort by urgency (only for pending tasks)
    pending_tasks = [t for t in task_list if t['completed'] == 0]
    completed_tasks = [t for t in task_list if t['completed'] == 1]
    
    pending_tasks.sort(key=lambda x: -x['urgency'])
    task_list = pending_tasks + completed_tasks
    
    categories = db.execute('SELECT * FROM categories WHERE user_id=?', 
                           (session['user_id'],)).fetchall()
    
    return render_template('tasks.html', 
                          tasks=task_list, 
                          categories=categories,
                          current_filters={
                              'status': status_filter,
                              'priority': priority_filter,
                              'category': category_filter
                          })

@app.route('/task/add', methods=['POST'])
@login_required
def add_task():
    title = request.form.get('title', '').strip()
    category_id = request.form.get('category_id')
    priority = request.form.get('priority', 'Medium')
    risk = request.form.get('risk', 'Normal')
    deadline = request.form.get('deadline')
    
    if not title:
        return redirect(request.referrer or url_for('tasks'))
    
    db = get_db()
    if category_id == '':
        category_id = None
    
    db.execute('''
        INSERT INTO tasks (user_id, category_id, title, priority, risk, deadline)
        VALUES (?,?,?,?,?,?)
    ''', (session['user_id'], category_id, title, priority, risk, deadline))
    db.commit()
    
    return redirect(request.referrer or url_for('tasks'))

@app.route('/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    db = get_db()
    
    task = db.execute('SELECT completed FROM tasks WHERE id=? AND user_id=?', 
                     (task_id, session['user_id'])).fetchone()
    
    if task:
        new_status = 1 if task['completed'] == 0 else 0
        db.execute('UPDATE tasks SET completed=? WHERE id=?', (new_status, task_id))
        db.commit()
    
    return redirect(request.referrer or url_for('tasks'))

@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    db = get_db()
    db.execute('DELETE FROM tasks WHERE id=? AND user_id=?', (task_id, session['user_id']))
    db.commit()
    return redirect(request.referrer or url_for('tasks'))

# ================= DASHBOARD =================

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    
    tasks = db.execute('''
        SELECT t.*, c.name as category_name, c.color, IFNULL(c.weight, 1) as weight
        FROM tasks t 
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.user_id=? AND t.completed=0
    ''', (session['user_id'],)).fetchall()
    
    task_list = []
    for task in tasks:
        task_dict = dict(task)
        task_dict['urgency'] = calculate_urgency(task_dict)
        task_list.append(task_dict)
    
    task_list.sort(key=lambda x: -x['urgency'])
    top_tasks = task_list[:5]
    
    stats = db.execute('''
        SELECT 
            SUM(CASE WHEN completed=0 THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN completed=1 THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN overdue=1 THEN 1 ELSE 0 END) as overdue,
            COUNT(*) as total
        FROM tasks WHERE user_id=?
    ''', (session['user_id'],)).fetchone()

    categories = db.execute('SELECT * FROM categories WHERE user_id=? ORDER BY weight DESC',
                            (session['user_id'],)).fetchall()
    
    return render_template('dashboard.html', 
                          tasks=top_tasks, 
                          stats=stats,
                          categories=categories,
                          today=date.today())

# ================= STATISTICS PAGE =================

@app.route('/statistics')
@login_required
def statistics():
    return render_template('statistics.html')

@app.route('/api/stats/priority')
@login_required
def stats_priority():
    db = get_db()
    rows = db.execute('''
        SELECT priority, COUNT(*) as count 
        FROM tasks
        WHERE user_id=? 
        GROUP BY priority
    ''', (session['user_id'],)).fetchall()
    return jsonify({r['priority']: r['count'] for r in rows})

@app.route('/api/stats/weekly')
@login_required
def stats_weekly():
    db = get_db()
    rows = db.execute('''
        SELECT 
            CASE strftime('%w', created_at)
                WHEN '0' THEN 'Sun'
                WHEN '1' THEN 'Mon'
                WHEN '2' THEN 'Tue'
                WHEN '3' THEN 'Wed'
                WHEN '4' THEN 'Thu'
                WHEN '5' THEN 'Fri'
                WHEN '6' THEN 'Sat'
            END as day,
            COUNT(*) as count
        FROM tasks 
        WHERE user_id=? AND completed=1
        GROUP BY strftime('%w', created_at)
        ORDER BY strftime('%w', created_at)
    ''', (session['user_id'],)).fetchall()
    return jsonify({r['day']: r['count'] for r in rows})

@app.route('/api/stats/completion')
@login_required
def stats_completion():
    db = get_db()
    rows = db.execute('''
        SELECT 
            strftime('%Y-%m', created_at) as month,
            COUNT(*) as total,
            SUM(CASE WHEN completed=1 THEN 1 ELSE 0 END) as completed
        FROM tasks 
        WHERE user_id=?
        GROUP BY strftime('%Y-%m', created_at)
        ORDER BY month DESC
        LIMIT 6
    ''', (session['user_id'],)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/stats/urgency')
@login_required
def stats_urgency():
    db = get_db()
    
    # Get tasks with urgency scores
    tasks = db.execute('''
        SELECT t.*, IFNULL(c.weight, 1) as weight
        FROM tasks t 
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.user_id=?
    ''', (session['user_id'],)).fetchall()
    
    # Calculate urgency for each
    urgency_scores = []
    for task in tasks:
        task_dict = dict(task)
        urgency_scores.append(calculate_urgency(task_dict))
    
    # Group into ranges
    ranges = {
        '0-10': 0,
        '11-20': 0,
        '21-30': 0,
        '31-40': 0,
        '41+': 0
    }
    
    for score in urgency_scores:
        if score <= 10:
            ranges['0-10'] += 1
        elif score <= 20:
            ranges['11-20'] += 1
        elif score <= 30:
            ranges['21-30'] += 1
        elif score <= 40:
            ranges['31-40'] += 1
        else:
            ranges['41+'] += 1
    
    return jsonify({
        'labels': list(ranges.keys()),
        'values': list(ranges.values())
    })

# ================= GROUPS PAGE =================

@app.route('/groups')
@login_required
def groups():
    db = get_db()
    
    groups = db.execute('''
        SELECT g.*, gm.role 
        FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = ?
    ''', (session['user_id'],)).fetchall()
    
    invites = db.execute('''
        SELECT gi.*, g.name as group_name, u.username as inviter_name
        FROM group_invites gi
        JOIN groups g ON gi.group_id = g.id
        JOIN users u ON gi.inviter_id = u.id
        WHERE gi.invitee_id = ? AND gi.status = 'pending'
    ''', (session['user_id'],)).fetchall()
    
    return render_template('groups.html', groups=groups, invites=invites)

@app.route('/group/create', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name', '').strip()
    
    if name:
        db = get_db()
        cursor = db.execute('INSERT INTO groups (name, owner_id) VALUES (?,?)',
                           (name, session['user_id']))
        group_id = cursor.lastrowid
        db.execute('INSERT INTO group_members (group_id, user_id, role) VALUES (?,?,?)',
                   (group_id, session['user_id'], 'admin'))
        db.commit()
    
    return redirect('/groups')

@app.route('/group/invite', methods=['POST'])
@login_required
def invite():
    group_id = request.form.get('group_id')
    username = request.form.get('username', '').strip()
    
    if not username or not group_id:
        return redirect('/groups')
    
    db = get_db()
    
    member = db.execute('SELECT role FROM group_members WHERE group_id=? AND user_id=?',
                       (group_id, session['user_id'])).fetchone()
    
    if member and member['role'] == 'admin':
        user = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
        
        if user and user['id'] != session['user_id']:
            existing = db.execute('SELECT 1 FROM group_members WHERE group_id=? AND user_id=?',
                                 (group_id, user['id'])).fetchone()
            
            pending = db.execute('''SELECT 1 FROM group_invites 
                                  WHERE group_id=? AND invitee_id=? AND status='pending' ''',
                               (group_id, user['id'])).fetchone()
            
            if not existing and not pending:
                db.execute('''INSERT INTO group_invites (group_id, inviter_id, invitee_id) 
                            VALUES (?,?,?)''', (group_id, session['user_id'], user['id']))
                db.commit()
    
    return redirect('/groups')

@app.route('/invite/<int:invite_id>/<action>')
@login_required
def invite_action(invite_id, action):
    db = get_db()
    
    invite = db.execute('SELECT * FROM group_invites WHERE id=? AND invitee_id=?',
                       (invite_id, session['user_id'])).fetchone()
    
    if invite and invite['status'] == 'pending':
        if action == 'accept':
            db.execute('UPDATE group_invites SET status="accepted" WHERE id=?', (invite_id,))
            db.execute('INSERT INTO group_members (group_id, user_id, role) VALUES (?,?,"member")',
                      (invite['group_id'], session['user_id']))
        elif action == 'reject':
            db.execute('UPDATE group_invites SET status="rejected" WHERE id=?', (invite_id,))
        
        db.commit()
    
    return redirect('/groups')

@app.route('/group/<int:group_id>')
@login_required
def group_tasks(group_id):
    db = get_db()
    
    member = db.execute('SELECT role FROM group_members WHERE group_id=? AND user_id=?',
                       (group_id, session['user_id'])).fetchone()
    
    if not member:
        return redirect('/groups')
    
    group = db.execute('SELECT * FROM groups WHERE id=?', (group_id,)).fetchone()
    
    tasks = db.execute('''
        SELECT * FROM group_tasks 
        WHERE group_id=? 
        ORDER BY completed ASC, deadline ASC
    ''', (group_id,)).fetchall()
    
    members = db.execute('''
        SELECT u.username, gm.role 
        FROM group_members gm
        JOIN users u ON gm.user_id = u.id
        WHERE gm.group_id=?
    ''', (group_id,)).fetchall()
    
    return render_template('group_tasks.html', 
                          group=group, 
                          tasks=tasks, 
                          members=members,
                          user_role=member['role'],
                          today=date.today())

@app.route('/group/task/add', methods=['POST'])
@login_required
def add_group_task():
    group_id = request.form.get('group_id')
    title = request.form.get('title', '').strip()
    priority = request.form.get('priority', 'Medium')
    risk = request.form.get('risk', 'Normal')
    deadline = request.form.get('deadline')
    
    if not title or not group_id:
        return redirect(f'/group/{group_id}')
    
    db = get_db()
    member = db.execute('SELECT 1 FROM group_members WHERE group_id=? AND user_id=?',
                       (group_id, session['user_id'])).fetchone()
    
    if member:
        db.execute('''
            INSERT INTO group_tasks (group_id, title, priority, risk, deadline)
            VALUES (?,?,?,?,?)
        ''', (group_id, title, priority, risk, deadline))
        db.commit()
    
    return redirect(f'/group/{group_id}')

@app.route('/group/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_group_task(task_id):
    db = get_db()
    
    task = db.execute('SELECT group_id FROM group_tasks WHERE id=?', (task_id,)).fetchone()
    if task:
        member = db.execute('SELECT role FROM group_members WHERE group_id=? AND user_id=?',
                           (task['group_id'], session['user_id'])).fetchone()
        if member and member['role'] == 'admin':
            db.execute('DELETE FROM group_tasks WHERE id=?', (task_id,))
            db.commit()
    
    return redirect(request.referrer or f'/group/{task["group_id"]}')

@app.route('/group/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_group_task(task_id):
    db = get_db()
    
    # Get the task and group info
    task = db.execute('SELECT group_id, completed FROM group_tasks WHERE id=?', (task_id,)).fetchone()
    if not task:
        return redirect('/groups')
    
    # Check if user is a member of the group
    member = db.execute('SELECT 1 FROM group_members WHERE group_id=? AND user_id=?',
                       (task['group_id'], session['user_id'])).fetchone()
    
    if not member:
        return redirect('/groups')
    
    # Toggle completion status
    new_status = 1 if task['completed'] == 0 else 0
    db.execute('UPDATE group_tasks SET completed=? WHERE id=?', (new_status, task_id))
    db.commit()
    
    return redirect(f'/group/{task["group_id"]}')

# ================= ERROR HANDLERS =================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db = get_db()
    db.rollback()
    return render_template('500.html'), 500

# ================= BACKGROUND TASK =================

def overdue_checker():
    """Check for overdue tasks periodically"""
    while True:
        try:
            with app.app_context():
                db = get_db()
                db.execute('''
                    UPDATE tasks 
                    SET overdue=1 
                    WHERE completed=0 
                    AND date(deadline) < date('now')
                    AND overdue=0
                ''')
                
                db.execute('''
                    UPDATE tasks 
                    SET overdue=0 
                    WHERE completed=0 
                    AND date(deadline) >= date('now')
                    AND overdue=1
                ''')
                
                db.commit()
        except Exception as e:
            print(f"Error in overdue_checker: {e}")
        
        time.sleep(3600)

# ================= RUN =================

if __name__ == '__main__':
    init_db()
    threading.Thread(target=overdue_checker, daemon=True).start()
    app.run(debug=True, port=5000)