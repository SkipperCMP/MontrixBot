from core.autonomy_policy import AutonomyPolicyStore
from core.trading_state_machine import TradingStateMachine
from core.status_service import StatusService

policy = AutonomyPolicyStore()
fsm = TradingStateMachine()
svc = StatusService(policy, fsm)

print(svc.build_status().to_dict())
