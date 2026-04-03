import re
import os
from datetime import datetime
from nicegui import ui, app, events

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Color palette for companies (cycles if more than available)
COMPANY_COLORS = [
    '#448aff', '#00e676', '#ff9100', '#e040fb', '#ffd740',
    '#ff1744', '#00bcd4', '#76ff03', '#ff6d00', '#d500f9',
    '#1de9b6', '#ffea00', '#651fff', '#f44336', '#00c853',
]


def _parse_resume_text(text: str) -> list[dict]:
    """Best-effort extraction of career entries from resume text.

    Looks for patterns like:
      Company Name | Role Title | Jan 2020 - Mar 2023
      Company Name, Role Title, 2020 - 2023
      Role Title at Company Name (Jan 2020 - Present)
    """
    entries = []
    # Pattern: lines with date ranges like "Jan 2020 - Dec 2023" or "2020 - Present"
    date_pattern = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\.?\s*(\d{4})\s*[-–—to]+\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\.?\s*(\d{4})|(Present|Current|Now))'

    lines = text.split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        match = re.search(date_pattern, line, re.IGNORECASE)
        if not match:
            continue

        start_year = match.group(1)
        end_year = match.group(2) or (match.group(3) if match.group(3) else str(datetime.now().year))
        if end_year.lower() in ('present', 'current', 'now'):
            end_year = str(datetime.now().year)

        # Try to extract month for more precision
        start_month_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s*' + start_year, line, re.IGNORECASE)
        end_month_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s*' + (match.group(2) or ''), line, re.IGNORECASE)

        month_map = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
                     'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'}

        start_month = month_map.get(start_month_match.group(1).lower()[:3], '01') if start_month_match else '01'
        end_month = month_map.get(end_month_match.group(1).lower()[:3], '12') if end_month_match else '12'

        start_date = f"{start_year}-{start_month}-01"
        end_date = f"{end_year}-{end_month}-01"

        # Extract company and role from the text before the date range
        prefix = line[:match.start()].strip().rstrip('|,–—-').strip()

        # Try splitting by common delimiters
        parts = re.split(r'\s*[|,]\s*', prefix)
        parts = [p.strip() for p in parts if p.strip()]

        # Heuristic: role titles usually contain these keywords
        _role_keywords = re.compile(
            r'\b(engineer|developer|manager|director|analyst|scientist|intern|lead|head|vp|cto|ceo|coo|architect|consultant|designer|coordinator|specialist|officer|associate|assistant|fellow|researcher|professor|instructor)\b',
            re.IGNORECASE,
        )

        if len(parts) >= 2:
            # If first part looks like a role and second doesn't, swap
            if _role_keywords.search(parts[0]) and not _role_keywords.search(parts[1]):
                role = parts[0]
                company = parts[1]
            else:
                company = parts[0]
                role = parts[1]
        elif len(parts) == 1:
            # Check previous line for context
            company = parts[0]
            role = ''
            if i > 0:
                prev = lines[i - 1].strip()
                if prev and not re.search(date_pattern, prev, re.IGNORECASE):
                    role = company
                    company = prev
        else:
            company = 'Unknown Company'
            role = ''

        # Clean up common artifacts
        company = re.sub(r'^[-•·\s]+', '', company).strip()
        role = re.sub(r'^[-•·\s]+', '', role).strip()

        if company:
            entries.append({
                'company': company,
                'role': role or 'Role',
                'start': start_date,
                'end': end_date,
            })

    return entries


