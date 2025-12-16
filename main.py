from tools.tpsl_bootstrap import start_tpsl_if_enabled

if __name__ == "__main__":
    runner = start_tpsl_if_enabled()
    print("Bot started. TPSL:", "RUNNING" if runner else "DISABLED")
