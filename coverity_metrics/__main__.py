"""
Allow the package to be run as a module:

    python -m coverity_metrics dashboard  [args...]
    python -m coverity_metrics export     [args...]
    python -m coverity_metrics report     [args...]
    python -m coverity_metrics delta      [args...]

Running without a subcommand prints usage.
"""

import sys


def main():
    subcommands = {
        "dashboard": "coverity_metrics.cli.dashboard",
        "export":    "coverity_metrics.cli.export",
        "report":    "coverity_metrics.cli.report",
        "delta":     "coverity_metrics.cli.delta",
    }

    if len(sys.argv) < 2 or sys.argv[1] not in subcommands:
        print("Usage: python -m coverity_metrics <subcommand> [args...]\n")
        print("Available subcommands:")
        print("  dashboard  Generate interactive HTML dashboards (equivalent to coverity-dashboard)")
        print("  export     Export metrics to ZIP files          (equivalent to coverity-export)")
        print("  report     Print metrics report to console      (equivalent to coverity-metrics)")
        print("  delta      Compare two export ZIPs and emit a delta report (equivalent to coverity-delta)")
        sys.exit(1)

    subcommand = sys.argv[1]
    # Remove the subcommand from argv so the target main() sees only its own args
    sys.argv = [f"coverity-{subcommand}"] + sys.argv[2:]

    import importlib
    module = importlib.import_module(subcommands[subcommand])
    module.main()


if __name__ == "__main__":
    main()