def _build_timeline_plot(career_entries: list[dict], container):
    """Build a Plotly horizontal bar (Gantt-style) timeline chart."""
    container.clear()

    if not career_entries:
        with container:
            ui.label('No career entries yet. Upload a resume or add entries manually.').classes('text-gray-500 text-center py-8')
        return

    # Assign colors by company
    companies = list(dict.fromkeys(e['company'] for e in career_entries))
    color_map = {c: COMPANY_COLORS[i % len(COMPANY_COLORS)] for i, c in enumerate(companies)}

    # Sort by start date
    sorted_entries = sorted(career_entries, key=lambda e: e['start'])

    import plotly.graph_objects as go

    fig = go.Figure()

    for entry in sorted_entries:
        start = datetime.strptime(entry['start'], '%Y-%m-%d')
        end = datetime.strptime(entry['end'], '%Y-%m-%d')
        color = color_map[entry['company']]
        label = f"{entry['company']}"

        fig.add_trace(go.Bar(
            x=[(end - start).days],
            y=[f"{entry['role']}"],
            base=[start.timestamp() * 1000],
            orientation='h',
            marker=dict(color=color, line=dict(width=0)),
            name=label,
            text=f"{entry['company']}<br>{entry['role']}<br>{entry['start'][:7]} → {entry['end'][:7]}",
            textposition='inside',
            insidetextanchor='middle',
            hovertemplate=(
                f"<b>{entry['company']}</b><br>"
                f"{entry['role']}<br>"
                f"{entry['start'][:7]} → {entry['end'][:7]}<br>"
                f"<extra></extra>"
            ),
            showlegend=label not in [t.name for t in fig.data[:-1]] if fig.data else True,
        ))

    fig.update_layout(
        barmode='stack',
        xaxis=dict(
            type='date',
            title='',
            gridcolor='#2a2a3a',
            tickformat='%Y',
        ),
        yaxis=dict(
            title='',
            autorange='reversed',
            gridcolor='#2a2a3a',
        ),
        plot_bgcolor='#0a0a0f',
        paper_bgcolor='#0a0a0f',
        font=dict(color='#e8e8f0', family='Outfit, sans-serif'),
        margin=dict(l=10, r=10, t=40, b=40),
        height=max(200, len(sorted_entries) * 60 + 80),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='left',
            x=0,
            font=dict(size=11),
        ),
        title=dict(
            text='Career Timeline',
            font=dict(size=16, color='#8888a0', family='JetBrains Mono, monospace'),
            x=0,
            xanchor='left',
        ),
    )

    with container:
        ui.plotly(fig).classes('w-full')

    # Color legend beneath the chart
    with container:
        with ui.row().classes('gap-3 flex-wrap mt-2'):
            for company, color in color_map.items():
                with ui.row().classes('items-center gap-1'):
                    ui.element('div').style(f'width: 12px; height: 12px; border-radius: 2px; background: {color};')
                    ui.label(company).classes('text-xs text-gray-400')


def build_career_tab():
    """Career tab: goals tracker + resume-based career timeline."""

    with ui.column().classes('w-full gap-4 p-4'):
        # ── Sub-tabs: Goals vs Career Path ──
        with ui.tabs().props('dense active-color=green indicator-color=green no-caps').classes('w-full') as career_tabs:
            goals_tab = ui.tab('goals', label='Goals Tracker')
            timeline_tab = ui.tab('timeline', label='Career Path')

        with ui.tab_panels(career_tabs, value=goals_tab).classes('w-full'):
            with ui.tab_panel(goals_tab):
                _build_goals_section()
            with ui.tab_panel(timeline_tab):
                _build_timeline_section()


