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
    """General-purpose career entry extractor from resume text.

    Handles a wide range of international resume formats:
      2025.08 ~ Present             Korean (YYYY.MM ~ ...)
      Jan 2020 - Dec 2023           English abbreviated month
      January 2020 - December 2023  English full month
      01/2020 - 12/2023             MM/YYYY numeric
      2020/01 - 2023/12             YYYY/MM numeric
      2020 - 2023                   Year-only
    Separators: -, –, —, ~, ～, to, through, until
    End keywords: Present, Current, Now, 현재, Ongoing, Till Date

    Company/role extraction handles:
      Company (Role)                Parenthesized role
      Company — Role                Em-dash separated
      Company | Role                Pipe separated
      Company, Role                 Comma separated
      Role at Company               "at" keyword
      Dates first (Korean)          2025.08 ~ Present  Company (Role)
      Dates last (Western)          Company, Role, Jan 2020 - Dec 2023
      Multi-line (role + company on adjacent lines)
    """
    entries = []

    # ── Pre-process: strip markdown/rich-text formatting ──
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)          # **bold**
    text = re.sub(r'\*([^*]+)\*', r'\1', text)               # *italic*
    text = re.sub(r'__([^_]+)__', r'\1', text)               # __bold__
    text = re.sub(r'`([^`]+)`', r'\1', text)                 # `code`
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)     # [text](url)
    text = re.sub(r'<[^>]+>', '', text)                       # HTML tags

    # ── Constants ──
    _MONTH_ABBR = r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec'
    _MONTH_FULL = r'January|February|March|April|May|June|July|August|September|October|November|December'
    _END_WORDS = r'Present|Current|Now|현재|Ongoing|Till\s*Date'
    _SEP = r'[-–—~～]+'
    _SEP_WORDS = r'(?:[-–—~～]+|to|through|until)'

    MONTH_MAP = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12',
    }

    ROLE_KEYWORDS = re.compile(
        r'\b('
        r'engineer|developer|programmer|architect|devops|sre|sysadmin|admin(?:istrator)?|'
        r'manager|director|chief|head|lead|principal|senior|junior|staff|'
        r'analyst|scientist|researcher|statistician|'
        r'designer|artist|illustrator|'
        r'consultant|advisor|strategist|planner|'
        r'coordinator|specialist|officer|associate|assistant|'
        r'intern|trainee|apprentice|fellow|'
        r'professor|lecturer|instructor|teacher|tutor|'
        r'founder|co-founder|cto|ceo|coo|cfo|cmo|cpo|vp|'
        r'accountant|auditor|attorney|lawyer|paralegal|'
        r'nurse|physician|therapist|pharmacist|technician|'
        r'editor|writer|journalist|reporter|producer|'
        r'recruiter|hr|'
        r'sales|marketing|product|project|program|operations|support'
        r')\b',
        re.IGNORECASE,
    )

    # Lines that are section headers, not career entries
    SECTION_KEYWORDS = re.compile(
        r'^\s*(?:#|\*)*\s*(?:'
        r'education|certificate|certification|license|skill|language|'
        r'award|honor|hobby|interest|volunteer|publication|'
        r'summary|objective|profile|reference|training|course'
        r')\b',
        re.IGNORECASE,
    )

    current_year = datetime.now().year
    current_month = datetime.now().strftime('%m')

    # ── Date patterns (most specific first) ──
    # Each returns a callable: match -> (start_year, start_month, end_year, end_month)
    date_patterns = []

    def _add(pattern, extractor):
        date_patterns.append((re.compile(pattern, re.IGNORECASE), extractor))

    # 1. YYYY.MM ~ YYYY.MM / Present (Korean)
    def _extract_kr(m):
        sy, sm = m.group('sy'), m.group('sm')
        if m.group('ey'):
            return sy, sm, m.group('ey'), m.group('em')
        return sy, sm, str(current_year), current_month
    _add(
        rf'(?P<sy>\d{{4}})\.(?P<sm>\d{{2}})\s*{_SEP}\s*(?:(?P<ey>\d{{4}})\.(?P<em>\d{{2}})|(?:{_END_WORDS}))',
        _extract_kr,
    )

    # 2. MM/YYYY - MM/YYYY / Present (numeric month/year)
    def _extract_mmyyyy(m):
        sy, sm = m.group('sy'), m.group('sm')
        if m.group('ey'):
            return sy, sm, m.group('ey'), m.group('em')
        return sy, sm, str(current_year), current_month
    _add(
        rf'(?P<sm>\d{{2}})/(?P<sy>\d{{4}})\s*{_SEP_WORDS}\s*(?:(?P<em>\d{{2}})/(?P<ey>\d{{4}})|(?:{_END_WORDS}))',
        _extract_mmyyyy,
    )

    # 3. YYYY/MM - YYYY/MM / Present (numeric year/month)
    def _extract_yyyymm(m):
        sy, sm = m.group('sy'), m.group('sm')
        if m.group('ey'):
            return sy, sm, m.group('ey'), m.group('em')
        return sy, sm, str(current_year), current_month
    _add(
        rf'(?P<sy>\d{{4}})/(?P<sm>\d{{2}})\s*{_SEP_WORDS}\s*(?:(?P<ey>\d{{4}})/(?P<em>\d{{2}})|(?:{_END_WORDS}))',
        _extract_yyyymm,
    )

    # 4. Full month name: January 2020 - December 2023 / Present
    def _extract_full_month(m):
        sm = MONTH_MAP.get(m.group('sm').lower(), '01')
        sy = m.group('sy')
        if m.group('em'):
            em = MONTH_MAP.get(m.group('em').lower(), '12')
            return sy, sm, m.group('ey'), em
        return sy, sm, str(current_year), current_month
    _add(
        rf'(?P<sm>{_MONTH_FULL})\.?\s*(?P<sy>\d{{4}})\s*{_SEP_WORDS}\s*(?:(?P<em>{_MONTH_FULL})\.?\s*(?P<ey>\d{{4}})|(?:{_END_WORDS}))',
        _extract_full_month,
    )

    # 5. Abbreviated month: Jan 2020 - Dec 2023 / Present
    def _extract_abbr_month(m):
        sm = MONTH_MAP.get(m.group('sm').lower()[:3], '01')
        sy = m.group('sy')
        if m.group('em'):
            em = MONTH_MAP.get(m.group('em').lower()[:3], '12')
            return sy, sm, m.group('ey'), em
        return sy, sm, str(current_year), current_month
    _add(
        rf'(?P<sm>{_MONTH_ABBR})\.?\s*,?\s*(?P<sy>\d{{4}})\s*{_SEP_WORDS}\s*(?:(?P<em>{_MONTH_ABBR})\.?\s*,?\s*(?P<ey>\d{{4}})|(?:{_END_WORDS}))',
        _extract_abbr_month,
    )

    # 6. Year only: 2020 - 2023 / Present (must not be inside phone/ID numbers)
    def _extract_year(m):
        sy = m.group('sy')
        if m.group('ey'):
            return sy, '01', m.group('ey'), '12'
        return sy, '01', str(current_year), current_month
    _add(
        rf'(?<![/.\d])(?P<sy>\d{{4}})\s*{_SEP_WORDS}\s*(?:(?P<ey>\d{{4}})(?![/.\d])|(?:{_END_WORDS}))',
        _extract_year,
    )

    def _try_match_date(line):
        """Try all date patterns on a line. Returns (match, sy, sm, ey, em) or None."""
        for pat, extractor in date_patterns:
            m = pat.search(line)
            if m:
                sy, sm, ey, em = extractor(m)
                # Validate year range (1960 to near future)
                try:
                    isy, iey = int(sy), int(ey)
                    if isy < 1960 or isy > current_year + 5:
                        continue
                    if iey < 1960 or iey > current_year + 5:
                        continue
                    if iey < isy:
                        continue
                    # Validate month range
                    ism, iem = int(sm), int(em)
                    if not (1 <= ism <= 12 and 1 <= iem <= 12):
                        continue
                except (ValueError, TypeError):
                    continue
                return m, sy, sm, ey, em
        return None

    def _extract_company_role(line, match, line_idx, lines_list):
        """Extract company and role from text around a date match."""
        suffix = line[match.end():].strip()
        suffix = re.sub(r'^[~～\-–—:,\s]+', '', suffix).strip()
        prefix = line[:match.start()].strip()
        prefix = re.sub(r'[|,–—\-~～:]+\s*$', '', prefix).strip()

        # Use both sides; prefer the longer/more meaningful one as primary
        # Korean: dates first, content after. Western: content first, dates after.
        if suffix and prefix:
            # If suffix has role keywords or parenthesized role, prefer it
            if '(' in suffix or ROLE_KEYWORDS.search(suffix):
                context = suffix
            elif '(' in prefix or ROLE_KEYWORDS.search(prefix):
                context = prefix
            else:
                context = suffix if len(suffix) > len(prefix) else prefix
        else:
            context = suffix or prefix

        if not context:
            return None, None

        # ── Pattern: "Role at Company" ──
        at_match = re.match(r'^(.+?)\s+at\s+(.+)$', context, re.IGNORECASE)
        if at_match and ROLE_KEYWORDS.search(at_match.group(1)):
            return at_match.group(2).strip(), at_match.group(1).strip()

        # ── Pattern: "Company (Role)" or "Company — Role" ──
        paren_match = re.match(r'^(.+?)\s*\(([^)]+)\)\s*(.*)$', context)
        if paren_match:
            company = paren_match.group(1).strip()
            role = paren_match.group(2).strip()
            extra = paren_match.group(3).strip()
            # If extra text after parens looks like a department/major, append to role
            if extra and not ROLE_KEYWORDS.search(extra):
                role = f"{role} — {extra}" if len(extra) < 50 else role
            return company, role

        # ── Pattern: "Company — Role" (em-dash) ──
        dash_match = re.match(r'^(.+?)\s*[—–]\s*(.+)$', context)
        if dash_match:
            left, right = dash_match.group(1).strip(), dash_match.group(2).strip()
            if ROLE_KEYWORDS.search(right):
                return left, right
            if ROLE_KEYWORDS.search(left):
                return right, left
            return left, right  # default: left=company, right=role

        # ── Pattern: "Part1 | Part2" or "Part1, Part2" ──
        parts = re.split(r'\s*[|]\s*', context)
        if len(parts) < 2:
            parts = re.split(r'\s*,\s*', context)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) >= 2:
            # Use role keyword heuristic to decide order
            if ROLE_KEYWORDS.search(parts[0]) and not ROLE_KEYWORDS.search(parts[1]):
                return parts[1], parts[0]
            if ROLE_KEYWORDS.search(parts[1]) and not ROLE_KEYWORDS.search(parts[0]):
                return parts[0], parts[1]
            # Default: first=company, second=role
            return parts[0], parts[1]

        if len(parts) == 1:
            text_chunk = parts[0]
            # Check adjacent lines for context
            for offset in [-1, 1]:
                adj_idx = line_idx + offset
                if 0 <= adj_idx < len(lines_list):
                    adj = lines_list[adj_idx].strip()
                    adj = re.sub(r'^[-•·#*\s]+', '', adj).strip()
                    if not adj or _try_match_date(adj):
                        continue
                    if SECTION_KEYWORDS.match(adj):
                        continue
                    # Adjacent line has context — figure out which is company, which is role
                    if ROLE_KEYWORDS.search(text_chunk):
                        return adj, text_chunk
                    if ROLE_KEYWORDS.search(adj):
                        return text_chunk, adj
                    # Heuristic: shorter text is more likely a role title
                    if offset == -1:
                        return adj, text_chunk  # previous line = company
                    break

            # Single chunk, no adjacent context
            if ROLE_KEYWORDS.search(text_chunk):
                return '', text_chunk
            return text_chunk, ''

        return None, None

    # ── Skip tracking for section context ──
    in_education_section = False

    lines = text.split('\n')
    for i, line in enumerate(lines):
        raw_line = line.strip()
        if not raw_line:
            continue

        # Track section headers to skip education/certificate entries
        if SECTION_KEYWORDS.match(raw_line):
            header_lower = raw_line.lower()
            in_education_section = any(
                kw in header_lower for kw in
                ('education', 'certificate', 'certification', 'license', 'award', 'course', 'training')
            )
            continue

        # Reset section on career-related headers
        career_header = re.match(
            r'^\s*(?:#|\*)*\s*(?:experience|career|work|employment|professional)\b',
            raw_line, re.IGNORECASE,
        )
        if career_header:
            in_education_section = False
            continue

        result = _try_match_date(raw_line)
        if not result:
            continue

        match, sy, sm, ey, em = result

        # Skip entries in education/certificate sections
        if in_education_section:
            continue

        start_date = f"{sy}-{sm}-01"
        end_date = f"{ey}-{em}-01"

        company, role = _extract_company_role(raw_line, match, i, lines)

        if not company and not role:
            continue

        # Clean up artifacts
        for cleanup_target in ('company', 'role'):
            val = company if cleanup_target == 'company' else role
            val = re.sub(r'^[-•·#*:;\s]+', '', val).strip()
            val = re.sub(r'[-•·#*:;\s]+$', '', val).strip()
            # Remove leading emoji
            val = re.sub(r'^[\U0001F300-\U0001FAFF\u2600-\u27BF]+\s*', '', val).strip()
            if cleanup_target == 'company':
                company = val
            else:
                role = val

        if not company or len(company) < 2:
            continue

        entries.append({
            'company': company,
            'role': role or 'Role',
            'start': start_date,
            'end': end_date,
        })

    return entries


