import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.permanent_session_lifetime = timedelta(days=30)  # Session lasts for 30 days

FIREBASE_URL = os.getenv("FIREBASE_URL")

firebase_creds = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
    "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN"),
}

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_creds)
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_URL})

TEAMS = [
    "planning", "challenge", "media", "video",
    "design", "sponsoring", "funds", "logistics"
]

def get_members():
    ref = db.reference("members")
    members = ref.get()
    return members or []

def get_team_members(team):
    members = get_members()
    return [member for member in members if team in member.get("team", [])]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def team_required():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return redirect(url_for('login', next=request.url))
            
            team = kwargs.get('team')
            if not team:
                return redirect(url_for('home'))
            
            user_teams = session.get('teams', [])
            if team not in user_teams:
                return render_template('unauthorized.html'), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        members = get_members()
        user = next((m for m in members if m.get('username') == username and m.get('Password') == password), None)
        
        if user:
            session.permanent = True
            session['username'] = user['username']
            session['fullName'] = user['fullName']
            session['teams'] = user['team']
            
            if user['team']:
                return redirect(url_for('dashboard', team=user['team'][0]))
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def get_tasks(team):
    ref = db.reference(team)
    tasks = ref.get()
    return tasks or {}

def get_resources(team):
    ref = db.reference(f"resources/{team}")
    resources = ref.get()
    return resources or {}

@app.route('/')
@login_required
def home():
    if 'teams' in session and session['teams']:
        return redirect(url_for('dashboard', team=session['teams'][0]))
    return render_template('home.html')

@app.route('/dashboard/<team>')
@login_required
@team_required()
def dashboard(team):
    tasks = get_tasks(team)
    resources = get_resources(team)
    assignees = [member['fullName'] for member in get_team_members(team)]

    for task_id, task in tasks.items():
        if 'due_date' in task and task['due_date']:
            try:
                due_date = datetime.fromtimestamp(int(task['due_date']) / 1000)
                task['formatted_due_date'] = due_date.strftime('%Y-%m-%d')
                task['is_past_due'] = due_date < datetime.now()
            except:
                task['formatted_due_date'] = 'N/A'
                task['is_past_due'] = False
        else:
            task['formatted_due_date'] = None

    status_filter = request.args.get('status')
    assignee_filter = request.args.get('assignee')
    date_filter = request.args.get('date_filter')

    filtered_tasks = {}
    for task_id, task in tasks.items():
        include = True

        if status_filter and task.get('status') != status_filter:
            include = False

        if assignee_filter and assignee_filter not in task.get('assignees', []):
            include = False

        if date_filter:
            due_ts = task.get('due_date')
            if due_ts:
                due_date = datetime.fromtimestamp(int(due_ts) / 1000)
                today = datetime.now()

                if date_filter == 'week':
                    end_of_week = today + timedelta(days=(6 - today.weekday()))
                    if not (today.date() <= due_date.date() <= end_of_week.date()):
                        include = False
                elif date_filter == 'month':
                    end_of_month = today.replace(day=28) + timedelta(days=4)
                    end_of_month = end_of_month - timedelta(days=end_of_month.day)
                    if not (today.date() <= due_date.date() <= end_of_month.date()):
                        include = False
                elif date_filter == 'overdue':
                    if due_date.date() >= today.date():
                        include = False
            else:
                include = False

        if include:
            filtered_tasks[task_id] = task

    sorted_tasks = dict(
        sorted(
            filtered_tasks.items(),
            key=lambda item: (item[1].get('due_date') is None, item[1].get('due_date', float('inf')))
        )
    )

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

def get_tasks(team):
    ref = db.reference(team)
    tasks = ref.get()
    return tasks or {}

def get_resources(team):
    ref = db.reference(f"resources/{team}")
    resources = ref.get()
    return resources or {}

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

    ref = db.reference(f"{team}/{task_id}")
    ref.set(task_data)

    return jsonify({'success': True, 'task_id': task_id})

@app.route('/api/tasks/<team>/<task_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_task(team, task_id):
    if request.method == 'PUT':
        data = request.get_json()
        ref = db.reference(f"{team}/{task_id}")
        
        # Create a filtered update data that excludes due_date if it's NaN or None
        update_data = {}
        for key, value in data.items():
            if key == 'due_date':
                if value and value != 'NaN':  # Only include if it has a valid value
                    update_data[key] = value
                # else: skip this field entirely
            else:
                update_data[key] = value
                
        ref.update(update_data)
        return jsonify({'success': True})

    elif request.method == 'DELETE':
        ref = db.reference(f"{team}/{task_id}")
        ref.delete()
        return jsonify({'success': True})

@app.route('/api/resources/<team>', methods=['POST'])
@login_required

def create_resource(team):
    data = request.get_json()

    timestamp = int(datetime.now().timestamp() * 1000)
    resource_id = str(timestamp)

    resource_data = {
        'name': data.get('name', ''),
        'url': data.get('url', ''),
        'team': team,
        'date_created': timestamp
    }

    ref = db.reference(f"resources/{team}/{resource_id}")
    ref.set(resource_data)

    return jsonify({'success': True, 'resource_id': resource_id})

@app.route('/api/resources/<team>/<resource_id>', methods=['PUT', 'DELETE'])
@login_required

def manage_resource(team, resource_id):
    if request.method == 'PUT':
        data = request.get_json()
        ref = db.reference(f"resources/{team}/{resource_id}")
        ref.update(data)
        return jsonify({'success': True})

    elif request.method == 'DELETE':
        ref = db.reference(f"resources/{team}/{resource_id}")
        ref.delete()
        return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)