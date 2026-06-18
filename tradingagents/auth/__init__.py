"""License/auth module for donation-based subscription."""
from .access import authenticate_account, authenticate_admin, authenticate_license_user
from .license import activate_license, check_license, get_license_status, has_plan_access, is_premium
from .machine_id import get_machine_fingerprint

__all__ = ["check_license", "activate_license", "get_license_status", "has_plan_access", "is_premium",
           "get_machine_fingerprint", "authenticate_account", "authenticate_admin",
           "authenticate_license_user"]
