import dash
from dash import Dash, html, dcc, dash_table, Input, Output, State, no_update
from dash.dash_table.Format import Format, Scheme, Symbol, Group
import dash_bootstrap_components as dbc
from dateutil.relativedelta import relativedelta
from datetime import date
import glob
import json
import os
import random
import pandas as pd

app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        'https://fonts.googleapis.com/icon?family=Material+Icons',
    ],
    title='mpsecondjobs.org',
)
server = app.server
app._favicon = 'favicon.png'

# ── Load all sessions ─────────────────────────────────────────────────
SESSIONS = {}

if os.path.exists('mp_session_summary.csv'):
    _df = pd.read_csv('mp_session_summary.csv')
    _jobs = pd.read_csv('mp_jobs_detail.csv', keep_default_na=False)
    with open('metadata.json') as f:
        _meta = json.load(f)
    SESSIONS['current'] = {'df': _df, 'jobs': _jobs, 'meta': _meta}

for path in sorted(glob.glob('mp_session_summary_*.csv')):
    suffix = os.path.basename(path).replace('mp_session_summary_', '').replace('.csv', '')
    _df = pd.read_csv(path)
    _jobs = pd.read_csv(f'mp_jobs_detail_{suffix}.csv', keep_default_na=False)
    with open(f'metadata_{suffix}.json') as f:
        _meta = json.load(f)
    SESSIONS[suffix] = {'df': _df, 'jobs': _jobs, 'meta': _meta}

SESSION_OPTIONS = []
if 'current' in SESSIONS:
    SESSION_OPTIONS.append({'label': '2024–present (current session)', 'value': 'current'})
for key in sorted([k for k in SESSIONS if k != 'current'], reverse=True):
    SESSION_OPTIONS.append({'label': f'{key} session', 'value': key})

DEFAULT_SESSION = 'current' if 'current' in SESSIONS else SESSION_OPTIONS[0]['value']


def get_session_info(session_key):
    s = SESSIONS[session_key]
    meta = s['meta']
    df = s['df']
    session_start = date.fromisoformat(meta['session_start'])
    snapshot_date = date.fromisoformat(meta['snapshot_date'])
    session_end = date.fromisoformat(meta['session_end']) if 'session_end' in meta else snapshot_date
    is_current = session_key == 'current'

    elapsed = relativedelta(session_end, session_start)
    elapsed_parts = []
    if elapsed.years:
        elapsed_parts.append(f'{elapsed.years} year{"s" if elapsed.years > 1 else ""}')
    if elapsed.months:
        elapsed_parts.append(f'{elapsed.months} month{"s" if elapsed.months > 1 else ""}')
    elapsed_str = ', '.join(elapsed_parts)

    session_label = (
        f'{session_start.day} {session_start.strftime("%B %Y")} – '
        f'{session_end.day} {session_end.strftime("%B %Y")} '
        f'({elapsed_str})'
    )

    return {
        'total_mps_with_earnings': len(df[df['total_earnings'] > 0]),
        'grand_total_earnings': df['total_earnings'].sum(),
        'grand_total_hours': df['total_hours'].sum(),
        'session_label': session_label,
        'snapshot_date_words': f'{snapshot_date.day} {snapshot_date.strftime("%B %Y")}',
        'session_end_words': f'{session_end.day} {session_end.strftime("%B %Y")}',
        'is_current': is_current,
    }


# ── Navbar ─────────────────────────────────────────────────────────────
def make_navbar(pathname='/'):
    summary_cls = 'navbar-link-active' if pathname == '/' else 'navbar-link-inactive'
    about_cls = 'navbar-link-active' if pathname == '/about' else 'navbar-link-inactive'
    return html.Div([
        html.Img(src='assets/mpsj_logo.png',
                style={'height': '30px', 'margin': '0 30px 0 0', 'filter': 'invert(1)'}),
        dcc.Link('Home', href='/', className=summary_cls,
                 style={'margin': '0 15px 0 0', 'fontSize': 16}),
        html.Span('/', style={'margin': '0 15px 0 0', 'color': 'white', 'fontSize': 20}),
        dcc.Link('About', href='/about', className=about_cls,
                 style={'margin': '0 15px 0 0', 'fontSize': 16}),
    ],
        style={
            'fontFamily': 'Arial', 'fontWeight': 'bold',
            'display': 'flex', 'justifyContent': 'flex-start',
            'alignItems': 'center', 'backgroundColor': '#000000', 'padding': '10px',
        },
        className='navbar')


