from nicegui import ui, app


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

                with ui.input('Deadline').classes('flex-grow') as deadline_input:
                    with deadline_input.add_slot('append'):
                        ui.icon('edit_calendar').on('click', lambda: menu.open()).classes('cursor-pointer')
                    with ui.menu() as menu:
                        ui.date(on_change=lambda e: (deadline_input.set_value(e.value), menu.close()))

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
