import json
import os
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import sys

RESULTS_FILE = sys.argv[1] if len(sys.argv) > 1 else 'results.json'
PRESET       = sys.argv[2] if len(sys.argv) > 2 else 'breaking'
OUTPUT_FILE  = sys.argv[3] if len(sys.argv) > 3 else f'ttft_{PRESET}.png'
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
PRESET_FILE  = os.path.join(PROJECT_ROOT, 'presets', f'{PRESET}.json')

# Global style
plt.rcParams.update({
    'font.family':       'DejaVu Sans',
    'axes.spines.top':   False,
    'axes.spines.right': False,
    'axes.facecolor':    '#f9f9f9',
    'figure.facecolor':  '#ffffff',
    'grid.color':        '#e0e0e0',
    'grid.linewidth':    0.8,
})

COLORS = {
    'success': '#2ecc71',
    'failed':  '#e74c3c',
    'ttft':    '#5b9bd5',
    'p99':     '#f39c12',
    'p99line': '#e74c3c',
    'vu':      '#f39c12',
}

# =============================================================================
# Load preset to derive stage boundaries
# =============================================================================
stage_boundaries = []
if os.path.exists(PRESET_FILE):
    with open(PRESET_FILE) as f:
        stages = json.load(f)

    elapsed = 0
    for stage in stages:
        duration = stage['duration']
        target   = stage['target']
        if duration.endswith('h'):
            secs = int(duration[:-1]) * 3600
        elif duration.endswith('m'):
            secs = int(duration[:-1]) * 60
        elif duration.endswith('s'):
            secs = int(duration[:-1])
        else:
            secs = 0
        elapsed += secs
        stage_boundaries.append((elapsed, f'VU={target}'))
else:
    print(f'Warning: {PRESET_FILE} not found, skipping stage boundaries')

# =============================================================================
# Parse results.json
# =============================================================================
ttft_rows         = []
vu_rows           = []
chat_success_rows = []
chat_failed_rows  = []
conv_success_rows = []
conv_failed_rows  = []

print(f'Reading {RESULTS_FILE}...')
with open(RESULTS_FILE) as f:
    for line in f:
        try:
            point = json.loads(line)
        except json.JSONDecodeError:
            continue

        metric = point.get('metric')
        ptype  = point.get('type')
        if ptype != 'Point':
            continue

        t = point['data']['time']
        v = point['data']['value']

        if metric == 'ttft_ms':
            ttft_rows.append({'time': t, 'ttft': v})
        elif metric == 'vus':
            vu_rows.append({'time': t, 'vus': v})
        elif metric == 'chat_success':
            chat_success_rows.append({'time': t, 'value': v})
        elif metric == 'chat_failed':
            chat_failed_rows.append({'time': t, 'value': v})
        elif metric == 'conv_success':
            conv_success_rows.append({'time': t, 'value': v})
        elif metric == 'conv_failed':
            conv_failed_rows.append({'time': t, 'value': v})

if not ttft_rows:
    print('No ttft_ms data found. Make sure you ran: k6 run --out json=results.json scripts/chatbot/test.js')
    sys.exit(1)

# =============================================================================
# Build DataFrames
# =============================================================================
ttft_df = pd.DataFrame(ttft_rows)
ttft_df['time'] = pd.to_datetime(ttft_df['time'])
ttft_df = ttft_df.sort_values('time')
t_origin = ttft_df['time'].min()
ttft_df['elapsed'] = (ttft_df['time'] - t_origin).dt.total_seconds()

vu_df = pd.DataFrame(vu_rows)
vu_df['time'] = pd.to_datetime(vu_df['time'])
vu_df = vu_df.sort_values('time')
vu_df['elapsed'] = (vu_df['time'] - t_origin).dt.total_seconds()

# =============================================================================
# Compute TTFT metrics
# =============================================================================
pmin      = ttft_df['ttft'].min() / 1000
p99_final = ttft_df['ttft'].quantile(0.99) / 1000
pmax      = ttft_df['ttft'].max() / 1000
ttft_df['cumulative_p99'] = ttft_df['ttft'].expanding(min_periods=1).quantile(0.99) / 1000
total_secs = ttft_df['elapsed'].max()

# =============================================================================
# Helpers
# =============================================================================
def format_elapsed(secs, _):
    secs = int(secs)
    if secs < 0:
        return ''
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h > 0:
        return f'{h}h {m:02d}m' if m > 0 else f'{h}h'
    elif m > 0:
        return f'{m}m {s:02d}s' if s > 0 else f'{m}m'
    else:
        return f'{s}s'

def apply_xaxis(ax):
    if total_secs > 3600 * 4:
        nbins = 6
    elif total_secs > 3600:
        nbins = 8
    else:
        nbins = 10
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(format_elapsed))
    ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=nbins, integer=True))
    plt.setp(ax.get_xticklabels(), rotation=0, ha='center', fontsize=9)
    ax.set_xlabel('Elapsed Time', fontsize=10, labelpad=6)

