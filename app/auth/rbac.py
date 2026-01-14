from enum import Enum
from typing import Set

class Permission(str, Enum):
    """All application permissions (fine-grained access control)"""
    
    # Tool permissions - what users can do via agent
    VIEW_DYNOS = "view:dynos"
    VIEW_VEHICLES = "view:vehicles"
    VIEW_ALLOCATIONS = "view:allocations"
    ALLOCATE_VEHICLE = "allocate:vehicle"
    MODIFY_ALLOCATION = "modify:allocation"
    DELETE_ALLOCATION = "delete:allocation"
    
    # Admin permissions
    VIEW_USERS = "view:users"
    MANAGE_USERS = "manage:users"
    VIEW_AUDIT_LOG = "view:audit_log"
    MANAGE_GUARDRAILS = "manage:guardrails"
    
    # Cost monitoring
    VIEW_COSTS = "view:costs"
    MANAGE_BUDGETS = "manage:budgets"


class Role(str, Enum):
    """Application roles (coarse-grained)"""
    USER = "user"
    POWER_USER = "power_user"
    ADMIN = "admin"

# Permission matrix - what each role can do
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.USER: {
        Permission.VIEW_DYNOS,
        Permission.VIEW_VEHICLES,
        Permission.VIEW_ALLOCATIONS,
        Permission.ALLOCATE_VEHICLE,  # Can allocate but can't modify others' allocations
        Permission.VIEW_COSTS,
    },
    Role.POWER_USER: {
        Permission.VIEW_DYNOS,
        Permission.VIEW_VEHICLES,
        Permission.VIEW_ALLOCATIONS,
        Permission.ALLOCATE_VEHICLE,
        Permission.MODIFY_ALLOCATION,  # Can modify any allocation
        Permission.DELETE_ALLOCATION,
        Permission.VIEW_COSTS,
    },
    Role.ADMIN: set(Permission),  # All permissions
}
