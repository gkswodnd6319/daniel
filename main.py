"""
═══════════════════════════════════════════════════════════════
  PERSONAL HUB — NiceGUI Dashboard
  
  Tabs:
    1. 🏟️ Matchday   — Live sports schedules (EPL, UCL, LCK, MLB, KBO)
    2. 🎯 Career      — Career goals tracker & roadmap
    3. 🚀 Projects    — Personal project workspace
  
  Run:
    pip install nicegui
    python main.py
    
  Then open http://localhost:8080
═══════════════════════════════════════════════════════════════
"""

from nicegui import ui, app
from datetime import datetime

# ── Shared State (in-memory, swap for SQLite/JSON later) ────
app.storage.general.setdefault('career_goals', [
    {'id': 1, 'title': 'Learn NiceGUI deeply', 'category': 'skill', 'status': 'in_progress', 'deadline': '2026-05-01', 'notes': 'Build personal hub project'},
    {'id': 2, 'title': 'Get promoted to Senior DS', 'category': 'career', 'status': 'not_started', 'deadline': '2026-12-31', 'notes': ''},
    {'id': 3, 'title': 'Publish a side project', 'category': 'project', 'status': 'not_started', 'deadline': '2026-08-01', 'notes': 'Open source on GitHub'},
])

app.storage.general.setdefault('projects', [
    {'id': 1, 'name': 'Personal Hub App', 'description': 'NiceGUI-based personal dashboard', 'status': 'active', 'tech': 'Python, NiceGUI', 'created': '2026-04-01', 'tasks': [
        {'text': 'Set up NiceGUI project structure', 'done': True},
        {'text': 'Build sports schedule tab', 'done': False},
        {'text': 'Add career goals tracker', 'done': False},
        {'text': 'Deploy to Cloud Run', 'done': False},
    ]},
])

# ── Theme / Dark Mode ──────────────────────────────────────
ui.dark_mode().enable()

# ── Custom CSS ─────────────────────────────────────────────
ui.add_head_html('''
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    body { font-family: 'Outfit', sans-serif !important; }
    .mono { font-family: 'JetBrains Mono', monospace !important; }
    
    .q-tab { text-transform: none !important; font-weight: 600 !important; letter-spacing: 0 !important; }
    .q-card { border-radius: 12px !important; }
    
    .goal-card:hover { transform: translateY(-2px); transition: all 0.2s; }
    .project-card:hover { transform: translateY(-2px); transition: all 0.2s; }
    
    .status-badge { 
        padding: 2px 10px; border-radius: 20px; font-size: 11px; 
        font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
    }
    .badge-live { background: #ff1744; color: white; }
    .badge-scheduled { background: #00e676; color: #0a0a0f; }
    .badge-ft { background: #555570; color: #e8e8f0; }
    
    .league-pl { background: #3d195b; color: white; }
    .league-ucl { background: #071d6b; color: white; }
    .league-lck { background: #c89b3c; color: #0a0a0f; }
    .league-mlb { background: #002d72; color: white; }
    .league-kbo { background: #c8102e; color: white; }
    
    .section-title {
        font-size: 13px; font-weight: 600; color: #8888a0;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 0.05em; text-transform: uppercase;
    }
</style>
''')


