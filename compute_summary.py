"""
MPSJ v2 — Pre-computation script
Calculates total outside employment earnings and hours worked per MP
for a parliamentary session.

Inputs:
  - data/ folder containing snapshot subfolders (yymmdd) with Category 1, 1.1, 1.2 CSVs
  - mp_reference.csv (MNIS ID, name, party, constituency)

Output:
  - mp_session_summary.csv (one row per MP)

Usage:
  Current session:
    python compute_summary.py --data-dir data/2024-present --ref mp_reference.csv --session-start 2024-07-17 --output mp_session_summary.csv

  Previous session:
    python compute_summary.py --data-dir data/2023-2024 --ref mp_reference_2023-2024.csv --session-start 2023-11-07 --session-end 2024-05-30 --output mp_session_summary_2023-2024.csv
"""

import argparse
import fnmatch
import json
import os
import pandas as pd
from datetime import date

# Set from command-line args in main()
SESSION_START = None


def load_all_csvs(data_dir, filename_patterns):
    """Load CSVs matching any of the glob patterns recursively from data_dir, deduplicate by ID."""
    if isinstance(filename_patterns, str):
        filename_patterns = [filename_patterns]
    frames = []
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            if any(fnmatch.fnmatch(f, p) for p in filename_patterns):
                frames.append(pd.read_csv(os.path.join(root, f), encoding='utf-8-sig'))
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values('Published').drop_duplicates('ID', keep='last')
    return combined


def period_to_months(period):
    """Convert a period string to its length in months."""
    return {
        'Weekly': 1 / 4.345,
        'Monthly': 1,
        'Quarterly': 3,
        'Yearly': 12,
    }.get(period, None)


def calc_ad_hoc(c11, session_end=None):
    """Cat 1.1: sum Value and HoursWorked per MP for payments received during session."""
    if c11.empty:
        return pd.DataFrame(columns=['MNIS ID', 'adhoc_earnings', 'adhoc_hours'])

    c11 = c11.copy()
    c11['ReceivedDate'] = pd.to_datetime(c11['ReceivedDate'], errors='coerce').dt.date
    c11 = c11[c11['ReceivedDate'] >= SESSION_START]
    if session_end:
        c11 = c11[c11['ReceivedDate'] <= session_end]

    return c11.groupby('MNIS ID').agg(
        adhoc_earnings=('Value', 'sum'),
        adhoc_hours=('HoursWorked', 'sum')
    ).reset_index()


def calc_ongoing(c12, snapshot_date):
    """Cat 1.2: estimate total earnings and hours per MP from ongoing agreements."""
    if c12.empty:
        return pd.DataFrame(columns=['MNIS ID', 'ongoing_earnings', 'ongoing_hours'])

    c12 = c12.copy()
    c12['StartDate'] = pd.to_datetime(c12['StartDate'], errors='coerce').dt.date
    c12['EndDate'] = pd.to_datetime(c12['EndDate'], errors='coerce').dt.date

    results = []
    for _, r in c12.iterrows():
        start = r['StartDate'] if pd.notna(r['StartDate']) else None
        end = r['EndDate'] if pd.notna(r['EndDate']) else None

        eff_start = max(start, SESSION_START) if start else SESSION_START
        eff_end = min(end, snapshot_date) if end else snapshot_date

        if eff_end <= eff_start:
            continue

        duration_months = (eff_end - eff_start).days / 30.4375

        pay_months = period_to_months(r['RegularityOfPayment'])
        earnings = (duration_months / pay_months) * r['Value'] if pay_months and pd.notna(r['Value']) else 0

        hrs_months = period_to_months(r['PeriodForHoursWorked'])
        hours = (duration_months / hrs_months) * r['HoursWorked'] if hrs_months and pd.notna(r['HoursWorked']) else 0

        results.append({
            'MNIS ID': r['MNIS ID'],
            'ongoing_earnings': earnings,
            'ongoing_hours': hours,
        })

    if not results:
        return pd.DataFrame(columns=['MNIS ID', 'ongoing_earnings', 'ongoing_hours'])

    return pd.DataFrame(results).groupby('MNIS ID').agg(
        ongoing_earnings=('ongoing_earnings', 'sum'),
        ongoing_hours=('ongoing_hours', 'sum')
    ).reset_index()


