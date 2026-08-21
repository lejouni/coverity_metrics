"""CLI entry points for coverity-metrics"""

from coverity_metrics.cli.dashboard import main as dashboard_main
from coverity_metrics.cli.report import main as report_main
from coverity_metrics.cli.export import main as export_main
from coverity_metrics.cli.delta import main as delta_main

__all__ = [
    "dashboard_main",
    "report_main",
    "export_main",
    "delta_main",
]
