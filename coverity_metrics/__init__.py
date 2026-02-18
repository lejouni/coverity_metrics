"""
Coverity Metrics - Comprehensive metrics and dashboard generator for Coverity static analysis

This package provides tools to analyze Coverity PostgreSQL databases and generate
comprehensive metrics reports and interactive dashboards.

Main components:
- CoverityMetrics: Core metrics calculation engine
- MultiInstanceMetrics: Multi-instance aggregation and management
- MetricsCache: Performance caching layer
- CLI tools: Command-line interface for dashboard generation and reporting
"""

from coverity_metrics.__version__ import __version__, __author__, __description__
from coverity_metrics.metrics import CoverityMetrics
from coverity_metrics.multi_instance_metrics import MultiInstanceMetrics, InstanceConfig
from coverity_metrics.db_connection import CoverityDatabase
from coverity_metrics.metrics_cache import MetricsCache

__all__ = [
    "__version__",
    "__author__",
    "__description__",
    "CoverityMetrics",
    "MultiInstanceMetrics",
    "InstanceConfig",
    "CoverityDatabase",
    "MetricsCache",
]
