def get_user_merchant(user):
    """
    Unified real-time lookup across the main owner link and staff user fields.
    """
    if user.is_superuser:
        return None
    # if hasattr(user, 'merchant_profile'):
    #     return user.merchant_profile
    return user.merchant_staff_profiles.first()