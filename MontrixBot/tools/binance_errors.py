
# tools/binance_errors.py — human-friendly decode of common Binance errors (1.0.1+)
ERRORS = {
    -1000: "UNKNOWN — Internal error; retry later",
    -1001: "DISCONNECTED — Internal system error; retry",
    -1002: "NO_AUTH — You are not authorized to execute this request",
    -1021: "INVALID_TIMESTAMP — Timestamp for this request was 1000ms ahead or behind server time",
    -1022: "INVALID_SIGNATURE — Signature for this request is not valid",
    -1100: "ILLEGAL_CHARS — Illegal characters found in parameter",
    -1102: "BAD_PARAM — Mandatory parameter was not sent, was empty/null, or malformed",
    -1121: "BAD_SYMBOL — Invalid symbol",
    -1128: "BAD_INTERVAL — Combination of optional parameters invalid",
    -1130: "BAD_PARAM_COMBINATION — Inconsistent parameters",
    -2010: "NEW_ORDER_REJECTED — e.g., MIN_NOTIONAL/LOT_SIZE/PRICE_FILTER violation or insufficient balance",
    -2011: "CANCEL_REJECTED — Unknown order or already canceled",
    -2013: "ORDER_NOT_EXIST — Order does not exist",
    -2015: "INVALID_API_KEY_IP — Invalid API-key, IP, or operational permissions",
    418:  "IP_BANNED — Auto-ban triggered due to too many requests; cool down",
    429:  "RATE_LIMIT — Breaking request rate limit; slow down",
}

def decode(code: int, default: str = "Unknown error") -> str:
    return ERRORS.get(int(code), default)
