from django.contrib import admin

# Register your models here.
from .models import Noticia, Voto, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'alias', 'show_alias_on_map', 'weekly_email_enabled', 'created_at')
    list_filter = ('show_alias_on_map', 'weekly_email_enabled', 'created_at')
    search_fields = ('user__email', 'alias')
    readonly_fields = ('created_at', 'updated_at')


admin.site.register(Noticia)
admin.site.register(Voto)
