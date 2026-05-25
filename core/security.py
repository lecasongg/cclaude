import secrets


class SecurityGate:
    def __init__(self, token: str):
        self._token = token

    def is_authorized(self, token: str | None) -> bool:
        if not token:
            return False
        return secrets.compare_digest(token, self._token)

    def action_allowed(self, action: str, confirmed: bool = False) -> bool:
        destructive = {"cancel", "restart", "stop", "clear_queue", "delete_artifact"}
        if action in destructive:
            return confirmed is True
        return True