def fmt_value(val):
    """Format a monetary value as human-readable shorthand."""
    if val >= 1_000_000:
        return f"\u00a3{val/1_000_000:.1f}m"
    elif val >= 1_000:
        return f"\u00a3{val/1_000:.0f}k"
    else:
        return f"\u00a3{val:,.0f}"


def format_payers(payer_series):
    """Format top payers into a readable string."""
    top = list(payer_series.head(2).index)
    n_others = len(payer_series) - 2
    if n_others > 0:
        return f"{', '.join(top)} and {n_others} other{'s' if n_others > 1 else ''}"
    elif len(top) == 2:
        return f"{top[0]} and {top[1]}"
    elif len(top) == 1:
        return top[0]
    return ''


def generate_summary(mnis_id, c11, c12, c1, snapshot_date):
    """Generate a templated 1-2 sentence summary of an MP's outside earnings."""
    # --- Ad hoc ---
    mp11 = c11.copy()
    mp11['ReceivedDate'] = pd.to_datetime(mp11['ReceivedDate'], errors='coerce').dt.date
    mp11 = mp11[(mp11['MNIS ID'] == mnis_id) & (mp11['ReceivedDate'] >= SESSION_START) & (mp11['ReceivedDate'] <= snapshot_date)]
    mp11 = mp11.merge(c1[['ID', 'PayerName']], left_on='Parent Interest ID', right_on='ID',
                       suffixes=('', '_parent'), how='left')

    adhoc_total = mp11['Value'].sum()
    adhoc_count = len(mp11)
    adhoc_by_payer = mp11.groupby('PayerName')['Value'].sum().sort_values(ascending=False)

    # --- Ongoing ---
    mp12 = c12[c12['MNIS ID'] == mnis_id].copy()
    mp12['StartDate'] = pd.to_datetime(mp12['StartDate'], errors='coerce').dt.date
    mp12['EndDate'] = pd.to_datetime(mp12['EndDate'], errors='coerce').dt.date

    ongoing_records = []
    for _, r in mp12.iterrows():
        start = r['StartDate'] if pd.notna(r['StartDate']) else None
        end = r['EndDate'] if pd.notna(r['EndDate']) else None
        eff_start = max(start, SESSION_START) if start else SESSION_START
        eff_end = min(end, snapshot_date) if end else snapshot_date
        if eff_end <= eff_start:
            continue
        dur_months = (eff_end - eff_start).days / 30.4375
        pay_m = period_to_months(r['RegularityOfPayment'])
        earn = (dur_months / pay_m) * r['Value'] if pay_m and pd.notna(r['Value']) else 0
        parent = c1[c1['ID'] == r['Parent Interest ID']]
        payer = parent['PayerName'].values[0] if len(parent) else 'Unknown'
        ongoing_records.append({'payer': payer, 'earnings': earn})

    ongoing_df = pd.DataFrame(ongoing_records) if ongoing_records else pd.DataFrame(columns=['payer', 'earnings'])
    ongoing_total = ongoing_df['earnings'].sum() if len(ongoing_df) else 0
    ongoing_count = len(ongoing_df)
    ongoing_by_payer = ongoing_df.groupby('payer')['earnings'].sum().sort_values(
        ascending=False) if len(ongoing_df) else pd.Series(dtype=float)

    # --- Build sentences ---
    parts = []

    if adhoc_count > 0:
        payer_str = format_payers(adhoc_by_payer)
        parts.append(
            f"{fmt_value(adhoc_total)} from {adhoc_count} "
            f"ad hoc payment{'s' if adhoc_count > 1 else ''} ({payer_str})"
        )

    if ongoing_count > 0 and ongoing_total > 0:
        payer_str = format_payers(ongoing_by_payer)
        parts.append(
            f"{fmt_value(ongoing_total)} from {ongoing_count} "
            f"ongoing role{'s' if ongoing_count > 1 else ''} ({payer_str})"
        )
    elif ongoing_count > 0 and ongoing_total == 0:
        top = list(ongoing_by_payer.head(2).index) if len(ongoing_by_payer) else []
        payer_str = ', '.join(top) if top else 'unpaid roles'
        parts.append(
            f"{ongoing_count} unpaid ongoing role{'s' if ongoing_count > 1 else ''} ({payer_str})"
        )

    if not parts:
        return "No outside employment earnings registered."

    return '. '.join(parts) + '.'


