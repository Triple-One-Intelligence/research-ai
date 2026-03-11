"""Root conftest: prettier test output and shared config."""

import sys


def pytest_report_header(config):
    return "research-ai test suite"


# Custom terminal summary: show clear section for failures
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if exitstatus == 0:
        return

    failed = terminalreporter.stats.get("failed", [])
    errors = terminalreporter.stats.get("error", [])

    if not failed and not errors:
        return

    terminalreporter.section("What went wrong", sep="=", bold=True, red=True)

    for report in failed:
        # Extract the test name without the full path noise
        nodeid = report.nodeid
        terminalreporter.write_line(f"  FAIL: {nodeid}", red=True)

        if report.longrepr:
            lines = str(report.longrepr).strip().splitlines()
            # Show the last few relevant lines (the assertion / error message)
            relevant = [l for l in lines if not l.startswith("    ") or "assert" in l.lower() or "error" in l.lower()]
            for line in relevant[-5:]:
                terminalreporter.write_line(f"        {line}")

    for report in errors:
        terminalreporter.write_line(f"  ERROR: {report.nodeid}", red=True)
        if report.longrepr:
            for line in str(report.longrepr).strip().splitlines()[-3:]:
                terminalreporter.write_line(f"        {line}")

    terminalreporter.write_line("")
    terminalreporter.write_line("  Tip: run with --tb=long for full tracebacks", yellow=True)
