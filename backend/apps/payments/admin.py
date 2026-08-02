from django.contrib import admin
from .models import FlowCustomer, Payment, Plan, Subscription

admin.site.register(Plan)
admin.site.register(FlowCustomer)
admin.site.register(Subscription)
admin.site.register(Payment)
