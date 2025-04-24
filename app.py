import os
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
TEAMS = [
    "planning", "challenge", "media", "video",
    "design", "sponsoring", "funds", "logistics"
]
SESSION_LIFETIME_DAYS = 30

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.permanent_session_lifetime = timedelta(days=SESSION_LIFETIME_DAYS)

# Firebase initialization
def initialize_firebase():
    if not firebase_admin._apps:
        firebase_creds = {
            key.replace("FIREBASE_", "").lower(): os.getenv(f"FIREBASE_{key}")
            for key in [
                "TYPE", "PROJECT_ID", "PRIVATE_KEY_ID", "PRIVATE_KEY",
                "CLIENT_EMAIL", "CLIENT_ID", "AUTH_URI", "TOKEN_URI",
                "AUTH_PROVIDER_CERT_URL", "CLIENT_CERT_URL", "UNIVERSE_DOMAIN"
            ]
        }
        firebase_creds["private_key"] = firebase_creds["private_key"].replace("\\n", "\n")
        
        cred = credentials.Certificate(firebase_creds)
        firebase_admin.initialize_app(cred, {"databaseURL": os.getenv("FIREBASE_URL")})

initialize_firebase()

# Helper functions
def get_db_reference(path):
    return db.reference(path)

def get_members():
    members = get_db_reference("members").get()
    return members or []

def get_team_members(team):
    return [member for member in get_members() if team in member.get("team", [])]

def format_due_date(task):
    if 'due_date' not in task or not task['due_date']:
        task['formatted_due_date'] = None
        task['is_past_due'] = False
        return
    
    try:
        due_date = datetime.fromtimestamp(int(task['due_date']) / 1000)
        task['formatted_due_date'] = due_date.strftime('%Y-%m-%d')
        task['is_past_due'] = due_date < datetime.now()
    except (ValueError, TypeError):
        task['formatted_due_date'] = 'N/A'
        task['is_past_due'] = False

def filter_tasks(tasks, status_filter, assignee_filter, date_filter):
    filtered_tasks = {}
    today = datetime.now()
    
    for task_id, task in tasks.items():
        # Status filter
        if status_filter and task.get('status') != status_filter:
            continue
            
        # Assignee filter
        if assignee_filter and assignee_filter not in task.get('assignees', []):
            continue
            
        # No date filter - include all matching tasks
        if not date_filter:
            filtered_tasks[task_id] = task
            continue
            
        # Date filtering logic
        due_ts = task.get('due_date')
        if not due_ts:
            continue
            
        try:
            due_date = datetime.fromtimestamp(int(due_ts) / 1000)
        except (ValueError, TypeError):
            continue
            
        if date_filter == 'week':
            end_of_week = today + timedelta(days=(6 - today.weekday()))
            if not (today.date() <= due_date.date() <= end_of_week.date()):
                continue
        elif date_filter == 'month':
            end_of_month = today.replace(day=28) + timedelta(days=4)
            end_of_month = end_of_month - timedelta(days=end_of_month.day)
            if not (today.date() <= due_date.date() <= end_of_month.date()):
                continue
        elif date_filter == 'overdue':
            # Only include overdue tasks that aren't in "ideas" or "done" status
            if due_date.date() >= today.date() or task.get('status') in ["ideas", "done"]:
                continue
                
        filtered_tasks[task_id] = task
        
    return filtered_tasks

def sort_tasks(tasks):
    return dict(
        sorted(
            tasks.items(),
            key=lambda item: (item[1].get('due_date') is None, item[1].get('due_date', float('inf')))
        )
    )

# Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def team_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        team = kwargs.get('team')
        if not team or team not in session.get('teams', []):
            return render_template('unauthorized.html'), 403
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = next(
            (m for m in get_members() 
             if m.get('username') == username and m.get('Password') == password),
            None
        )
        
        if user:
            session.update({
                'permanent': True,
                'username': user['username'],
                'fullName': user['fullName'],
                'teams': user['team']
            })
            
            if user['team']:
                return redirect(url_for('dashboard', team=user['team'][0]))
            return redirect(url_for('home'))
        
        flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    if session.get('teams'):
        return redirect(url_for('dashboard', team=session['teams'][0]))
    return render_template('home.html')

@app.route('/dashboard/<team>')
@login_required
@team_required
def dashboard(team):
    tasks = get_db_reference(team).get() or {}
    resources = get_db_reference(f"resources/{team}").get() or {}
    assignees = [member['fullName'] for member in get_team_members(team)]

    for task in tasks.values():
        format_due_date(task)

    status_filter = request.args.get('status')
    assignee_filter = request.args.get('assignee')
    date_filter = request.args.get('date_filter')

    filtered_tasks = filter_tasks(tasks, status_filter, assignee_filter, date_filter)
    sorted_tasks = sort_tasks(filtered_tasks)

    return render_template(
        'dashboard.html',
        team=team,
        teams=session.get('teams', []),
        tasks=sorted_tasks,
        resources=resources,
        assignees=assignees,
        current_status=status_filter,
        current_assignee=assignee_filter,
        current_date_filter=date_filter,
        fullName=session.get('fullName', '')
    )

@app.route('/api/tasks/<team>', methods=['POST'])
@login_required
def create_task(team):
    data = request.get_json()
    timestamp = int(datetime.now().timestamp() * 1000)
    task_id = str(timestamp)

    task_data = {
        'name': data.get('name', ''),
        'status': data.get('status', 'on stand by'),
        'date_created': str(timestamp)
    }

    if data.get('description'):
        task_data['description'] = data['description']

    if data.get('due_date') and data['due_date'] != 'NaN':
        task_data['due_date'] = data['due_date']

    if data.get('assignees'):
        task_data['assignees'] = data['assignees']

    get_db_reference(f"{team}/{task_id}").set(task_data)

    return jsonify({'success': True, 'task_id': task_id})

@app.route('/api/tasks/<team>/<task_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_task(team, task_id):
    ref = get_db_reference(f"{team}/{task_id}")
    
    if request.method == 'PUT':
        data = request.get_json()
        update_data = {
            k: v for k, v in data.items() 
            if not (k == 'due_date' and (not v or v == 'NaN'))
        }
        ref.update(update_data)
        return jsonify({'success': True})

    elif request.method == 'DELETE':
        ref.delete()
        return jsonify({'success': True})

@app.route('/api/resources/<team>', methods=['POST'])
@login_required
def create_resource(team):
    data = request.get_json()
    timestamp = int(datetime.now().timestamp() * 1000)
    
    resource_data = {
        'name': data.get('name', ''),
        'url': data.get('url', ''),
        'team': team,
        'date_created': timestamp
    }

    get_db_reference(f"resources/{team}/{timestamp}").set(resource_data)
    return jsonify({'success': True, 'resource_id': timestamp})

@app.route('/api/resources/<team>/<resource_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_resource(team, resource_id):
    ref = get_db_reference(f"resources/{team}/{resource_id}")
    
    if request.method == 'PUT':
        ref.update(request.get_json())
        return jsonify({'success': True})
        
    elif request.method == 'DELETE':
        ref.delete()
        return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')