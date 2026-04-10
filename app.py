import dash
from dash import Dash, html, dcc, dash_table, Input, Output, State, no_update
from dash.dash_table.Format import Format, Scheme, Symbol, Group
import dash_bootstrap_components as dbc
from dateutil.relativedelta import relativedelta
from datetime import date
import json
import pandas as pd

app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title='mpsecondjobs.org',
)
server = app.server

# ── Load data ──────────────────────────────────────────────────────────
df = pd.read_csv('mp_session_summary.csv')
jobs = pd.read_csv('mp_jobs_detail.csv', keep_default_na=False)

with open('metadata.json') as f:
    meta = json.load(f)
SESSION_START = date.fromisoformat(meta['session_start'])
SNAPSHOT_DATE = date.fromisoformat(meta['snapshot_date'])

elapsed = relativedelta(SNAPSHOT_DATE, SESSION_START)
elapsed_parts = []
if elapsed.years:
    elapsed_parts.append(f'{elapsed.years} year{"s" if elapsed.years > 1 else ""}')
if elapsed.months:
    elapsed_parts.append(f'{elapsed.months} month{"s" if elapsed.months > 1 else ""}')
elapsed_str = ', '.join(elapsed_parts)
session_label = (
    f'{SESSION_START.day} {SESSION_START.strftime("%B %Y")} – '
    f'{SNAPSHOT_DATE.day} {SNAPSHOT_DATE.strftime("%B %Y")} '
    f'({elapsed_str})'
)
snapshot_date_words = f'{SNAPSHOT_DATE.day} {SNAPSHOT_DATE.strftime("%B %Y")}'

# ── Navbar ─────────────────────────────────────────────────────────────
navbar = html.Div([
    html.Span('mpsecondjobs.org', className='navbar-title',
              style={'margin': '0 30px 0 0', 'color': 'white', 'fontSize': 20}),
    dcc.Link('Summary', href='/', className='navbar-link',
             style={'margin': '0 15px 0 0', 'color': 'white', 'fontSize': 16}),
    html.Span('/', style={'margin': '0 15px 0 0', 'color': 'white', 'fontSize': 20}),
    dcc.Link('About', href='/about', className='navbar-link',
             style={'margin': '0 15px 0 0', 'color': 'white', 'fontSize': 16}),
],
    style={
        'fontFamily': 'Arial',
        'fontWeight': 'bold',
        'display': 'flex',
        'justifyContent': 'flex-start',
        'alignItems': 'center',
        'backgroundColor': '#383838',
        'padding': '10px',
    },
    className='navbar')

# ── Header ─────────────────────────────────────────────────────────────
total_mps_with_earnings = len(df[df['total_earnings'] > 0])
grand_total_earnings = df['total_earnings'].sum()
grand_total_hours = df['total_hours'].sum()

link_style = {'color': '#383838', 'cursor': 'pointer', 'textDecoration': 'underline'}
sep = html.Span(' · ', style={'color': '#999', 'margin': '0 4px'})

header = html.Div([
    # Line 1: headline stats
    html.Div([
        html.Span(f'{total_mps_with_earnings}',
                  style={'fontSize': 24, 'fontWeight': 'bold', 'color': '#383838'}),
        html.Span(' MPs with outside earnings', style={'fontSize': 13, 'color': '#666'}),
        sep,
        html.Span(f'£{grand_total_earnings:,.0f}',
                  style={'fontSize': 24, 'fontWeight': 'bold', 'color': '#383838'}),
        html.Span(' total earned', style={'fontSize': 13, 'color': '#666'}),
        sep,
        html.Span(f'{grand_total_hours:,.0f}',
                  style={'fontSize': 24, 'fontWeight': 'bold', 'color': '#383838'}),
        html.Span(' hours worked', style={'fontSize': 13, 'color': '#666'}),
    ], style={'marginBottom': 8}),

    # Line 2: session context caption
    html.Div([
        html.Em('All figures are cumulative totals for the current parliamentary session '
                f'({session_label})',
                style={'fontSize': 13, 'color': '#666'}),
    ], style={'marginBottom': 8}),

    # Line 3: housekeeping
    html.Div([
        html.Span(f'Last updated: {snapshot_date_words}',
                  style={'fontSize': 13, 'color': '#666'}),
        sep,
        html.Span('Download: ', style={'fontSize': 13, 'color': '#666'}),
        html.A('MP summary (.xlsx)', id='btn-download-summary',
               style={**link_style, 'fontSize': 13}),
        sep,
        html.A('Jobs detail (.xlsx)', id='btn-download-detail',
               style={**link_style, 'fontSize': 13}),
        dcc.Download(id='download-summary'),
        dcc.Download(id='download-detail'),
    ]),
], style={
    'padding': '15px 20px',
    'fontFamily': 'Arial',
    'borderBottom': '1px solid #ddd',
})