# ═══════════════════════════════════════════════════════════
#  TAB 1: MATCHDAY — Sports Schedules
# ═══════════════════════════════════════════════════════════
def build_sports_tab():
    """Sports schedule tab with league filters."""
    from sports_data import get_all_matches, LEAGUE_FILTERS
    
    selected_league = {'value': 'all'}
    selected_status = {'value': 'all'}
    
    with ui.column().classes('w-full gap-4 p-4'):
        # Header
        ui.label('MATCHDAY').classes('text-3xl font-extrabold')
        ui.label('EPL · UCL · LCK · MLB · KBO').classes('mono text-xs text-gray-500')
        
        # League filter chips
        with ui.row().classes('gap-2 flex-wrap'):
            league_buttons = {}
            for key, info in LEAGUE_FILTERS.items():
                btn = ui.button(
                    info['label'],
                    on_click=lambda k=key: filter_matches(k, None),
                ).props('flat dense rounded').classes('text-xs')
                league_buttons[key] = btn
        
        # Status filter
        with ui.row().classes('gap-2'):
            for status in ['all', 'live', 'upcoming', 'completed']:
                ui.button(
                    status.upper(),
                    on_click=lambda s=status: filter_matches(None, s),
                ).props('flat dense rounded outline').classes('text-xs')
        
        # Match cards container
        matches_container = ui.column().classes('w-full gap-2')
        
        def filter_matches(league=None, status=None):
            if league is not None:
                selected_league['value'] = league
            if status is not None:
                selected_status['value'] = status
            render_matches()
        
        def render_matches():
            matches_container.clear()
            matches = get_all_matches()
            
            # Apply filters
            filtered = matches
            if selected_league['value'] != 'all':
                filtered = [m for m in filtered if m['league'] == selected_league['value']]
            if selected_status['value'] == 'live':
                filtered = [m for m in filtered if m['status'] == 'LIVE']
            elif selected_status['value'] == 'upcoming':
                filtered = [m for m in filtered if m['status'] == 'SCHEDULED']
            elif selected_status['value'] == 'completed':
                filtered = [m for m in filtered if m['status'] == 'FT']
            
            if not filtered:
                with matches_container:
                    ui.label('No matches found').classes('text-gray-500 text-center py-8')
                return
            
            # Group by date
            from itertools import groupby
            filtered.sort(key=lambda m: m['date'])
            for date_str, group in groupby(filtered, key=lambda m: m['date'][:10]):
                with matches_container:
                    ui.label(date_str).classes('section-title mt-4')
                    for match in group:
                        build_match_card(match)
        
        def build_match_card(match):
            league_class = {
                'Premier League': 'league-pl',
                'Champions League': 'league-ucl',
                'LCK': 'league-lck',
                'MLB': 'league-mlb',
                'KBO': 'league-kbo',
            }.get(match['league'], '')
            
            status_class = {
                'LIVE': 'badge-live',
                'SCHEDULED': 'badge-scheduled',
                'FT': 'badge-ft',
            }.get(match['status'], 'badge-ft')
            
            with ui.card().classes('w-full p-3'):
                # Top row: league badge + status
                with ui.row().classes('w-full justify-between items-center'):
                    ui.badge(match['league_short']).classes(f'{league_class} text-xs')
                    
                    status_text = match['status']
                    if match['status'] == 'LIVE':
                        status_text = f"🔴 LIVE {match.get('minute', '')}"
                    elif match['status'] == 'SCHEDULED':
                        status_text = match['time']
                    
                    ui.label(status_text).classes(f'mono text-xs')
                
                # Teams + Score
                with ui.row().classes('w-full justify-between items-center py-2'):
                    # Home
                    with ui.column().classes('items-start'):
                        ui.label(match['home']).classes('font-bold')
                    
                    # Score or time
                    if match['status'] in ('LIVE', 'FT'):
                        ui.label(f"{match['score_home']} : {match['score_away']}").classes('mono text-2xl font-extrabold')
                    else:
                        ui.label(match['time']).classes('mono text-lg text-gray-500')
                    
                    # Away
                    with ui.column().classes('items-end'):
                        ui.label(match['away']).classes('font-bold')
                
                # Round info
                ui.label(match.get('round', '')).classes('mono text-xs text-gray-600 text-center w-full')
        
        # Initial render
        render_matches()
        
        # Auto-refresh timer
        ui.timer(60.0, render_matches)


