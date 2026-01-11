from runtime.state_manager import StateManager

if __name__ == "__main__":
    sm = StateManager("runtime/state.json")
    print("Before:", sm.get("positions"))
    sm.set("positions", {"TEST": {"qty": 1}})
    print("After:", sm.get("positions"))
    print("Done.")
