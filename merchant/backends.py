# from django.contrib.auth.backends import ModelBackend
# from django.contrib.auth import get_user_model

# class MerchantStaffPermissionBackend(ModelBackend):
#     """
#     Dynamically computes system access rights and model permissions 
#     based solely on membership within the Merchant model fields.
#     """

#     def authenticate(self, request, username=None, password=None, **kwargs):
#         User = get_user_model()
#         login_identifier = username or kwargs.get(User.USERNAME_FIELD)
#         if not login_identifier:
#             return None

#         try:
#             lookup_kwargs = {User.USERNAME_FIELD: login_identifier}
#             user = User.objects.get(**lookup_kwargs)
            
#             if user.check_password(password):
#                 is_merchant_member = (
#                     # hasattr(user, 'merchant_profile') or 
#                     user.merchant_staff_profiles.exists()
#                 )
                
#                 if not user.is_superuser:
#                     if is_merchant_member != user.is_staff:
#                         user.is_staff = is_merchant_member
#                         user.save(update_fields=['is_staff'])
                
#                 return user
#         except User.DoesNotExist:
#             return None

#     def has_perm(self, user_obj, perm, obj=None):
#         """
#         Dynamically grants access rights by matching the core target model 
#         suffixes, completely eliminating app-label naming conflicts.
#         """
#         if not user_obj.is_active or user_obj.is_anonymous:
#             return False

#         if user_obj.is_superuser:
#             return True

#         # Check real-time merchant status
#         is_staff_member = user_obj.merchant_staff_profiles.exists()
#         # is_owner = hasattr(user_obj, 'merchant_profile')

#         if is_staff_member:
#             # Suffix mapping: checks if the permission string ends with these key actions
#             # This handles any app name variations like 'merchant.', 'merchants.', 'products.', etc.
#             allowed_suffixes = [
#                 'add_merchantproduct',
#                 'change_merchantproduct',
#                 'view_merchantproduct',
#                 'delete_merchantproduct', # Added to support row-editing reloads
#                 'add_product',
#                 'view_product',
#                 'add_productimage',
#                 'change_productimage',
#                 'view_productimage',
#                 'delete_productimage',
#             ]
            
#             # If the permission string ends with any of our allowed suffixes, grant immediate access
#             if any(perm.endswith(suffix) for suffix in allowed_suffixes):
#                 return True

#         return super().has_perm(user_obj, perm, obj)

#     def has_module_perms(self, user_obj, app_label):
#         """
#         Ensures that Django Admin renders the main application group blocks 
#         on the homepage dashboard menu grid for merchants.
#         """
#         if not user_obj.is_active or user_obj.is_anonymous:
#             return False

#         if user_obj.is_superuser:
#             return True

#         # If they belong to a merchant, always let them see the dashboard groups
#         # if hasattr(user_obj, 'merchant_profile') or user_obj.merchant_staff_profiles.exists():
#         #     return True
#         if user_obj.merchant_staff_profiles.exists():
#             return True
#         return super().has_module_perms(user_obj, app_label)





from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class MerchantStaffPermissionBackend(ModelBackend):
    """
    Dynamically computes system access rights and model permissions 
    based on membership within the Merchant model fields.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        login_identifier = username or kwargs.get(User.USERNAME_FIELD)
        if not login_identifier:
            return None

        try:
            lookup_kwargs = {User.USERNAME_FIELD: login_identifier}
            user = User.objects.get(**lookup_kwargs)
            
            if user.check_password(password):
                is_merchant_member = user.merchant_staff_profiles.exists()
                
                # ONLY change status if they are a merchant staff AND not already staff
                if not user.is_superuser and is_merchant_member:
                    if not user.is_staff:
                        user.is_staff = True
                        user.save(update_fields=['is_staff'])
                
                return user
        except User.DoesNotExist:
            return None

    def has_perm(self, user_obj, perm, obj=None):
        """
        Dynamically grants access rights by matching the core target model 
        suffixes, completely eliminating app-label naming conflicts.
        """
        if not user_obj.is_active or user_obj.is_anonymous:
            return False

        if user_obj.is_superuser:
            return True

        # Fallback to standard Django permissions if they are a regular staff member
        # (This ensures regular non-merchant staff keep their normal permissions)
        if super().has_perm(user_obj, perm, obj):
            return True

        # Check real-time merchant status
        is_staff_member = user_obj.merchant_staff_profiles.exists()

        if is_staff_member:
            # Suffix mapping: checks if the permission string ends with these key actions
            allowed_suffixes = [
                'add_merchantproduct',
                'change_merchantproduct',
                'view_merchantproduct',
                'delete_merchantproduct',
                'add_product',
                'view_product',
                'add_productimage',
                'change_productimage',
                'view_productimage',
                'delete_productimage',
            ]
            
            if any(perm.endswith(suffix) for suffix in allowed_suffixes):
                return True

        return False

    def has_module_perms(self, user_obj, app_label):
        """
        Ensures that Django Admin renders the main application group blocks 
        on the homepage dashboard menu grid for merchants.
        """
        if not user_obj.is_active or user_obj.is_anonymous:
            return False

        if user_obj.is_superuser:
            return True

        # If they are standard staff with regular access, let them see their models
        if super().has_module_perms(user_obj, app_label):
            return True

        # If they belong to a merchant, let them see everything they need
        if user_obj.merchant_staff_profiles.exists():
            return True
            
        return False
