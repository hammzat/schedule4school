from . import registration, common, schedule, admin, bells, changes
labelers = [
    registration.bl,
    common.bl,
    schedule.bl,
    admin.bl,
    bells.bl,
    changes.bl
]

__all__ = ['labelers'] 