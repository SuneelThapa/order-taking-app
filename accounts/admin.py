# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    list_display = ["avatar_thumb", "email", "username", "tenant", "is_tenant", "is_superuser", "is_staff", "is_active"]
    list_filter = ["tenant", "is_tenant", "is_superuser", "is_staff", "is_active", "groups"]
    search_fields = ("email", "username")
    ordering = ("email",)

    autocomplete_fields = ("tenant",)

    fieldsets = (
        (None, {"fields": ("username", "email", "password", "profile_image", "tenant", "can_delete", "is_tenant")}),
        ("Permissions", {"fields": ("is_staff", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2", "profile_image", "tenant", "can_delete", "is_tenant", "is_staff", "is_active"),
        }),
    )

    readonly_fields = ("avatar_thumb", "last_login", "date_joined")

    def avatar_thumb(self, obj):
        if obj.profile_image:
            return format_html('<img src="{}" width="40" style="border-radius:50%;" />', obj.profile_image.url)
        return "-"
    avatar_thumb.short_description = "Avatar"

    # ----------------------------
    # Restrict tenant assignment & is_tenant for non-superusers
    # ----------------------------
    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly += ["tenant", "is_tenant", "is_superuser", "is_staff"]
        return readonly

    # ----------------------------
    # Autocomplete for tenant only visible to superusers
    # ----------------------------
    def get_autocomplete_fields(self, request):
        if request.user.is_superuser:
            return ("tenant",)
        return ()

    # ----------------------------
    # Optional: hide add button for non-superusers
    # ----------------------------
    def has_add_permission(self, request):
        return request.user.is_superuser or (request.user.is_staff and not request.user.is_tenant) #type:ignore

    def has_change_permission(self, request, obj=None):
        # Tenant users can only view, cannot change
        if request.user.is_tenant: #type:ignore
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Tenant users cannot delete
        if request.user.is_tenant: #type:ignore
            return False
        return super().has_delete_permission(request, obj)