def _build_timeline_plot(career_entries: list[dict], container):
    """Build a Plotly timeline chart — labels on the left, bars on the right."""
    container.clear()

    if not career_entries:
        with container:
            ui.label('No career entries yet. Upload a resume or add entries manually.').classes('text-gray-500 text-center py-8')
        return

    # Assign colors by company
    companies = list(dict.fromkeys(e['company'] for e in career_entries))
    color_map = {c: COMPANY_COLORS[i % len(COMPANY_COLORS)] for i, c in enumerate(companies)}

    # Sort by start date (oldest first)
    sorted_entries = sorted(career_entries, key=lambda e: e['start'])

    import plotly.graph_objects as go

    fig = go.Figure()

    bar_height = 0.3

    # One trace per entry — use millisecond timestamps for JSON safety
    for idx, entry in enumerate(sorted_entries):
        start = datetime.strptime(entry['start'], '%Y-%m-%d')
        end = datetime.strptime(entry['end'], '%Y-%m-%d')
        color = color_map[entry['company']]
        y_pos = idx

        start_ms = start.timestamp() * 1000
        duration_ms = (end - start).total_seconds() * 1000

        fig.add_trace(go.Bar(
            x=[duration_ms],
            y=[y_pos],
            base=[start_ms],
            orientation='h',
            marker=dict(color=color, line=dict(width=0), cornerradius=4),
            width=bar_height * 2,
            showlegend=False,
            hovertemplate=(
                f"<b>{entry['company']}</b><br>"
                f"{entry['role']}<br>"
                f"{entry['start'][:7]} → {entry['end'][:7]}"
                f"<extra></extra>"
            ),
        ))

    # Y-axis labels: "Company · Role\nYYYY-MM → YYYY-MM"
    y_labels = []
    for entry in sorted_entries:
        y_labels.append(
            f"<b>{entry['company']}</b> · {entry['role']}<br>"
            f"<span style='color:#666;font-size:11px'>{entry['start'][:7]} → {entry['end'][:7]}</span>"
        )

    fig.update_layout(
        barmode='overlay',
        xaxis=dict(
            type='date',
            gridcolor='#1e1e2e',
            tickformat='%Y',
            side='bottom',
            tickfont=dict(size=11, color='#666'),
            zeroline=False,
        ),
        yaxis=dict(
            tickmode='array',
            tickvals=list(range(len(sorted_entries))),
            ticktext=y_labels,
            autorange='reversed',
            showgrid=False,
            tickfont=dict(size=12),
            ticklabelposition='outside',
        ),
        plot_bgcolor='#0a0a0f',
        paper_bgcolor='#0a0a0f',
        font=dict(color='#e8e8f0', family='Outfit, sans-serif'),
        margin=dict(l=250, r=20, t=20, b=40),
        height=max(180, len(sorted_entries) * 70 + 60),
        bargap=0.3,
    )

    with container:
        ui.plotly(fig).classes('w-full')

    # Compact color legend
    with container:
        with ui.row().classes('gap-4 flex-wrap mt-1 px-2'):
            for company, color in color_map.items():
                with ui.row().classes('items-center gap-1'):
                    ui.element('div').style(
                        f'width: 10px; height: 10px; border-radius: 2px; background: {color};'
                    )
                    ui.label(company).classes('text-xs text-gray-500')


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