def draw_stage_boundaries(axes):
    for t, label in stage_boundaries:
        for ax in axes:
            ax.axvline(x=t, color='#aaaaaa', linestyle='--', alpha=0.6, linewidth=0.8)
        # Only label on the top panel, above the plot area
        axes[0].annotate(
            label,
            xy=(t, 1), xycoords=('data', 'axes fraction'),
            xytext=(4, -4), textcoords='offset points',
            fontsize=7, color='#888888', va='top', ha='left',
        )

def build_rate(rows, col, bucket_secs):
    if not rows:
        return pd.DataFrame(columns=['elapsed', col])
    df = pd.DataFrame(rows)
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time')
    df['elapsed'] = (df['time'] - t_origin).dt.total_seconds()
    df['bucket'] = (df['elapsed'] // bucket_secs) * bucket_secs
    rate = df.groupby('bucket')['value'].sum().reset_index()
    rate.columns = ['elapsed', col]
    return rate

def bar_with_labels(ax, rate_df, col, color, alpha, width):
    if rate_df.empty:
        return
    show_labels = len(rate_df) <= 20
    bars = ax.bar(
        rate_df['elapsed'], rate_df[col],
        width=width, align='edge',
        color=color, alpha=alpha,
        linewidth=0.4, edgecolor='white',
    )
    if show_labels:
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2, h + 0.02,
                    str(int(h)), ha='center', va='bottom',
                    fontsize=7.5, color='#444444', fontweight='bold',
                )

def plot_requests(ax, success_rows, failed_rows, title):
    bucket = 120 if total_secs > 3600 else 5
    width  = bucket * 0.75

    success_rate = build_rate(success_rows, 'success', bucket)
    failed_rate  = build_rate(failed_rows,  'failed',  bucket)

    n_success = int(sum(r['value'] for r in success_rows)) if success_rows else 0
    n_failed  = int(sum(r['value'] for r in failed_rows))  if failed_rows  else 0

    bar_with_labels(ax, success_rate, 'success', COLORS['success'], 0.75, width)
    bar_with_labels(ax, failed_rate,  'failed',  COLORS['failed'],  0.85, width)

    ax.set_title(f'{title}  ·  {bucket}s buckets', fontsize=10, fontweight='bold',
                 loc='left', pad=6, color='#333333')
    ax.set_ylabel('Requests', fontsize=9)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.grid(True, axis='y')

    # Headroom for labels
    ymax = ax.get_ylim()[1]
    ax.set_ylim(0, ymax * 1.25)

    # Legend as patches
    legend_handles = [
        mpatches.Patch(color=COLORS['success'], alpha=0.75, label=f'Success  {n_success}'),
    ]
    if n_failed > 0:
        legend_handles.append(mpatches.Patch(color=COLORS['failed'], alpha=0.85, label=f'Failed  {n_failed}'))
    ax.legend(handles=legend_handles, loc='upper left', fontsize=8.5,
              framealpha=0.9, edgecolor='#dddddd')

# =============================================================================
# Figure — left: 4 time-series panels, right: VU vs TTFT correlation
# =============================================================================
fig = plt.figure(figsize=(20, 14), constrained_layout=False)
fig.patch.set_facecolor('#ffffff')

outer = gridspec.GridSpec(
    1, 2,
    width_ratios=[3, 1],
    left=0.06, right=0.97,
    top=0.91, bottom=0.07,
    wspace=0.28,
)

gs = gridspec.GridSpecFromSubplotSpec(
    4, 1,
    subplot_spec=outer[0],
    height_ratios=[3, 2, 2, 1],
    hspace=0.52,
)

# Title + stats badge
fig.text(0.5, 0.975, f'Chatbot Load Test  [{PRESET.upper()}]',
         ha='center', va='top', fontsize=14, fontweight='bold', color='#222222')
fig.text(0.5, 0.955,
         f'min {pmin:.2f}s   ·   p99 {p99_final:.2f}s   ·   max {pmax:.2f}s',
         ha='center', va='top', fontsize=9.5, color='#555555',
         bbox=dict(boxstyle='round,pad=0.45', facecolor='#fff9e6',
                   edgecolor='#f0d080', alpha=0.95))

# ── Panel 1: TTFT ────────────────────────────────────────────────────────────
ax1 = fig.add_subplot(gs[0])

ax1.scatter(ttft_df['elapsed'], ttft_df['ttft'] / 1000,
            alpha=0.35, s=14, color=COLORS['ttft'], zorder=3, label='TTFT (raw)')
