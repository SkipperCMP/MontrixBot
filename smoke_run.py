
import time, traceback, os

def test_case(name, fn):
    t0 = time.perf_counter()
    try:
        fn()
        dt = time.perf_counter() - t0
        print(f"[SMOKE] {name}: OK ({dt:.2f}s)")
    except Exception as e:
        dt = time.perf_counter() - t0
        print(f"[SMOKE] {name}: FAIL ({dt:.2f}s): {e}")
        traceback.print_exc()
        raise

def t_snapshot():
    from health_monitor import write_snapshot
    write_snapshot({"smoke":"yes"})

def t_dry_order():
    from core.executor import execute_dry_run
    execute_dry_run("BUY", "ADAUSDT", 0.5, 10.0, mode="SIM")

def t_runtime_folder():
    os.makedirs("runtime", exist_ok=True)
    assert os.path.isdir("runtime")

if __name__ == "__main__":
    import time
    test_case("snapshot", t_snapshot)
    test_case("dry_order", t_dry_order)
    test_case("runtime_folder", t_runtime_folder)
