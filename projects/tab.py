from nicegui import ui, app
from datetime import datetime


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
