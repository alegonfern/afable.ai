from django.contrib import admin
from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'sector', 'odoo_connected', 'created_at']
    list_filter = ['sector', 'odoo_connected']
    search_fields = ['name', 'owner__email']