def _merge_entries(entries, status_label, timeline_container, render_list_fn):
    """Merge parsed career entries into storage and refresh the UI."""
    if not entries:
        status_label.text = 'No career entries detected. Try adding manually below.'
        status_label.classes(remove='text-amber-400 text-green-400', add='text-red-400')
        return

    existing = app.storage.general.get('career_timeline', [])
    existing_keys = {(e['company'], e['start']) for e in existing}
    new_entries = [e for e in entries if (e['company'], e['start']) not in existing_keys]
    existing.extend(new_entries)
    app.storage.general['career_timeline'] = existing

    status_label.text = f'Extracted {len(new_entries)} new career entries! ({len(entries)} total found)'
    status_label.classes(remove='text-amber-400 text-red-400', add='text-green-400')

    _build_timeline_plot(existing, timeline_container)
    render_list_fn()


def _build_timeline_section():
    """Career path timeline: upload resume / paste text, view & edit timeline."""

    with ui.column().classes('w-full gap-4'):
        ui.label('CAREER PATH').classes('text-3xl font-extrabold')
        ui.label('Upload resume or add entries manually').classes('mono text-xs text-gray-500')

        # ── Upload / Link Section ──
        with ui.card().classes('w-full p-4'):
            ui.label('IMPORT CAREER DATA').classes('section-title')

            with ui.tabs().props('dense no-caps').classes('w-full') as import_tabs:
                pdf_tab = ui.tab('pdf', label='Upload PDF')
                paste_tab = ui.tab('paste', label='Paste Text')

            with ui.tab_panels(import_tabs, value=pdf_tab).classes('w-full'):
                with ui.tab_panel(pdf_tab):
                    ui.label('Upload your resume as PDF to auto-extract career history.').classes('text-sm text-gray-400 mb-2')
                    upload_status = ui.label('').classes('text-sm')

                    async def handle_upload(e: events.UploadEventArguments):
                        upload_status.text = 'Parsing PDF...'
                        upload_status.classes(remove='text-red-400 text-green-400', add='text-amber-400')

                        try:
                            import pdfplumber
                            file_path = os.path.join(UPLOAD_DIR, e.name)
                            with open(file_path, 'wb') as f:
                                f.write(e.content.read())

                            full_text = ''
                            with pdfplumber.open(file_path) as pdf:
                                for page in pdf.pages:
                                    full_text += (page.extract_text() or '') + '\n'

                            if not full_text.strip():
                                upload_status.text = 'Could not extract text from PDF. Try a text-based PDF.'
                                upload_status.classes(remove='text-amber-400 text-green-400', add='text-red-400')
                                return

                            entries = _parse_resume_text(full_text)
                            _merge_entries(entries, upload_status, timeline_container, _render_entries_list)

                        except Exception as ex:
                            upload_status.text = f'Error parsing PDF: {ex}'
                            upload_status.classes(remove='text-amber-400 text-green-400', add='text-red-400')

                    ui.upload(
                        label='Drop resume PDF here',
                        on_upload=handle_upload,
                        auto_upload=True,
                        max_files=1,
                    ).props('accept=".pdf" flat bordered').classes('w-full')

                with ui.tab_panel(paste_tab):
                    ui.label(
                        'Paste your resume text, LinkedIn experience, or Notion page content. '
                        'Include company names with date ranges (e.g. "Google, Engineer, Jan 2020 - Dec 2023").'
                    ).classes('text-sm text-gray-400 mb-2')
                    paste_input = ui.textarea('Paste resume / career text here').classes('w-full').props('rows=8')
                    paste_status = ui.label('').classes('text-sm')

                    def parse_pasted_text():
                        text = paste_input.value.strip()
                        if not text:
                            ui.notify('Please paste some text first', type='warning')
                            return

                        entries = _parse_resume_text(text)
                        _merge_entries(entries, paste_status, timeline_container, _render_entries_list)
                        if entries:
                            paste_input.value = ''

                    ui.button('Parse & Import', icon='upload', on_click=parse_pasted_text).props('color=primary')

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