ax1.plot(ttft_df['elapsed'], ttft_df['cumulative_p99'],
         color=COLORS['p99'], linewidth=2.2, zorder=4, label='p99 (cumulative)')
ax1.axhline(y=p99_final, color=COLORS['p99line'], linestyle='--', linewidth=1.4,
            zorder=5, label=f'p99 final = {p99_final:.2f}s')

ax1.set_ylabel('Time to First Chunk (s)', fontsize=10)
ax1.set_title('TTFT over time', fontsize=10, fontweight='bold',
              loc='left', pad=6, color='#333333')
ax1.legend(loc='upper left', fontsize=8.5, framealpha=0.9, edgecolor='#dddddd')
ax1.grid(True)
ax1.set_xticklabels([])

# ── Panel 2: Chat requests ───────────────────────────────────────────────────
ax2 = fig.add_subplot(gs[1], sharex=ax1)
plot_requests(ax2, chat_success_rows, chat_failed_rows, 'Chat Requests')
ax2.set_xticklabels([])

# ── Panel 3: Conversation requests ──────────────────────────────────────────
ax3 = fig.add_subplot(gs[2], sharex=ax1)
plot_requests(ax3, conv_success_rows, conv_failed_rows, 'Conversation Requests')
ax3.set_xticklabels([])

# ── Panel 4: VU count ────────────────────────────────────────────────────────
ax4 = fig.add_subplot(gs[3], sharex=ax1)
if not vu_df.empty:
    ax4.fill_between(vu_df['elapsed'], vu_df['vus'],
                     alpha=0.35, color=COLORS['vu'])
    ax4.plot(vu_df['elapsed'], vu_df['vus'],
             color='#d68910', linewidth=1.8)
ax4.set_ylabel('Active VUs', fontsize=9)
ax4.set_title('Virtual Users', fontsize=10, fontweight='bold',
              loc='left', pad=6, color='#333333')
ax4.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
ax4.grid(True)

# Annotate peak VU count
if not vu_df.empty:
    peak_vus = int(vu_df['vus'].max())
    peak_t   = vu_df.loc[vu_df['vus'].idxmax(), 'elapsed']
    ax4.annotate(
        f'peak {peak_vus} VUs',
        xy=(peak_t, peak_vus),
        xytext=(peak_t + total_secs * 0.02, peak_vus * 0.8),
        fontsize=8, color='#d68910', fontweight='bold',
        arrowprops=dict(arrowstyle='->', color='#d68910', lw=1.2),
    )
    ax4.set_ylim(0, peak_vus * 1.35)

apply_xaxis(ax4)

# ── Correlation panel: VU count vs TTFT ─────────────────────────────────────
ax5 = fig.add_subplot(outer[1])

if not vu_df.empty and not ttft_df.empty:
    # For each TTFT point, find the closest VU reading by time
    vu_df_s = vu_df.set_index('elapsed').sort_index()
    def lookup_vus(elapsed):
        idx = vu_df_s.index.searchsorted(elapsed)
        idx = min(idx, len(vu_df_s) - 1)
        return int(vu_df_s.iloc[idx]['vus'])

    ttft_corr = ttft_df.copy()
    ttft_corr['vus'] = ttft_corr['elapsed'].apply(lookup_vus)

    # Scatter points coloured by elapsed time (earlier=blue, later=orange)
    sc = ax5.scatter(
        ttft_corr['vus'], ttft_corr['ttft'] / 1000,
        c=ttft_corr['elapsed'], cmap='plasma',
        alpha=0.5, s=18, zorder=3,
    )

    # Trend line (linear regression)
    if len(ttft_corr) > 2:
        import numpy as np
        z = np.polyfit(ttft_corr['vus'], ttft_corr['ttft'] / 1000, 1)
        p = np.poly1d(z)
        xu = sorted(ttft_corr['vus'].unique())
        ax5.plot(xu, p(xu), color='#e74c3c', linewidth=1.8,
                 linestyle='--', zorder=4, label=f'trend')
        ax5.legend(fontsize=8, framealpha=0.9, edgecolor='#dddddd')

    cbar = fig.colorbar(sc, ax=ax5, pad=0.02, fraction=0.046)
    cbar.set_label('Elapsed (s)', fontsize=8)
    cbar.ax.tick_params(labelsize=7)

ax5.set_xlabel('Active VUs', fontsize=10, labelpad=6)
ax5.set_ylabel('TTFT (s)', fontsize=10)
ax5.set_title('VU vs TTFT', fontsize=10, fontweight='bold',
              loc='left', pad=6, color='#333333')
ax5.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
ax5.grid(True)

# ── Stage boundaries ─────────────────────────────────────────────────────────
draw_stage_boundaries([ax1, ax2, ax3, ax4])

plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches='tight')
print(f'Saved {OUTPUT_FILE}')
plt.show()
