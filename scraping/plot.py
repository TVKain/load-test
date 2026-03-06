#!/usr/bin/env python3
"""Plot scraping API benchmark results.

Usage:
    python3 scripts/scraping/plot.py results/2026-03-06_14-22-01_stress/results.json stress
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_scraping_results(results_path: Path, preset: str, output_path: Path):
    """Generate a 2-panel plot for scraping API benchmarks."""
    
    with open(results_path) as f:
        data = json.load(f)

    metrics = data.get('metrics', {})
    
    # Extract latency data points
    latency_metric = metrics.get('scraping_latency_ms', {})
    latency_values = latency_metric.get('values', {})
    
    # Get individual data points if available
    latency_points = []
    if 'values' in data.get('root_group', {}).get('checks', []):
        # Try to extract from detailed metrics
        pass
    
    # For now, use aggregated metrics
    latency_min = latency_values.get('min', 0)
    latency_p50 = latency_values.get('med', 0)
    latency_p95 = latency_values.get('p(95)', 0)
    latency_p99 = latency_values.get('p(99)', 0)
    latency_max = latency_values.get('max', 0)
    latency_avg = latency_values.get('avg', 0)
    
    # Extract VU data
    vus_metric = metrics.get('vus', {})
    vus_values = vus_metric.get('values', {})
    vus_max = int(vus_values.get('max', 0))
    
    # Extract request counts
    scraping_total = metrics.get('scraping_total', {}).get('values', {}).get('count', 0)
    scraping_success = metrics.get('scraping_success', {}).get('values', {}).get('count', 0)
    scraping_failed = metrics.get('scraping_failed', {}).get('values', {}).get('count', 0)
    
    # Create figure with 2 panels
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle(f'Scraping API Benchmark — {preset.upper()}', fontsize=16, fontweight='bold')
    
    # Panel 1: Latency distribution (bar chart)
    categories = ['Min', 'P50', 'Avg', 'P95', 'P99', 'Max']
    latencies = [latency_min, latency_p50, latency_avg, latency_p95, latency_p99, latency_max]
    
    bars = ax1.bar(categories, latencies, color=['#2ecc71', '#3498db', '#9b59b6', '#e74c3c', '#e67e22', '#c0392b'])
    ax1.set_ylabel('Latency (ms)', fontsize=12)
    ax1.set_title(
        f'Scraping Latency Distribution (min={latency_min:.0f}ms, p95={latency_p95:.0f}ms, max={latency_max:.0f}ms)',
        fontsize=12
    )
    ax1.grid(axis='y', alpha=0.3)
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2.,
            height,
            f'{height:.0f}',
            ha='center',
            va='bottom',
            fontsize=10
        )
    
    # Panel 2: Request results (pie chart)
    if scraping_total > 0:
        labels = []
        sizes = []
        colors = []
        
        if scraping_success > 0:
            labels.append(f'Success ({scraping_success})')
            sizes.append(scraping_success)
            colors.append('#2ecc71')
        
        if scraping_failed > 0:
            labels.append(f'Failed ({scraping_failed})')
            sizes.append(scraping_failed)
            colors.append('#e74c3c')
        
        interrupted = scraping_total - scraping_success - scraping_failed
        if interrupted > 0:
            labels.append(f'Interrupted ({interrupted})')
            sizes.append(interrupted)
            colors.append('#95a5a6')
        
        ax2.pie(
            sizes,
            labels=labels,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            textprops={'fontsize': 11}
        )
        ax2.set_title(
            f'Request Results (Total: {scraping_total}, Peak VUs: {vus_max})',
            fontsize=12
        )
    else:
        ax2.text(
            0.5,
            0.5,
            'No requests completed',
            ha='center',
            va='center',
            fontsize=14,
            transform=ax2.transAxes
        )
        ax2.set_title('Request Results', fontsize=12)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f'Plot saved to: {output_path}')


def main():
    if len(sys.argv) < 3:
        print('Usage: python3 scripts/scraping/plot.py <results.json> <preset>')
        sys.exit(1)
    
    results_path = Path(sys.argv[1])
    preset = sys.argv[2]
    
    if not results_path.exists():
        print(f'Error: {results_path} not found')
        sys.exit(1)
    
    output_path = results_path.parent / f'scraping_{preset}.png'
    plot_scraping_results(results_path, preset, output_path)


if __name__ == '__main__':
    main()