link_style = {'color': '#000000', 'cursor': 'pointer', 'textDecoration': 'underline'}

# ── Summary page ──────────────────────────────────────────────────────
summary_page = html.Div([
    html.Div(id='header-content', style={
        'padding': '15px 20px 0 20px', 'fontFamily': 'Arial',
    }),
    # Housekeeping line — static layout, dynamic label text
    html.Div([
        html.Div([
            html.Span(id='housekeeping-label', style={'fontSize': 13, 'color': '#666'}),
        ], className='header-housekeeping-item'),
        html.Div([
            html.Span('Download: ', style={'fontSize': 13, 'color': '#666'}),
            html.A('MP summary (.xlsx)', id='btn-download-summary',
                   style={**link_style, 'fontSize': 13}),
            html.Span(' · ', style={'color': '#999', 'margin': '0 4px'}),
            html.A('Jobs detail (.xlsx)', id='btn-download-detail',
                   style={**link_style, 'fontSize': 13}),
        ], className='header-housekeeping-item'),
    ], className='header-housekeeping', style={
        'padding': '0 20px 15px', 'fontFamily': 'Arial',
        'borderBottom': '1px solid #ddd'}),
    html.Div([
        html.Strong([
            html.Span('info', className='material-icons',
                      style={'fontSize': 16, 'verticalAlign': 'text-bottom', 'marginRight': 4}),
            'Search for an MP, constituency, party, or any detail about their outside work '
            '(e.g. "X Corp", "solicitor", "speaking", "Mauritius"). Click any MP to see a full breakdown.',
        ]),
    ], style={'padding': '10px 20px 5px', 'fontSize': 13, 'color': '#000000',
              'fontFamily': 'Arial'}),
    html.Div([
        html.Div([
            html.Span('search', className='material-icons',
                      style={'position': 'absolute', 'left': 12, 'top': '50%',
                             'transform': 'translateY(-50%)', 'fontSize': 18,
                             'color': '#999', 'zIndex': 2, 'pointerEvents': 'none'}),
            dcc.Input(id='search-input', type='text', placeholder='What do you want to search?',
                      debounce=True, className='search-input',
                      style={'width': '350px', 'fontSize': 14, 'fontFamily': 'Arial',
                             'border': '1px solid #ccc', 'borderRadius': '20px', 'outline': 'none'}),
        ], className='search-wrapper'),
        html.Div([
            html.Label('Show: ', style={'fontSize': 13, 'color': '#666', 'marginRight': 5}),
            dcc.Dropdown(id='filter-dropdown',
                         options=[{'label': 'All MPs', 'value': 'all'},
                                  {'label': 'MPs with earnings only', 'value': 'with_earnings'}],
                         value='all', clearable=False, searchable=False,
                         style={'width': 200, 'fontSize': 13}),
        ], style={'display': 'flex', 'alignItems': 'center'}),
    ], className='filter-bar', style={
        'display': 'flex', 'justifyContent': 'space-between',
        'alignItems': 'center', 'padding': '5px 20px 10px', 'fontFamily': 'Arial',
    }),
    html.Div([
        html.Button('\u2039', className='scroll-arrow scroll-arrow-left', id='scroll-left'),
        dash_table.DataTable(
            id='summary-table',
            columns=[
                {'name': 'Name', 'id': 'name', 'type': 'text'},
                {'name': 'Party', 'id': 'party', 'type': 'text'},
                {'name': 'Constituency', 'id': 'constituency', 'type': 'text'},
                {'name': 'Total Earnings', 'id': 'total_earnings', 'type': 'numeric',
                 'format': Format(precision=2, scheme=Scheme.fixed)
                 .group(True).symbol(Symbol.yes).symbol_prefix('\u00a3').symbol_suffix('')},
                {'name': 'Total Hours', 'id': 'total_hours', 'type': 'numeric',
                 'format': Format(precision=1, scheme=Scheme.fixed).group(True)},
                {'name': 'Summary', 'id': 'summary', 'type': 'text'},
            ],
            data=[], sort_action='custom', sort_mode='single',
            sort_by=[{'column_id': 'total_earnings', 'direction': 'desc'}],
            page_size=25, page_action='native',
            style_table={'overflowX': 'auto'},
            style_header={'backgroundColor': '#000000', 'color': 'white', 'fontWeight': 'bold',
                          'fontFamily': 'Arial', 'fontSize': 13, 'padding': '10px 8px', 'textAlign': 'left'},
            style_cell={'fontFamily': 'Arial', 'fontSize': 13, 'padding': '8px', 'textAlign': 'left',
                        'whiteSpace': 'normal', 'height': 'auto', 'maxWidth': '300px', 'cursor': 'pointer'},
            style_cell_conditional=[
                {'if': {'column_id': 'name'}, 'width': '160px', 'fontWeight': 'bold'},
                {'if': {'column_id': 'party'}, 'width': '120px'},
                {'if': {'column_id': 'constituency'}, 'width': '160px'},
                {'if': {'column_id': 'total_earnings'}, 'width': '120px'},
                {'if': {'column_id': 'total_hours'}, 'width': '90px'},
                {'if': {'column_id': 'summary'}, 'width': '350px', 'fontSize': 12},
            ],
            style_data={'borderBottom': '1px solid #eee'},
            style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#f9f9f9'}],
            hidden_columns=['mnis_id', 'adhoc_earnings', 'adhoc_hours',
                            'ongoing_earnings', 'ongoing_hours'],
        ),
        html.Button('\u203a', className='scroll-arrow scroll-arrow-right', id='scroll-right'),
    ], className='table-wrapper', style={'padding': '0 20px 0 20px'}),
    html.Div(id='no-results', style={'padding': '20px', 'fontFamily': 'Arial',
                                      'fontSize': 14, 'color': '#666',
                                      'fontStyle': 'italic', 'display': 'none'}),
    dbc.Modal([
        dbc.ModalHeader(id='modal-header', close_button=True,
                        style={'backgroundColor': '#000000', 'color': 'white', 'fontFamily': 'Arial'}),
        dbc.ModalBody(id='modal-body', style={'fontFamily': 'Arial', 'padding': '0'}),
    ], id='detail-modal', size='xl', centered=True, scrollable=True),
    dcc.Download(id='download-summary'),
    dcc.Download(id='download-detail'),
])