# ── Search / filter bar ───────────────────────────────────────────────
filter_bar = html.Div([
    dcc.Input(
        id='search-input',
        type='text',
        placeholder='Search by MP name, constituency, or party...',
        debounce=True,
        style={
            'width': '400px', 'padding': '8px 12px', 'fontSize': 14,
            'fontFamily': 'Arial', 'border': '1px solid #ccc', 'borderRadius': '3px',
        }
    ),
    html.Div([
        html.Label('Show: ', style={'fontSize': 13, 'color': '#666', 'marginRight': 5}),
        dcc.Dropdown(
            id='filter-dropdown',
            options=[
                {'label': 'All MPs', 'value': 'all'},
                {'label': 'MPs with earnings only', 'value': 'with_earnings'},
            ],
            value='all',
            clearable=False,
            style={'width': 200, 'fontSize': 13},
        ),
    ], style={'display': 'flex', 'alignItems': 'center'}),
], style={
    'display': 'flex', 'justifyContent': 'space-between',
    'alignItems': 'center', 'padding': '10px 20px', 'fontFamily': 'Arial',
})

# ── Summary table ─────────────────────────────────────────────────────
table = dash_table.DataTable(
    id='summary-table',
    columns=[
        {'name': 'Name', 'id': 'name', 'type': 'text'},
        {'name': 'Party', 'id': 'party', 'type': 'text'},
        {'name': 'Constituency', 'id': 'constituency', 'type': 'text'},
        {'name': 'Total Earnings', 'id': 'total_earnings', 'type': 'numeric',
         'format': Format(precision=2, scheme=Scheme.fixed)
         .group(True).symbol(Symbol.yes).symbol_prefix('£').symbol_suffix('')},
        {'name': 'Total Hours Worked', 'id': 'total_hours', 'type': 'numeric',
         'format': Format(precision=1, scheme=Scheme.fixed).group(True)},
        {'name': 'Summary', 'id': 'summary', 'type': 'text'},
    ],
    data=df.to_dict('records'),
    sort_action='custom',
    sort_mode='single',
    sort_by=[{'column_id': 'total_earnings', 'direction': 'desc'}],
    page_size=25,
    page_action='native',
    style_table={'overflowX': 'auto'},
    style_header={
        'backgroundColor': '#383838', 'color': 'white', 'fontWeight': 'bold',
        'fontFamily': 'Arial', 'fontSize': 13, 'padding': '10px 8px', 'textAlign': 'left',
    },
    style_cell={
        'fontFamily': 'Arial', 'fontSize': 13, 'padding': '8px', 'textAlign': 'left',
        'whiteSpace': 'normal', 'height': 'auto', 'maxWidth': '300px', 'cursor': 'pointer',
    },
    style_cell_conditional=[
        {'if': {'column_id': 'name'}, 'width': '160px', 'fontWeight': 'bold'},
        {'if': {'column_id': 'party'}, 'width': '120px'},
        {'if': {'column_id': 'constituency'}, 'width': '160px'},
        {'if': {'column_id': 'total_earnings'}, 'width': '120px'},
        {'if': {'column_id': 'total_hours'}, 'width': '90px'},
        {'if': {'column_id': 'summary'}, 'width': '350px', 'fontSize': 12},
    ],
    style_data={'borderBottom': '1px solid #eee'},
    style_data_conditional=[
        {'if': {'row_index': 'odd'}, 'backgroundColor': '#f9f9f9'},
    ],
    hidden_columns=['mnis_id', 'adhoc_earnings', 'adhoc_hours',
                    'ongoing_earnings', 'ongoing_hours'],
)