# ═══════════════════════════════════════════════════════════
#  TAB 2: CAREER — Goals & Roadmap
# ═══════════════════════════════════════════════════════════
def build_career_tab():
    """Career goals tracker with kanban-style status."""
    
    with ui.column().classes('w-full gap-4 p-4'):
        ui.label('CAREER GOALS').classes('text-3xl font-extrabold')
        ui.label('Track milestones · Set deadlines · Stay accountable').classes('mono text-xs text-gray-500')
        
        goals_container = ui.column().classes('w-full gap-3')
        
        def render_goals():
            goals_container.clear()
            goals = app.storage.general['career_goals']
            
            status_order = ['in_progress', 'not_started', 'done']
            status_labels = {
                'not_started': ('⬜ Not Started', 'bg-gray-800'),
                'in_progress': ('🔵 In Progress', 'bg-blue-900'),
                'done': ('✅ Done', 'bg-green-900'),
            }
            
            for status in status_order:
                status_goals = [g for g in goals if g['status'] == status]
                if not status_goals:
                    continue
                    
                with goals_container:
                    label, _ = status_labels[status]
                    ui.label(label).classes('section-title mt-2')
                    
                    for goal in status_goals:
                        build_goal_card(goal)
        
        def build_goal_card(goal):
            category_colors = {
                'skill': '#00e676',
                'career': '#448aff',
                'project': '#ff9100',
                'health': '#e040fb',
                'finance': '#ffd740',
            }
            color = category_colors.get(goal.get('category', ''), '#888')
            
            with ui.card().classes('w-full p-4 goal-card'):
                with ui.row().classes('w-full justify-between items-start'):
                    with ui.column().classes('gap-1 flex-grow'):
                        ui.label(goal['title']).classes('font-bold text-lg')
                        if goal.get('notes'):
                            ui.label(goal['notes']).classes('text-sm text-gray-400')
                        with ui.row().classes('gap-2 items-center mt-1'):
                            ui.badge(goal.get('category', 'general')).props(f'color="{color}" text-color="black"').classes('text-xs')
                            if goal.get('deadline'):
                                ui.label(f"📅 {goal['deadline']}").classes('mono text-xs text-gray-500')
                    
                    # Status toggle
                    with ui.column().classes('gap-1'):
                        ui.select(
                            options={'not_started': 'Not Started', 'in_progress': 'In Progress', 'done': 'Done'},
                            value=goal['status'],
                            on_change=lambda e, g=goal: update_goal_status(g, e.value),
                        ).props('dense outlined').classes('text-xs').style('min-width: 130px')
                        
                        ui.button(
                            icon='delete', 
                            on_click=lambda g=goal: delete_goal(g),
                        ).props('flat dense round color=red-4 size=sm')
        
        def update_goal_status(goal, new_status):
            goals = app.storage.general['career_goals']
            for g in goals:
                if g['id'] == goal['id']:
                    g['status'] = new_status
            app.storage.general['career_goals'] = goals
            render_goals()
        
        def delete_goal(goal):
            goals = app.storage.general['career_goals']
            goals = [g for g in goals if g['id'] != goal['id']]
            app.storage.general['career_goals'] = goals
            render_goals()
        
        # Add new goal form
        ui.separator()
        ui.label('ADD NEW GOAL').classes('section-title')
        
        with ui.card().classes('w-full p-4'):
            title_input = ui.input('Goal title', placeholder='e.g. Master Kubernetes').classes('w-full')
            
            with ui.row().classes('w-full gap-3'):
                category_select = ui.select(
                    options={'skill': 'Skill', 'career': 'Career', 'project': 'Project', 'health': 'Health', 'finance': 'Finance'},
                    value='skill',
                    label='Category',
                ).props('dense outlined').classes('flex-grow')
                
                deadline_input = ui.input('Deadline', placeholder='YYYY-MM-DD').classes('flex-grow')
            
            notes_input = ui.textarea('Notes (optional)').classes('w-full').props('rows=2')
            
            def add_goal():
                if not title_input.value:
                    ui.notify('Please enter a goal title', type='warning')
                    return
                
                goals = app.storage.general['career_goals']
                new_id = max([g['id'] for g in goals], default=0) + 1
                goals.append({
                    'id': new_id,
                    'title': title_input.value,
                    'category': category_select.value,
                    'status': 'not_started',
                    'deadline': deadline_input.value or '',
                    'notes': notes_input.value or '',
                })
                app.storage.general['career_goals'] = goals
                
                # Clear form
                title_input.value = ''
                deadline_input.value = ''
                notes_input.value = ''
                
                ui.notify(f'Goal added: {goals[-1]["title"]}', type='positive')
                render_goals()
            
            ui.button('Add Goal', icon='add', on_click=add_goal).props('color=primary')
        
        render_goals()


