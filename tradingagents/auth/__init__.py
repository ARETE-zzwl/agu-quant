"""License/auth module for donation-based subscription."""
from .license import check_license, activate_license, get_license_status, is_premium
from .machine_id import get_machine_fingerprint

__all__ = ["check_license", "activate_license", "get_license_status", "is_premium",
           "get_machine_fingerprint"]
