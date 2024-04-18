def get_role_name(az_role: str) -> str:
    match az_role.lower():
        case "reader" | "read only":
            return "reader"
        case "contributor" | "read/write" | "scripts run only" | "scripts run and correct":
            return "contributor"
        case "owner" | "superuser":
            return "owner"
        case other:
            return other