def determine_snapshot_date(data_dir):
    """Infer the snapshot date from the latest Published value across all Cat 1.1 files."""
    max_date = None
    patterns = ['PublishedInterest-Category_1_1_*.csv', 'PublishedInterest-Category_1_1.csv',
                'PublishedInterest-Category_1.1_*.csv', 'PublishedInterest-Category_1.1.csv']
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            if any(fnmatch.fnmatch(f, p) for p in patterns):
                df = pd.read_csv(os.path.join(root, f), encoding='utf-8-sig')
                d = pd.to_datetime(df['Published']).max().date()
                if max_date is None or d > max_date:
                    max_date = d
    if max_date is None:
        raise FileNotFoundError(f"No Category 1.1 CSVs found in {data_dir}")
    return max_date


def fmt_date(d):
    """Format a date as 'D Mon YYYY'."""
    if d is None:
        return ''
    return f"{d.day} {d.strftime('%b %Y')}"


def generate_jobs_detail(c1, c11, c12, snapshot_date):
    """Generate a flat CSV of all job records for the modal detail view.

    Row types:
      - ongoing_parent: aggregated row for all ongoing agreements under one parent employer
      - ongoing_child: individual ongoing agreement (sub-row with rate info)
      - adhoc: individual ad hoc payment
    """
    rows = []

    c11 = c11.copy()
    c11['ReceivedDate'] = pd.to_datetime(c11['ReceivedDate'], errors='coerce').dt.date

    c12 = c12.copy()
    c12['StartDate'] = pd.to_datetime(c12['StartDate'], errors='coerce').dt.date
    c12['EndDate'] = pd.to_datetime(c12['EndDate'], errors='coerce').dt.date

    # Process each parent employer record
    for _, parent in c1.iterrows():
        pid = parent['ID']
        mnis_id = parent['MNIS ID']
        member = parent['Member'] if pd.notna(parent.get('Member')) else ''
        employer = parent['PayerName']
        role = parent['JobTitle'] if pd.notna(parent['JobTitle']) else ''
        nature = parent['PayerNatureOfBusiness'] if pd.notna(parent['PayerNatureOfBusiness']) else ''
        address = parent['PayerPublicAddress'] if pd.notna(parent['PayerPublicAddress']) else ''

        # --- Ongoing agreements for this employer ---
        kids12 = c12[c12['Parent Interest ID'] == pid]
        ongoing_children = []
        for _, k in kids12.iterrows():
            start = k['StartDate'] if pd.notna(k['StartDate']) else None
            end = k['EndDate'] if pd.notna(k['EndDate']) else None
            eff_start = max(start, SESSION_START) if start else SESSION_START
            eff_end = min(end, snapshot_date) if end else snapshot_date

            if eff_end <= eff_start:
                continue  # Outside session

            dur_months = (eff_end - eff_start).days / 30.4375
            pay_m = period_to_months(k['RegularityOfPayment'])
            earn = (dur_months / pay_m) * k['Value'] if pay_m and pd.notna(k['Value']) else 0
            hrs_m = period_to_months(k['PeriodForHoursWorked'])
            hrs = (dur_months / hrs_m) * k['HoursWorked'] if hrs_m and pd.notna(k['HoursWorked']) else 0

            # Date display
            end_str = 'ongoing' if end is None else fmt_date(end)
            date_display = f"{fmt_date(start or SESSION_START)} – {end_str}"

            # Rate display
            val_str = f"£{k['Value']:,.0f}" if pd.notna(k['Value']) else '£0'
            rate_parts = [f"{val_str}/{k['RegularityOfPayment'].lower()}"]
            if pd.notna(k['HoursWorked']) and k['HoursWorked'] > 0:
                rate_parts.append(f"{k['HoursWorked']:g}h/{k['PeriodForHoursWorked'].lower()}")
            rate_display = ' · '.join(rate_parts)

            # Add description if present
            desc = k.get('PaymentDescription', '')
            if pd.notna(desc) and str(desc).strip():
                desc_short = str(desc).strip()
                if len(desc_short) > 60:
                    desc_short = desc_short[:57] + '...'
                rate_display += f" ({desc_short})"

            ongoing_children.append({
                'earnings': round(earn, 2),
                'hours': round(hrs, 1),
                'date_display': date_display,
                'rate_display': rate_display,
                'sort_date': str(start or SESSION_START),
            })

        # If there are ongoing children, emit parent + child rows
        if ongoing_children:
            total_earn = sum(c['earnings'] for c in ongoing_children)
            total_hrs = sum(c['hours'] for c in ongoing_children)

            # Find the earliest start and latest end across children
            starts = [k['StartDate'] for _, k in kids12.iterrows()
                      if pd.notna(k['StartDate']) and (k['EndDate'] is pd.NaT or pd.isna(k['EndDate']) or k['EndDate'] > SESSION_START)]
            first_child_date = ongoing_children[0]['date_display'] if len(ongoing_children) == 1 else ''

            if len(ongoing_children) == 1:
                # Single ongoing — no need for parent+child, just one row
                rows.append({
                    'mnis_id': mnis_id,
                    'member': member,
                    'employer': employer,
                    'role': role,
                    'nature_of_business': nature,
                    'address': address,
                    'row_type': 'ongoing',
                    'date_display': ongoing_children[0]['date_display'],
                    'earnings': ongoing_children[0]['earnings'],
                    'hours': ongoing_children[0]['hours'],
                    'rate_display': ongoing_children[0]['rate_display'],
                    'sort_date': ongoing_children[0]['sort_date'],
                })
            else:
                # Multiple ongoing — parent row with total, then child rows
                # Use most recent child date for sorting the group
                most_recent = max(c['sort_date'] for c in ongoing_children)
                rows.append({
                    'mnis_id': mnis_id,
                    'member': member,
                    'employer': employer,
                    'role': role,
                    'nature_of_business': nature,
                    'address': address,
                    'row_type': 'ongoing_parent',
                    'date_display': '',
                    'earnings': round(total_earn, 2),
                    'hours': round(total_hrs, 1),
                    'rate_display': '',
                    'sort_date': most_recent,
                })
                for child in ongoing_children:
                    rows.append({
                        'mnis_id': mnis_id,
                    'member': member,
                        'employer': employer,
                        'role': role,
                        'nature_of_business': nature,
                        'address': address,
                        'row_type': 'ongoing_child',
                        'date_display': child['date_display'],
                        'earnings': child['earnings'],
                        'hours': child['hours'],
                        'rate_display': child['rate_display'],
                        'sort_date': most_recent,
                    })

        # --- Ad hoc payments for this employer (in session only) ---
        kids11 = c11[(c11['Parent Interest ID'] == pid) & (c11['ReceivedDate'] >= SESSION_START) & (c11['ReceivedDate'] <= snapshot_date)]
        for _, k in kids11.sort_values('ReceivedDate').iterrows():
            rows.append({
                'mnis_id': mnis_id,
                    'member': member,
                'employer': employer,
                'role': role,
                'nature_of_business': nature,
                'address': address,
                'row_type': 'adhoc',
                'date_display': fmt_date(k['ReceivedDate']),
                'earnings': round(k['Value'], 2) if pd.notna(k['Value']) else 0,
                'hours': round(k['HoursWorked'], 1) if pd.notna(k['HoursWorked']) else 0,
                'rate_display': '',
                'sort_date': str(k['ReceivedDate']),
            })

    if not rows:
        return pd.DataFrame(columns=[
            'mnis_id', 'member', 'employer', 'role', 'nature_of_business', 'address',
            'row_type', 'date_display', 'earnings', 'hours', 'rate_display',
        ])

    detail = pd.DataFrame(rows)

    # Sort: within each MP, most recent date first.
    # Parent/child rows share the same sort_date so they stay grouped.
    # Within a group, parent comes before children (type_sort).
    type_order = {'ongoing_parent': 0, 'ongoing_child': 1, 'ongoing': 0, 'adhoc': 0}
    detail['_type_sort'] = detail['row_type'].map(type_order)

    detail = detail.sort_values(
        ['mnis_id', 'sort_date', '_type_sort'],
        ascending=[True, False, True]
    ).reset_index(drop=True)

    detail = detail.drop(columns=['_type_sort'])
    # Drop sort_date — internal field only
    detail = detail.drop(columns=['sort_date'])
    # Ensure no NaN in display columns
    for col in ['date_display', 'rate_display', 'nature_of_business', 'address', 'role']:
        detail[col] = detail[col].fillna('')
    return detail


