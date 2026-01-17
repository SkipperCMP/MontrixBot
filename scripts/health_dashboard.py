# scripts/health_dashboard.py
#
# DISABLED — POLICY-01
# Health is snapshot-only. File-based health.log is forbidden.
#
# This dashboard previously read runtime/health.log via HealthPanel(log_path=...).
# It is intentionally disabled to prevent accidental policy violations.

def main():
    # No-op by design
    return


if __name__ == "__main__":
    main()