def _build_timeline_section():
    """Career path timeline: upload resume / paste Notion link, view & edit timeline."""

    with ui.column().classes('w-full gap-4'):
        ui.label('CAREER PATH').classes('text-3xl font-extrabold')
        ui.label('Upload resume or add entries manually').classes('mono text-xs text-gray-500')

        # ── Upload / Link Section ──
        with ui.card().classes('w-full p-4'):
            ui.label('IMPORT CAREER DATA').classes('section-title')

            with ui.tabs().props('dense no-caps').classes('w-full') as import_tabs:
                pdf_tab = ui.tab('pdf', label='Upload PDF')
                notion_tab = ui.tab('notion', label='Notion Link')

            with ui.tab_panels(import_tabs, value=pdf_tab).classes('w-full'):
                with ui.tab_panel(pdf_tab):
                    ui.label('Upload your resume as PDF to auto-extract career history.').classes('text-sm text-gray-400 mb-2')
                    upload_status = ui.label('').classes('text-sm')

                    async def handle_upload(e: events.UploadEventArguments):
                        upload_status.text = 'Parsing PDF...'
                        upload_status.classes(remove='text-red-400 text-green-400', add='text-amber-400')

                        try:
                            import pdfplumber
                            # Save uploaded file
                            file_path = os.path.join(UPLOAD_DIR, e.name)
                            with open(file_path, 'wb') as f:
                                f.write(e.content.read())

                            # Extract text
                            full_text = ''
                            with pdfplumber.open(file_path) as pdf:
                                for page in pdf.pages:
                                    full_text += (page.extract_text() or '') + '\n'

                            if not full_text.strip():
                                upload_status.text = 'Could not extract text from PDF. Try a text-based PDF.'
                                upload_status.classes(remove='text-amber-400 text-green-400', add='text-red-400')
                                return

                            entries = _parse_resume_text(full_text)

                            if not entries:
                                upload_status.text = 'No career entries detected. Try adding manually below.'
                                upload_status.classes(remove='text-amber-400 text-green-400', add='text-red-400')
                                return

                            # Merge with existing (avoid duplicates by company+start)
                            existing = app.storage.general.get('career_timeline', [])
                            existing_keys = {(e['company'], e['start']) for e in existing}
                            new_entries = [e for e in entries if (e['company'], e['start']) not in existing_keys]
                            existing.extend(new_entries)
                            app.storage.general['career_timeline'] = existing

                            upload_status.text = f'Extracted {len(new_entries)} new career entries! ({len(entries)} total found in PDF)'
                            upload_status.classes(remove='text-amber-400 text-red-400', add='text-green-400')

                            _build_timeline_plot(app.storage.general['career_timeline'], timeline_container)
                            _render_entries_list()

                        except Exception as ex:
                            upload_status.text = f'Error parsing PDF: {ex}'
                            upload_status.classes(remove='text-amber-400 text-green-400', add='text-red-400')

                    ui.upload(
                        label='Drop resume PDF here',
                        on_upload=handle_upload,
                        auto_upload=True,
                        max_files=1,
                    ).props('accept=".pdf" flat bordered').classes('w-full')

                with ui.tab_panel(notion_tab):
                    ui.label('Paste a public Notion page URL to extract career data.').classes('text-sm text-gray-400 mb-2')
                    notion_input = ui.input('Notion URL', placeholder='https://notion.so/...').classes('w-full')
                    notion_status = ui.label('').classes('text-sm')

                    async def fetch_notion():
                        url = notion_input.value.strip()
                        if not url:
                            ui.notify('Please enter a Notion URL', type='warning')
                            return

                        notion_status.text = 'Fetching page content...'
                        notion_status.classes(remove='text-red-400 text-green-400', add='text-amber-400')

                        try:
                            import urllib.request
                            # For public Notion pages, fetch the HTML and extract text
                            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                            with urllib.request.urlopen(req, timeout=15) as resp:
                                html = resp.read().decode('utf-8', errors='ignore')

                            # Strip HTML tags to get plain text
                            text = re.sub(r'<[^>]+>', ' ', html)
                            text = re.sub(r'\s+', ' ', text)

                            entries = _parse_resume_text(text)

                            if not entries:
                                notion_status.text = 'No career entries detected from the page. Try adding manually.'
                                notion_status.classes(remove='text-amber-400 text-green-400', add='text-red-400')
                                return

                            existing = app.storage.general.get('career_timeline', [])
                            existing_keys = {(e['company'], e['start']) for e in existing}
                            new_entries = [e for e in entries if (e['company'], e['start']) not in existing_keys]
                            existing.extend(new_entries)
                            app.storage.general['career_timeline'] = existing

                            notion_status.text = f'Extracted {len(new_entries)} new career entries!'
                            notion_status.classes(remove='text-amber-400 text-red-400', add='text-green-400')

                            _build_timeline_plot(app.storage.general['career_timeline'], timeline_container)
                            _render_entries_list()

                        except Exception as ex:
                            notion_status.text = f'Error fetching page: {ex}'
                            notion_status.classes(remove='text-amber-400 text-green-400', add='text-red-400')

                    ui.button('Fetch & Parse', icon='download', on_click=fetch_notion).props('color=primary')

        # ── Timeline Plot ──
        timeline_container = ui.column().classes('w-full')
        _build_timeline_plot(app.storage.general.get('career_timeline', []), timeline_container)

        # ── Career Entries List (editable) ──
        ui.separator()
        ui.label('CAREER ENTRIES').classes('section-title')

        entries_container = ui.column().classes('w-full gap-2')

        def _render_entries_list():
            entries_container.clear()
            entries = app.storage.general.get('career_timeline', [])

            if not entries:
                with entries_container:
                    ui.label('No entries yet.').classes('text-gray-500')
                return

            sorted_entries = sorted(entries, key=lambda e: e['start'], reverse=True)
            companies_ordered = list(dict.fromkeys(e['company'] for e in sorted(entries, key=lambda e: e['start'])))
            color_map = {c: COMPANY_COLORS[i % len(COMPANY_COLORS)] for i, c in enumerate(companies_ordered)}

            with entries_container:
                for entry in sorted_entries:
                    color = color_map.get(entry['company'], '#888')
                    with ui.card().classes('w-full p-3').style(f'border-left: 4px solid {color};'):
                        with ui.row().classes('w-full justify-between items-center'):
                            with ui.column().classes('gap-0'):
                                ui.label(entry['company']).classes('font-bold')
                                ui.label(entry['role']).classes('text-sm text-gray-400')
                                ui.label(f"{entry['start'][:7]} → {entry['end'][:7]}").classes('mono text-xs text-gray-500')
                            with ui.row().classes('gap-1'):
                                ui.button(icon='edit', on_click=lambda e=entry: _open_edit_dialog(e)).props('flat dense round size=sm')
                                ui.button(icon='delete', on_click=lambda e=entry: _delete_entry(e)).props('flat dense round color=red-4 size=sm')

        def _delete_entry(entry):
            ui.notify('Entry deleted', type='info')
            entries = app.storage.general.get('career_timeline', [])
            entries = [e for e in entries if not (e['company'] == entry['company'] and e['start'] == entry['start'] and e['role'] == entry['role'])]
            app.storage.general['career_timeline'] = entries
            _build_timeline_plot(entries, timeline_container)
            _render_entries_list()

        def _open_edit_dialog(entry):
            with ui.dialog() as dialog, ui.card().classes('p-4').style('min-width: 350px;'):
                ui.label('Edit Career Entry').classes('font-bold text-lg mb-2')
                company_input = ui.input('Company', value=entry['company']).classes('w-full')
                role_input = ui.input('Role / Title', value=entry['role']).classes('w-full')
                with ui.row().classes('w-full gap-2'):
                    start_input = ui.input('Start (YYYY-MM-DD)', value=entry['start']).classes('flex-grow')
                    end_input = ui.input('End (YYYY-MM-DD)', value=entry['end']).classes('flex-grow')

                with ui.row().classes('w-full justify-end gap-2 mt-2'):
                    ui.button('Cancel', on_click=dialog.close).props('flat')

                    def save_edit():
                        entries = app.storage.general.get('career_timeline', [])
                        for e in entries:
                            if e['company'] == entry['company'] and e['start'] == entry['start'] and e['role'] == entry['role']:
                                e['company'] = company_input.value
                                e['role'] = role_input.value
                                e['start'] = start_input.value
                                e['end'] = end_input.value
                                break
                        app.storage.general['career_timeline'] = entries
                        dialog.close()
                        _build_timeline_plot(entries, timeline_container)
                        _render_entries_list()
                        ui.notify('Entry updated', type='positive')

                    ui.button('Save', on_click=save_edit).props('color=primary')

            dialog.open()

        _render_entries_list()

        # ── Add New Entry Form ──
        ui.separator()
        ui.label('ADD CAREER ENTRY').classes('section-title')

        with ui.card().classes('w-full p-4'):
            new_company = ui.input('Company', placeholder='e.g. Google').classes('w-full')
            new_role = ui.input('Role / Title', placeholder='e.g. Senior Data Scientist').classes('w-full')

            with ui.row().classes('w-full gap-3'):
                with ui.input('Start Date').classes('flex-grow') as new_start:
                    with new_start.add_slot('append'):
                        ui.icon('edit_calendar').on('click', lambda: start_menu.open()).classes('cursor-pointer')
                    with ui.menu() as start_menu:
                        ui.date(on_change=lambda e: (new_start.set_value(e.value), start_menu.close()))

                with ui.input('End Date (leave empty for Present)').classes('flex-grow') as new_end:
                    with new_end.add_slot('append'):
                        ui.icon('edit_calendar').on('click', lambda: end_menu.open()).classes('cursor-pointer')
                    with ui.menu() as end_menu:
                        ui.date(on_change=lambda e: (new_end.set_value(e.value), end_menu.close()))

            def add_entry():
                if not new_company.value or not new_start.value:
                    ui.notify('Company and start date are required', type='warning')
                    return

                end_val = new_end.value or datetime.now().strftime('%Y-%m-%d')
                entries = app.storage.general.get('career_timeline', [])
                entries.append({
                    'company': new_company.value,
                    'role': new_role.value or 'Role',
                    'start': new_start.value,
                    'end': end_val,
                })
                app.storage.general['career_timeline'] = entries

                # Clear form
                new_company.value = ''
                new_role.value = ''
                new_start.value = ''
                new_end.value = ''

                _build_timeline_plot(entries, timeline_container)
                _render_entries_list()
                ui.notify('Career entry added!', type='positive')

            ui.button('Add Entry', icon='add', on_click=add_entry).props('color=primary')

        # ── Clear All ──
        with ui.row().classes('w-full justify-end'):
            def clear_all():
                app.storage.general['career_timeline'] = []
                _build_timeline_plot([], timeline_container)
                _render_entries_list()
                ui.notify('All career entries cleared', type='info')

            ui.button('Clear All Entries', icon='delete_sweep', on_click=clear_all).props('flat color=red-4 size=sm')


def _build_goals_section():
    """Career goals tracker with kanban-style status (original feature)."""

    with ui.column().classes('w-full gap-4'):
        ui.label('CAREER GOALS').classes('text-3xl font-extrabold')
        ui.label('Track milestones · Set deadlines · Stay accountable').classes('mono text-xs text-gray-500')

        goals_container = ui.column().classes('w-full gap-3')

        def render_goals():
            goals_container.clear()
            goals = app.storage.general['career_goals']

            status_order = ['in_progress', 'not_started', 'done']
            status_labels = {
                'not_started': ('Not Started', 'bg-gray-800'),
                'in_progress': ('In Progress', 'bg-blue-900'),
                'done': ('Done', 'bg-green-900'),
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

                title_input.value = ''
                deadline_input.value = ''
                notes_input.value = ''

                ui.notify(f'Goal added: {goals[-1]["title"]}', type='positive')
                render_goals()

            ui.button('Add Goal', icon='add', on_click=add_goal).props('color=primary')

        render_goals()