# ═══════════════════════════════════════════════════════════
#  TAB 3: PROJECTS — Personal Project Workspace
# ═══════════════════════════════════════════════════════════
def build_projects_tab():
    """Personal projects with task lists."""
    
    with ui.column().classes('w-full gap-4 p-4'):
        ui.label('PROJECTS').classes('text-3xl font-extrabold')
        ui.label('Side projects · Ideas · Build log').classes('mono text-xs text-gray-500')
        
        projects_container = ui.column().classes('w-full gap-4')
        
        def render_projects():
            projects_container.clear()
            projects = app.storage.general['projects']
            
            if not projects:
                with projects_container:
                    ui.label('No projects yet. Start one below!').classes('text-gray-500 py-8 text-center')
                return
            
            for project in projects:
                with projects_container:
                    build_project_card(project)
        
        def build_project_card(project):
            status_colors = {
                'active': 'green',
                'paused': 'orange',
                'idea': 'blue',
                'done': 'gray',
            }
            color = status_colors.get(project.get('status', 'idea'), 'gray')
            
            tasks = project.get('tasks', [])
            done_count = sum(1 for t in tasks if t.get('done'))
            total_count = len(tasks)
            progress = done_count / total_count if total_count > 0 else 0
            
            with ui.card().classes('w-full p-4 project-card'):
                # Header
                with ui.row().classes('w-full justify-between items-start'):
                    with ui.column().classes('gap-1'):
                        ui.label(project['name']).classes('font-bold text-xl')
                        ui.label(project.get('description', '')).classes('text-sm text-gray-400')
                        with ui.row().classes('gap-2 mt-1'):
                            ui.badge(project.get('status', 'idea').upper()).props(f'color={color}').classes('text-xs')
                            ui.label(f"🛠️ {project.get('tech', '')}").classes('mono text-xs text-gray-500')
                            ui.label(f"📅 {project.get('created', '')}").classes('mono text-xs text-gray-500')
                    
                    with ui.row().classes('gap-1'):
                        ui.button(
                            icon='delete',
                            on_click=lambda p=project: delete_project(p),
                        ).props('flat dense round color=red-4 size=sm')
                
                # Progress bar
                if total_count > 0:
                    ui.label(f'{done_count}/{total_count} tasks').classes('mono text-xs text-gray-500 mt-2')
                    ui.linear_progress(value=progress, show_value=False).props(f'color={color}').classes('mt-1')
                
                # Task list
                ui.separator().classes('my-2')
                
                for i, task in enumerate(tasks):
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.checkbox(
                            value=task.get('done', False),
                            on_change=lambda e, p=project, idx=i: toggle_task(p, idx, e.value),
                        )
                        label_class = 'line-through text-gray-600' if task.get('done') else ''
                        ui.label(task['text']).classes(f'flex-grow {label_class}')
                        ui.button(
                            icon='close',
                            on_click=lambda p=project, idx=i: remove_task(p, idx),
                        ).props('flat dense round size=xs color=gray')
                
                # Add task input
                with ui.row().classes('w-full mt-2 gap-2'):
                    task_input = ui.input(placeholder='Add a task...').classes('flex-grow').props('dense')
                    
                    def add_task(p=project, inp=task_input):
                        if not inp.value:
                            return
                        projects = app.storage.general['projects']
                        for proj in projects:
                            if proj['id'] == p['id']:
                                proj.setdefault('tasks', []).append({'text': inp.value, 'done': False})
                        app.storage.general['projects'] = projects
                        inp.value = ''
                        render_projects()
                    
                    ui.button(icon='add', on_click=add_task).props('dense flat color=primary')
        
        def toggle_task(project, task_idx, value):
            projects = app.storage.general['projects']
            for p in projects:
                if p['id'] == project['id']:
                    p['tasks'][task_idx]['done'] = value
            app.storage.general['projects'] = projects
            render_projects()
        
        def remove_task(project, task_idx):
            projects = app.storage.general['projects']
            for p in projects:
                if p['id'] == project['id']:
                    p['tasks'].pop(task_idx)
            app.storage.general['projects'] = projects
            render_projects()
        
        def delete_project(project):
            projects = app.storage.general['projects']
            projects = [p for p in projects if p['id'] != project['id']]
            app.storage.general['projects'] = projects
            render_projects()
        
        # New project form
        ui.separator()
        ui.label('START NEW PROJECT').classes('section-title')
        
        with ui.card().classes('w-full p-4'):
            name_input = ui.input('Project name', placeholder='e.g. ROAS Prediction API').classes('w-full')
            desc_input = ui.input('Description', placeholder='One-liner about the project').classes('w-full')
            
            with ui.row().classes('w-full gap-3'):
                tech_input = ui.input('Tech stack', placeholder='e.g. Python, FastAPI').classes('flex-grow')
                status_select = ui.select(
                    options={'idea': 'Idea', 'active': 'Active', 'paused': 'Paused'},
                    value='active',
                    label='Status',
                ).props('dense outlined').classes('flex-grow')
            
            def add_project():
                if not name_input.value:
                    ui.notify('Please enter a project name', type='warning')
                    return
                
                projects = app.storage.general['projects']
                new_id = max([p['id'] for p in projects], default=0) + 1
                projects.append({
                    'id': new_id,
                    'name': name_input.value,
                    'description': desc_input.value or '',
                    'status': status_select.value,
                    'tech': tech_input.value or '',
                    'created': datetime.now().strftime('%Y-%m-%d'),
                    'tasks': [],
                })
                app.storage.general['projects'] = projects
                
                name_input.value = ''
                desc_input.value = ''
                tech_input.value = ''
                
                ui.notify(f'Project created: {projects[-1]["name"]}', type='positive')
                render_projects()
            
            ui.button('Create Project', icon='rocket_launch', on_click=add_project).props('color=primary')
        
        render_projects()


