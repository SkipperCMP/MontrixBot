# scripts/health_monitor.py
# MontrixBot — health monitor (DISABLED)
#
# POLICY-01:
# Health is snapshot-only.
# File-based health logging (health.log) is forbidden.
#
# This script is intentionally disabled to prevent
# background health log writers from existing.

def main():
    # No-op by design
    return


if __name__ == "__main__":
    main()