# ── Modal for job detail ──────────────────────────────────────────────
modal = dbc.Modal([
    dbc.ModalHeader(id='modal-header', close_button=True, style={
        'backgroundColor': '#383838', 'color': 'white', 'fontFamily': 'Arial',
    }),
    dbc.ModalBody(id='modal-body', style={'fontFamily': 'Arial', 'padding': '0'}),
], id='detail-modal', size='xl', centered=True, scrollable=True)

# ── Summary page ──────────────────────────────────────────────────────
summary_page = html.Div([
    header,
    filter_bar,
    html.Div(html.Em('Click any MP name to see a full breakdown of their outside employment.'),
             style={'padding': '0 20px 5px', 'fontSize': 12, 'color': '#666',
                    'fontFamily': 'Arial'}),
    html.Div([table], style={'padding': '0 20px 20px 20px'}),
    modal,
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
as Excel files from the Summary page.

---

**Links**

MP Second Jobs was built and is maintained by **Andrew Messios**.

- For the full codebase and methodology, visit the
  [GitHub](https://github.com/messiosa/mpsecondjobs_v2).

- To learn more about the Register, see
  [Parliament's guidance](https://publications.parliament.uk/pa/cm201719/cmcode/1882/188204.htm#_idTextAnchor017).

- To get in touch, contact me via
  [Linktree](https://linktr.ee/andrewkm) or at
  [andrew.messios@gmail.com](mailto:andrew.messios@gmail.com).

---

**Support this project**
        ''', style={'fontFamily': 'Arial', 'fontSize': 14},
            link_target='_blank'),

        html.A(
            html.Img(src='assets/bmc_qr.png',
                     style={'height': '200px', 'width': '200px',
                            'margin': '0 auto', 'display': 'block'}),
            href='https://www.buymeacoffee.com/mpsecondjobs',
            target='_blank',
        ),
        html.Br(),
    ], style={'padding': '20px'}),
])

# ── Layout ────────────────────────────────────────────────────────────
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    navbar,
    html.Div(id='page-content'),
], style={'backgroundColor': 'white', 'minHeight': '100vh'})


# ── Helpers ───────────────────────────────────────────────────────────
def build_type_badge(row_type):
    """Return a styled badge for the job type."""
    if row_type in ('ongoing', 'ongoing_parent'):
        return html.Span('Ongoing', style={
            'background': '#383838', 'color': 'white', 'padding': '2px 6px',
            'borderRadius': '3px', 'fontSize': 10,
        })
    elif row_type == 'adhoc':
        return html.Span('Ad hoc', style={
            'background': '#666', 'color': 'white', 'padding': '2px 6px',
            'borderRadius': '3px', 'fontSize': 10,
        })
    return ''


def build_detail_table(mnis_id):
    """Build the HTML table for an MP's job detail."""
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
    ], style={'background': '#f0f0f0', 'fontSize': 11, 'color': '#555',
              'fontWeight': 'bold'}))

    rows = []
    for i, (_, r) in enumerate(mp_jobs.iterrows()):
        is_child = r['row_type'] == 'ongoing_child'
        bg = '#fafafa' if is_child else ('#f9f9f9' if i % 2 else 'white')

        if is_child:
            rows.append(html.Tr([
                html.Td('', style={'padding': '4px 8px'}),
                html.Td(
                    f"\u21b3 {r['rate_display']}",
                    colSpan=4,
                    style={'padding': '4px 8px 4px 20px', 'color': '#888',
                           'fontSize': 11},
                ),
                html.Td(r['date_display'],
                         style={'padding': '4px 8px', 'color': '#888',
                                'fontSize': 11}),
                html.Td(f"\u00a3{r['earnings']:,.2f}",
                         style={'padding': '4px 8px', 'textAlign': 'right',
                                'color': '#888', 'fontSize': 11}),
                html.Td(f"{r['hours']:.1f}",
                         style={'padding': '4px 8px', 'textAlign': 'right',
                                'color': '#888', 'fontSize': 11}),
            ], style={'background': bg, 'borderBottom': '1px solid #f0f0f0'}))
        else:
            is_zero = r['earnings'] == 0
            is_bold = r['row_type'] == 'ongoing_parent'

            rows.append(html.Tr([
                html.Td(r['employer'], style={
                    'padding': '7px 8px', 'fontWeight': 'bold'}),
                html.Td(r['role'], style={'padding': '7px 8px'}),
                html.Td(r['nature_of_business'],
                         style={'padding': '7px 8px', 'fontSize': 11}),
                html.Td(r['address'],
                         style={'padding': '7px 8px', 'fontSize': 11}),
                html.Td(build_type_badge(r['row_type']),
                         style={'padding': '7px 8px'}),
                html.Td(r['date_display'],
                         style={'padding': '7px 8px', 'fontSize': 11}),
                html.Td(f"\u00a3{r['earnings']:,.2f}", style={
                    'padding': '7px 8px', 'textAlign': 'right',
                    'color': '#999' if is_zero else 'inherit',
                    'fontWeight': 'bold' if is_bold else 'normal'}),
                html.Td(f"{r['hours']:.1f}", style={
                    'padding': '7px 8px', 'textAlign': 'right',
                    'fontWeight': 'bold' if is_bold else 'normal'}),
            ], style={'background': bg, 'borderBottom': '1px solid #eee'}))

    return html.Table(
        [header, html.Tbody(rows)],
        style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': 12},
    )


# ── Callbacks ─────────────────────────────────────────────────────────

# Page routing
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname'),
)
def display_page(pathname):
    if pathname == '/about':
        return about_page
    return summary_page


# Filter and sort table
@app.callback(
    Output('summary-table', 'data'),
    [Input('search-input', 'value'),
     Input('filter-dropdown', 'value'),
     Input('summary-table', 'sort_by')],
)
def filter_and_sort_table(search, show_filter, sort_by):
    filtered = df.copy()

    if show_filter == 'with_earnings':
        filtered = filtered[filtered['total_earnings'] > 0]

    if search:
        search_lower = search.lower()
        filtered = filtered[
            filtered['name'].str.lower().str.contains(search_lower, na=False) |
            filtered['constituency'].str.lower().str.contains(search_lower, na=False) |
            filtered['party'].str.lower().str.contains(search_lower, na=False)
        ]

    if sort_by:
        col = sort_by[0]['column_id']
        if col != 'summary':
            ascending = sort_by[0]['direction'] == 'asc'
            filtered = filtered.sort_values(col, ascending=ascending)

    return filtered.to_dict('records')


# Modal: open on row click, reset active_cell to allow re-clicking same row
@app.callback(
    [Output('detail-modal', 'is_open'),
     Output('modal-header', 'children'),
     Output('modal-body', 'children'),
     Output('summary-table', 'active_cell')],
    [Input('summary-table', 'active_cell')],
    [State('summary-table', 'data')],
    prevent_initial_call=True,
)
def show_mp_detail(active_cell, table_data):
    if not active_cell:
        return no_update, no_update, no_update, no_update

    row_idx = active_cell['row']
    row_data = table_data[row_idx]
    mnis_id = row_data['mnis_id']
    name = row_data['name']
    party = row_data['party']
    constituency = row_data['constituency']
    total_earnings = row_data['total_earnings']
    total_hours = row_data['total_hours']

    header_content = html.Div([
        html.Div([
            html.Span(name, style={'fontSize': 17, 'fontWeight': 'bold', 'color': 'white'}),
            html.Span(f'  {party} \u00b7 {constituency}',
                      style={'fontSize': 13, 'color': '#aaa', 'marginLeft': 12}),
        ]),
        html.Div([
            html.Span(f'\u00a3{total_earnings:,.2f}',
                      style={'fontSize': 18, 'fontWeight': 'bold', 'color': 'white'}),
            html.Span(' earned',
                      style={'fontSize': 11, 'color': '#aaa', 'marginRight': 20}),
            html.Span(f'{total_hours:,.1f}',
                      style={'fontSize': 18, 'fontWeight': 'bold', 'color': 'white'}),
            html.Span(' hours', style={'fontSize': 11, 'color': '#aaa'}),
        ]),
    ], style={'display': 'flex', 'justifyContent': 'space-between',
              'alignItems': 'center', 'width': '100%'})

    detail = build_detail_table(mnis_id)
    return True, header_content, detail, None


# ── Column definitions for data dictionary ────────────────────────────
SUMMARY_COLUMNS = pd.DataFrame([
    {'Column': 'mnis_id', 'Description': 'Unique Parliament identifier for the MP'},
    {'Column': 'name', 'Description': 'MP\'s full name as listed by Parliament'},
    {'Column': 'party', 'Description': 'Political party'},
    {'Column': 'constituency', 'Description': 'Parliamentary constituency'},
    {'Column': 'adhoc_earnings', 'Description': 'Total earnings (£) from one-off payments received during the session'},
    {'Column': 'adhoc_hours', 'Description': 'Total hours worked for one-off payments during the session'},
    {'Column': 'ongoing_earnings', 'Description': 'Estimated total earnings (£) from ongoing employment agreements during the session, calculated from declared rates'},
    {'Column': 'ongoing_hours', 'Description': 'Estimated total hours worked for ongoing agreements during the session, calculated from declared rates'},
    {'Column': 'total_earnings', 'Description': 'Sum of adhoc_earnings and ongoing_earnings (£)'},
    {'Column': 'total_hours', 'Description': 'Sum of adhoc_hours and ongoing_hours'},
    {'Column': 'summary', 'Description': 'Human-readable summary of the MP\'s outside earnings, generated from the data'},
])

DETAIL_COLUMNS = pd.DataFrame([
    {'Column': 'mnis_id', 'Description': 'Unique Parliament identifier for the MP'},
    {'Column': 'member', 'Description': 'MP\'s full name'},
    {'Column': 'employer', 'Description': 'Name of the paying organisation'},
    {'Column': 'role', 'Description': 'MP\'s job title or role with the employer'},
    {'Column': 'nature_of_business', 'Description': 'Description of the employer\'s business activity'},
    {'Column': 'address', 'Description': 'Employer\'s registered public address'},
    {'Column': 'row_type', 'Description': 'Type of record: "adhoc" = one-off payment; "ongoing" = single ongoing agreement; "ongoing_parent" = aggregated total for multiple ongoing agreements with same employer; "ongoing_child" = individual agreement within a group'},
    {'Column': 'date_display', 'Description': 'Date of payment (ad hoc) or period of agreement (ongoing)'},
    {'Column': 'earnings', 'Description': 'Amount earned (£) — actual amount for ad hoc payments, estimated from declared rate for ongoing agreements'},
    {'Column': 'hours', 'Description': 'Hours worked — actual for ad hoc payments, estimated from declared rate for ongoing agreements'},
    {'Column': 'rate_display', 'Description': 'Declared payment rate and hours commitment for ongoing agreements (blank for ad hoc payments)'},
])


def make_xlsx_bytes(data_df, definitions_df):
    """Create an xlsx file in memory with Data and Column Definitions sheets."""
    import io
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        data_df.to_excel(writer, sheet_name='Data', index=False)
        definitions_df.to_excel(writer, sheet_name='Column Definitions', index=False)
        # Auto-fit column widths for definitions sheet
        ws = writer.sheets['Column Definitions']
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 80
    return buffer.getvalue()


# Download callbacks
@app.callback(
    Output('download-summary', 'data'),
    Input('btn-download-summary', 'n_clicks'),
    prevent_initial_call=True,
)
def download_summary(n_clicks):
    return dcc.send_bytes(
        make_xlsx_bytes(df, SUMMARY_COLUMNS),
        'mp_session_summary.xlsx',
    )


@app.callback(
    Output('download-detail', 'data'),
    Input('btn-download-detail', 'n_clicks'),
    prevent_initial_call=True,
)
def download_detail(n_clicks):
    return dcc.send_bytes(
        make_xlsx_bytes(jobs, DETAIL_COLUMNS),
        'mp_jobs_detail.xlsx',
    )


if __name__ == '__main__':
    app.run(debug=False)
