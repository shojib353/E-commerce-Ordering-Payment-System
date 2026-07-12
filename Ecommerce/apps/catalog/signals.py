from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.catalog.models import Category
from apps.catalog.services import invalidate_category_tree_cache


#clear cache after  category save or delete
@receiver(post_save, sender=Category)
def category_saved(sender, instance, **kwargs):
    invalidate_category_tree_cache()

@receiver(post_delete, sender=Category)
def category_deleted(sender, instance, **kwargs):
    invalidate_category_tree_cache()
