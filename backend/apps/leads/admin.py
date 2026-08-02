from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('email', 'segment', 'company', 'emailed', 'created_at')
    list_filter = ('segment', 'emailed', 'created_at')
    search_fields = ('email', 'name', 'company', 'summary')
    readonly_fields = ('created_at',)
