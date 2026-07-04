"""Derived metrics engine — transparentné, dopočítané denné metriky nad DuckDB.

Hlavný vstup: :func:`build_daily_metrics`, ktorý zostaví dennú tabuľku metrík a zapíše
ju späť do DuckDB ako ``metrics_daily``.
"""

from shealth.metrics.daily import DEFAULT_PARAMS, MetricParams, build_daily_metrics

__all__ = ["build_daily_metrics", "MetricParams", "DEFAULT_PARAMS"]