# ── About page ────────────────────────────────────────────────────────
about_page = html.Div([
    html.Div([
        dcc.Markdown('''
**Do you want to know about the extra income earned by UK MPs and the hours
they spend working outside of Parliament?**

While this information (and more) is publicly available in the
[Register of Members' Financial Interests](https://www.parliament.uk/mps-lords-and-offices/standards-and-financial-interests/parliamentary-commissioner-for-standards/registers-of-interests/register-of-members-financial-interests/),
it can be difficult to find and understand. That's why MP Second Jobs was
created — to make this important democratic resource more accessible and
insightful to members of the public, journalists, and researchers.

MP Second Jobs was built and is maintained by **Andrew Messios**. The
project was cited in
[written evidence](https://committees.parliament.uk/writtenevidence/138264/pdf/)
by former MP Peter Bradley to the 2025 Committee on Standards inquiry
into MPs' outside interests and employment.

---

**How it works**

The Register records two types of outside employment income for MPs:

- **Ad hoc payments** — one-off fees for speaking engagements, writing,
  consultancy, etc. These have a specific date and amount.

- **Ongoing agreements** — regular roles such as directorships, advisory
  positions, and media contracts. These declare a rate (e.g. £5,000/month)
  and hours commitment.

This site calculates session totals by summing ad hoc payments received
since the session started, and estimating ongoing earnings based on
declared rates and the time each agreement has been active. Ongoing
figures are estimates based on what the Register declares — actual
payments may differ.

The underlying data is open source — you can download the full dataset
as Excel files from the Home page.

---

**Links**

- For the full codebase and methodology, visit the
  [GitHub](https://github.com/messiosa/mpsecondjobs_v2).

- To learn more about the Register, see
  [Parliament's guidance](https://publications.parliament.uk/pa/cm201719/cmcode/1882/188204.htm#_idTextAnchor017).

- To get in touch, contact me via
  [Linktree](https://linktr.ee/andrewkm) or at
  [andrew.messios@gmail.com](mailto:andrew.messios@gmail.com).

---

**Support this project**
        ''', style={'fontFamily': 'Arial', 'fontSize': 14}, link_target='_blank'),
        html.A(
            html.Img(src='assets/bmc_qr.png',
                     style={'height': '200px', 'width': '200px',
                            'margin': '0 auto', 'display': 'block'}),
            href='https://www.buymeacoffee.com/mpsecondjobs', target='_blank'),
        html.Br(),
    ], style={'padding': '20px'}),
])