def main():
    global SESSION_START

    parser = argparse.ArgumentParser(description='MPSJ: compute session summary')
    parser.add_argument('--data-dir', required=True, help='Directory containing snapshot subfolders')
    parser.add_argument('--ref', required=True, help='Path to mp_reference.csv')
    parser.add_argument('--session-start', required=True, help='Session start date (YYYY-MM-DD)')
    parser.add_argument('--session-end', default=None, help='Session end date (YYYY-MM-DD). Defaults to snapshot date.')
    parser.add_argument('--output', default='mp_session_summary.csv', help='Output CSV path')
    args = parser.parse_args()

    SESSION_START = date.fromisoformat(args.session_start)

    # Determine snapshot date and session end
    snapshot_date = determine_snapshot_date(args.data_dir)
    session_end = date.fromisoformat(args.session_end) if args.session_end else snapshot_date
    print(f"Session start: {SESSION_START}")
    print(f"Session end: {session_end}")
    print(f"Snapshot date: {snapshot_date}")

    # File patterns — match both with and without date suffixes
    cat1_patterns = ['PublishedInterest-Category_1_*.csv', 'PublishedInterest-Category_1.csv']
    cat11_patterns = ['PublishedInterest-Category_1_1_*.csv', 'PublishedInterest-Category_1_1.csv',
                      'PublishedInterest-Category_1.1_*.csv', 'PublishedInterest-Category_1.1.csv']
    cat12_patterns = ['PublishedInterest-Category_1_2_*.csv', 'PublishedInterest-Category_1_2.csv',
                      'PublishedInterest-Category_1.2_*.csv', 'PublishedInterest-Category_1.2.csv']

    # Load and deduplicate
    print("Loading Category 1 (parent)...")
    c1 = load_all_csvs(args.data_dir, cat1_patterns)
    if 'Category' in c1.columns:
        c1 = c1[c1['Category'] == 'Employment and earnings']
    c1 = c1.drop_duplicates('ID', keep='last')
    print(f"  {len(c1)} unique records")

    print("Loading Category 1.1 (ad hoc)...")
    c11 = load_all_csvs(args.data_dir, cat11_patterns)
    print(f"  {len(c11)} unique records")

    print("Loading Category 1.2 (ongoing)...")
    c12 = load_all_csvs(args.data_dir, cat12_patterns)
    print(f"  {len(c12)} unique records")

    # Calculate
    print("Calculating ad hoc totals...")
    adhoc = calc_ad_hoc(c11, session_end)
    print(f"  {len(adhoc)} MPs with ad hoc payments in session")

    print("Calculating ongoing totals...")
    ongoing = calc_ongoing(c12, session_end)
    print(f"  {len(ongoing)} MPs with ongoing agreements in session")

    # Merge earnings
    all_mnis = set()
    if not adhoc.empty:
        all_mnis.update(adhoc['MNIS ID'].tolist())
    if not ongoing.empty:
        all_mnis.update(ongoing['MNIS ID'].tolist())

    earnings = pd.DataFrame({'MNIS ID': list(all_mnis)})
    earnings = earnings.merge(adhoc, on='MNIS ID', how='left')
    earnings = earnings.merge(ongoing, on='MNIS ID', how='left')
    earnings = earnings.fillna(0)
    earnings['total_earnings'] = earnings['adhoc_earnings'] + earnings['ongoing_earnings']
    earnings['total_hours'] = earnings['adhoc_hours'] + earnings['ongoing_hours']

    # Generate summaries
    print("Generating summaries...")
    summaries = {}
    for mnis_id in all_mnis:
        summaries[mnis_id] = generate_summary(mnis_id, c11, c12, c1, session_end)
    earnings['summary'] = earnings['MNIS ID'].map(summaries)

    # Load reference and merge
    print("Loading MP reference data...")
    ref = pd.read_csv(args.ref)

    summary = ref.merge(
        earnings.rename(columns={'MNIS ID': 'mnis_id'}),
        on='mnis_id',
        how='left'
    )
    summary = summary.fillna({
        'adhoc_earnings': 0, 'adhoc_hours': 0,
        'ongoing_earnings': 0, 'ongoing_hours': 0,
        'total_earnings': 0, 'total_hours': 0,
        'summary': 'No outside employment earnings registered.',
    })

    # Round
    for col in ['adhoc_earnings', 'ongoing_earnings', 'total_earnings']:
        summary[col] = summary[col].round(2)
    for col in ['adhoc_hours', 'ongoing_hours', 'total_hours']:
        summary[col] = summary[col].round(1)

    # Sort by total earnings descending
    summary = summary.sort_values('total_earnings', ascending=False).reset_index(drop=True)

    # Output columns
    output_cols = [
        'mnis_id', 'name', 'party', 'constituency',
        'adhoc_earnings', 'adhoc_hours',
        'ongoing_earnings', 'ongoing_hours',
        'total_earnings', 'total_hours',
        'summary',
    ]
    summary[output_cols].to_csv(args.output, index=False)
    print(f"\nSaved {len(summary)} MPs to {args.output}")

    # Write metadata
    output_dir = os.path.dirname(args.output) or '.'
    output_basename = os.path.splitext(os.path.basename(args.output))[0]
    suffix = output_basename.replace('mp_session_summary', '')
    detail_path = os.path.join(output_dir, f'mp_jobs_detail{suffix}.csv')
    metadata_path = os.path.join(output_dir, f'metadata{suffix}.json')

    metadata = {
        'session_start': str(SESSION_START),
        'session_end': str(session_end),
        'snapshot_date': str(snapshot_date),
    }
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata to {metadata_path}")

    # Generate jobs detail CSV
    print("Generating jobs detail...")
    jobs_detail = generate_jobs_detail(c1, c11, c12, session_end)
    jobs_detail.to_csv(detail_path, index=False)
    print(f"Saved {len(jobs_detail)} job records to {detail_path}")

    # Top 10 preview
    print("\nTop 10 by total earnings:")
    for _, r in summary.head(10).iterrows():
        print(f"  {r['name']} ({r['party']}, {r['constituency']}): "
              f"\u00a3{r['total_earnings']:,.2f} / {r['total_hours']:.1f}h")
        print(f"    {r['summary']}")


if __name__ == '__main__':
    main()