# ═══════════════════════════════════════════════════════════
#  MAIN PAGE LAYOUT
# ═══════════════════════════════════════════════════════════
@ui.page('/')
def main_page():
    # Header
    with ui.header().classes('items-center justify-between').style(
        'background: linear-gradient(135deg, #0a0a0f 0%, #12121a 100%); '
        'border-bottom: 1px solid #2a2a3a;'
    ):
        ui.label('PERSONAL HUB').classes('text-xl font-extrabold tracking-tight').style(
            'background: linear-gradient(135deg, #e8e8f0 20%, #00e676 100%); '
            '-webkit-background-clip: text; -webkit-text-fill-color: transparent;'
        )
        
        ui.label(datetime.now().strftime('%a, %b %d %Y')).classes('mono text-xs text-gray-500')
    
    # Tab navigation
    with ui.tabs().classes('w-full').props('dense active-color=green indicator-color=green') as tabs:
        sports_tab = ui.tab('matchday', label='🏟️ Matchday', icon=None)
        career_tab = ui.tab('career', label='🎯 Career', icon=None)
        projects_tab = ui.tab('projects', label='🚀 Projects', icon=None)
    
    # Tab panels
    with ui.tab_panels(tabs, value=sports_tab).classes('w-full flex-grow'):
        with ui.tab_panel(sports_tab):
            build_sports_tab()
        
        with ui.tab_panel(career_tab):
            build_career_tab()
        
        with ui.tab_panel(projects_tab):
            build_projects_tab()


# ═══════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════
ui.run(
    title='Personal Hub',
    port=8080,
    dark=True,
    storage_secret='personal-hub-secret-key-change-me',
)