# ── Layout ────────────────────────────────────────────────────────────
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='session-store', data=DEFAULT_SESSION),
    html.Div(id='navbar-container'),
    html.Div(id='page-content'),
], style={'backgroundColor': 'white', 'minHeight': '100vh'})


# ── Helpers ───────────────────────────────────────────────────────────
def build_type_badge(row_type):
    if row_type in ('ongoing', 'ongoing_parent'):
        return html.Span('Ongoing', style={
            'background': '#000000', 'color': 'white', 'padding': '2px 6px',
            'borderRadius': '3px', 'fontSize': 10})
    elif row_type == 'adhoc':
        return html.Span('Ad hoc', style={
            'background': '#666', 'color': 'white', 'padding': '2px 6px',
            'borderRadius': '3px', 'fontSize': 10})
    return ''


def build_detail_table(mnis_id, session_key):
    jobs = SESSIONS[session_key]['jobs']
    mp_jobs = jobs[jobs['mnis_id'] == mnis_id]
    if mp_jobs.empty:
        return html.P('No outside employment records for this MP.',
                       style={'padding': 20, 'color': '#666', 'fontSize': 13})

    header = html.Thead(html.Tr([
        html.Th('Employer', style={'padding': '8px', 'textAlign': 'left'}),
        html.Th('Role', style={'padding': '8px', 'textAlign': 'left'}),
        html.Th('Nature of business', style={'padding': '8px', 'textAlign': 'left'}),
        html.Th('Address', style={'padding': '8px', 'textAlign': 'left'}),
        html.Th('Type', style={'padding': '8px', 'textAlign': 'left'}),
        html.Th('Dates', style={'padding': '8px', 'textAlign': 'left'}),
        html.Th('Earnings', style={'padding': '8px', 'textAlign': 'right'}),
        html.Th('Hours', style={'padding': '8px', 'textAlign': 'right'}),
    ], style={'background': '#f0f0f0', 'fontSize': 11, 'color': '#555', 'fontWeight': 'bold'}))

    rows = []
    for i, (_, r) in enumerate(mp_jobs.iterrows()):
        is_child = r['row_type'] == 'ongoing_child'
        bg = '#fafafa' if is_child else ('#f9f9f9' if i % 2 else 'white')
        if is_child:
            rows.append(html.Tr([
                html.Td('', style={'padding': '4px 8px'}),
                html.Td(f"\u21b3 {r['rate_display']}", colSpan=4,
                         style={'padding': '4px 8px 4px 20px', 'color': '#888', 'fontSize': 11}),
                html.Td(r['date_display'], style={'padding': '4px 8px', 'color': '#888', 'fontSize': 11}),
                html.Td(f"\u00a3{r['earnings']:,.2f}",
                         style={'padding': '4px 8px', 'textAlign': 'right', 'color': '#888', 'fontSize': 11}),
                html.Td(f"{r['hours']:.1f}",
                         style={'padding': '4px 8px', 'textAlign': 'right', 'color': '#888', 'fontSize': 11}),
            ], style={'background': bg, 'borderBottom': '1px solid #f0f0f0'}))
        else:
            is_zero = r['earnings'] == 0
            is_bold = r['row_type'] == 'ongoing_parent'
            rows.append(html.Tr([
                html.Td(r['employer'], style={'padding': '7px 8px', 'fontWeight': 'bold'}),
                html.Td(r['role'], style={'padding': '7px 8px'}),
                html.Td(r['nature_of_business'], style={'padding': '7px 8px', 'fontSize': 11}),
                html.Td(r['address'], style={'padding': '7px 8px', 'fontSize': 11}),
                html.Td(build_type_badge(r['row_type']), style={'padding': '7px 8px'}),
                html.Td(r['date_display'], style={'padding': '7px 8px', 'fontSize': 11}),
                html.Td(f"\u00a3{r['earnings']:,.2f}", style={
                    'padding': '7px 8px', 'textAlign': 'right',
                    'color': '#999' if is_zero else 'inherit',
                    'fontWeight': 'bold' if is_bold else 'normal'}),
                html.Td(f"{r['hours']:.1f}", style={
                    'padding': '7px 8px', 'textAlign': 'right',
                    'fontWeight': 'bold' if is_bold else 'normal'}),
            ], style={'background': bg, 'borderBottom': '1px solid #eee'}))

    return html.Table([header, html.Tbody(rows)],
                      style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': 12})


FUN_FACTS = [
    "Pete Wishart (SNP) receives music royalties from EMI \u2014 he was the keyboard player in Scottish rock band Runrig.",
    "Ed Davey (Liberal Democrat) was paid \u00a32,000 for a guest appearance on Have I Got News For You.",
    "Louise Haigh (Labour) was paid \u00a31,500 as a guest panellist on Have I Got News For You.",
    "Nigel Farage (Reform UK) has earned over \u00a3220,000 this session from Cameo \u2014 the app where you pay celebrities to record personalised video messages.",
    "Carla Denyer (Green Party) has been paid twice for ITV gameshow guest appearances \u2014 \u00a31,800 each time.",
    "Dr Andrew Murrison (Conservative) serves as a Surgeon Commander in the Royal Naval Reserve alongside being an MP \u2014 earning over \u00a322,000 for 426 hours of naval service this session.",
    "Aphra Brandreth (Conservative) is a company director of Smart Vet Ltd, trading as 'Pet People' \u2014 a veterinary clinic.",
    "Sir Geoffrey Clifton-Brown (Conservative) works as a partner in an arable farming business \u2014 706 hours of farming this session.",
    "Diane Abbott (Independent) received over \u00a340,000 in book advances for writing her autobiography \u2014 plus \u00a32,250 for narrating the audiobook herself.",
    "Carla Lockhart (DUP) has logged 701 hours of farming and administrative duties this session \u2014 more hours than most MPs spend on any outside job.",
    "Dr Rosena Allin-Khan (Labour) works shifts as a doctor at St George's Hospital NHS Trust alongside being an MP \u2014 over 300 hours this session.",
    "Chris Coghlan (Liberal Democrat) serves as a Reservist army officer in the British Army \u2014 attending nearly 90 hours of service this session.",
    "Sir Keir Starmer (Labour) still receives copyright payments for books he wrote before becoming Prime Minister.",
    "Dr Neil Hudson (Conservative) sits on the British Horseracing Authority's Horse Welfare Board \u2014 57 hours of horse welfare work this session.",
    "Wes Streeting (Labour) earns library copyright fees through Public Lending Right \u2014 for people borrowing his book from libraries.",
]


# ── Callbacks ─────────────────────────────────────────────────────────

@app.callback(
    [Output('navbar-container', 'children'),
     Output('page-content', 'children')],
    Input('url', 'pathname'),
)
def display_page(pathname):
    nav = make_navbar(pathname)
    if pathname == '/about':
        return nav, about_page
    return nav, summary_page


@app.callback(
    Output('header-content', 'children'),
    Input('session-store', 'data'),
)
def update_header(session_key):
    info = get_session_info(session_key)

    session_selector = []
    if len(SESSIONS) > 1:
        session_selector = [html.Div([
            html.Label('Session: ', style={'fontSize': 13, 'color': '#666', 'marginRight': 5}),
            dcc.Dropdown(id='session-dropdown', options=SESSION_OPTIONS, value=session_key,
                         clearable=False, searchable=False, style={'width': 280, 'fontSize': 13}),
        ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': 10})]

    if info['is_current']:
        caption = f'All figures are cumulative totals for the current parliamentary session ({info["session_label"]})'
    else:
        caption = f'All figures are cumulative totals for this parliamentary session ({info["session_label"]})'

    return [
        *session_selector,
        html.Div([
            html.Div([
                html.Span(f'{info["total_mps_with_earnings"]}',
                          style={'fontSize': 24, 'fontWeight': 'bold', 'color': '#000000'}),
                html.Span(' MPs with outside earnings', style={'fontSize': 13, 'color': '#666'}),
            ], className='stat-item', style={'marginRight': 20}),
            html.Div([
                html.Span(f'\u00a3{info["grand_total_earnings"]:,.0f}',
                          style={'fontSize': 24, 'fontWeight': 'bold', 'color': '#000000'}),
                html.Span(' total earned', style={'fontSize': 13, 'color': '#666'}),
            ], className='stat-item', style={'marginRight': 20}),
            html.Div([
                html.Span(f'{info["grand_total_hours"]:,.0f}',
                          style={'fontSize': 24, 'fontWeight': 'bold', 'color': '#000000'}),
                html.Span(' hours worked', style={'fontSize': 13, 'color': '#666'}),
            ], className='stat-item'),
        ], className='header-stats-line', style={'marginBottom': 8}),
        html.Div([html.Em(caption, style={'fontSize': 13, 'color': '#666'})],
                 style={'marginBottom': 8}),
    ]


@app.callback(
    Output('session-store', 'data'),
    Input('session-dropdown', 'value'),
    prevent_initial_call=True,
)
def update_session_store(value):
    return value


@app.callback(
    Output('housekeeping-label', 'children'),
    Input('session-store', 'data'),
)
def update_housekeeping_label(session_key):
    info = get_session_info(session_key)
    if info['is_current']:
        return f'Last updated: {info["snapshot_date_words"]}'
    return f'Session ended: {info["session_end_words"]}'


@app.callback(
    [Output('summary-table', 'data'),
     Output('no-results', 'children'),
     Output('no-results', 'style')],
    [Input('search-input', 'value'),
     Input('filter-dropdown', 'value'),
     Input('summary-table', 'sort_by'),
     Input('session-store', 'data')],
)
def filter_and_sort_table(search, show_filter, sort_by, session_key):
    session = SESSIONS[session_key]
    df = session['df']
    jobs = session['jobs']
    filtered = df.copy()
    hidden = {'display': 'none'}
    visible = {'padding': '20px', 'fontFamily': 'Arial', 'fontSize': 14,
               'color': '#666', 'fontStyle': 'italic'}

    if show_filter == 'with_earnings':
        filtered = filtered[filtered['total_earnings'] > 0]

    if search:
        sl = search.lower()
        mp_match = (
            filtered['name'].str.lower().str.contains(sl, na=False) |
            filtered['constituency'].str.lower().str.contains(sl, na=False) |
            filtered['party'].str.lower().str.contains(sl, na=False)
        )
        jobs_match = jobs[
            jobs['employer'].str.lower().str.contains(sl, na=False) |
            jobs['role'].str.lower().str.contains(sl, na=False) |
            jobs['nature_of_business'].str.lower().str.contains(sl, na=False) |
            jobs['address'].str.lower().str.contains(sl, na=False)
        ]['mnis_id'].unique()
        filtered = filtered[mp_match | filtered['mnis_id'].isin(jobs_match)]

    if sort_by:
        col = sort_by[0]['column_id']
        if col != 'summary':
            filtered = filtered.sort_values(col, ascending=sort_by[0]['direction'] == 'asc')

    if filtered.empty and search:
        parts = [html.Span(f'No results found for "{search}".')]
        if session_key == 'current':
            fact = random.choice(FUN_FACTS)
            parts += [html.Br(), html.Br(),
                      html.Span('Did you know? ', style={'fontWeight': 'bold', 'fontStyle': 'normal'}),
                      html.Span(fact, style={'fontStyle': 'normal'})]
        return [], html.Div(parts), visible
    return filtered.to_dict('records'), '', hidden


@app.callback(
    [Output('detail-modal', 'is_open'),
     Output('modal-header', 'children'),
     Output('modal-body', 'children'),
     Output('summary-table', 'active_cell')],
    [Input('summary-table', 'active_cell')],
    [State('summary-table', 'data'),
     State('session-store', 'data')],
    prevent_initial_call=True,
)
def show_mp_detail(active_cell, table_data, session_key):
    if not active_cell:
        return no_update, no_update, no_update, no_update
    row = table_data[active_cell['row']]
    header_content = html.Div([
        html.Div([
            html.Span(row['name'], style={'fontSize': 17, 'fontWeight': 'bold', 'color': 'white'}),
            html.Span(f'  {row["party"]} \u00b7 {row["constituency"]}',
                      style={'fontSize': 13, 'color': '#aaa', 'marginLeft': 12}),
        ]),
        html.Div([
            html.Span(f'\u00a3{row["total_earnings"]:,.2f}',
                      style={'fontSize': 18, 'fontWeight': 'bold', 'color': 'white'}),
            html.Span(' earned', style={'fontSize': 11, 'color': '#aaa', 'marginRight': 20}),
            html.Span(f'{row["total_hours"]:,.1f}',
                      style={'fontSize': 18, 'fontWeight': 'bold', 'color': 'white'}),
            html.Span(' hours', style={'fontSize': 11, 'color': '#aaa'}),
        ]),
    ], style={'display': 'flex', 'justifyContent': 'space-between',
              'alignItems': 'center', 'width': '100%'})
    return True, header_content, build_detail_table(row['mnis_id'], session_key), None


# ── Downloads ─────────────────────────────────────────────────────────
SUMMARY_COLUMNS = pd.DataFrame([
    {'Column': 'mnis_id', 'Description': 'Unique Parliament identifier for the MP'},
    {'Column': 'name', 'Description': "MP's full name as listed by Parliament"},
    {'Column': 'party', 'Description': 'Political party'},
    {'Column': 'constituency', 'Description': 'Parliamentary constituency'},
    {'Column': 'adhoc_earnings', 'Description': 'Total earnings from one-off payments received during the session'},
    {'Column': 'adhoc_hours', 'Description': 'Total hours worked for one-off payments during the session'},
    {'Column': 'ongoing_earnings', 'Description': 'Estimated total earnings from ongoing agreements during the session'},
    {'Column': 'ongoing_hours', 'Description': 'Estimated total hours worked for ongoing agreements during the session'},
    {'Column': 'total_earnings', 'Description': 'Sum of adhoc_earnings and ongoing_earnings'},
    {'Column': 'total_hours', 'Description': 'Sum of adhoc_hours and ongoing_hours'},
    {'Column': 'summary', 'Description': "Human-readable summary of the MP's outside earnings"},
])

DETAIL_COLUMNS = pd.DataFrame([
    {'Column': 'mnis_id', 'Description': 'Unique Parliament identifier for the MP'},
    {'Column': 'member', 'Description': "MP's full name"},
    {'Column': 'employer', 'Description': 'Name of the paying organisation'},
    {'Column': 'role', 'Description': "MP's job title or role with the employer"},
    {'Column': 'nature_of_business', 'Description': "Description of the employer's business activity"},
    {'Column': 'address', 'Description': "Employer's registered public address"},
    {'Column': 'row_type', 'Description': 'Type of record: adhoc, ongoing, ongoing_parent, ongoing_child'},
    {'Column': 'date_display', 'Description': 'Date of payment (ad hoc) or period of agreement (ongoing)'},
    {'Column': 'earnings', 'Description': 'Amount earned — actual for ad hoc, estimated for ongoing'},
    {'Column': 'hours', 'Description': 'Hours worked — actual for ad hoc, estimated for ongoing'},
    {'Column': 'rate_display', 'Description': 'Declared payment rate for ongoing agreements'},
])


def make_xlsx_bytes(data_df, definitions_df):
    import io
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        data_df.to_excel(writer, sheet_name='Data', index=False)
        definitions_df.to_excel(writer, sheet_name='Column Definitions', index=False)
        ws = writer.sheets['Column Definitions']
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 80
    return buffer.getvalue()


@app.callback(Output('download-summary', 'data'), Input('btn-download-summary', 'n_clicks'),
              State('session-store', 'data'), prevent_initial_call=True)
def download_summary(n_clicks, session_key):
    if dash.ctx.triggered_id != 'btn-download-summary':
        return no_update
    suffix = '' if session_key == 'current' else f'_{session_key}'
    return dcc.send_bytes(make_xlsx_bytes(SESSIONS[session_key]['df'], SUMMARY_COLUMNS),
                          f'mp_session_summary{suffix}.xlsx')


@app.callback(Output('download-detail', 'data'), Input('btn-download-detail', 'n_clicks'),
              State('session-store', 'data'), prevent_initial_call=True)
def download_detail(n_clicks, session_key):
    if dash.ctx.triggered_id != 'btn-download-detail':
        return no_update
    suffix = '' if session_key == 'current' else f'_{session_key}'
    return dcc.send_bytes(make_xlsx_bytes(SESSIONS[session_key]['jobs'], DETAIL_COLUMNS),
                          f'mp_jobs_detail{suffix}.xlsx')


if __name__ == '__main__':
    app.run(debug=False)
