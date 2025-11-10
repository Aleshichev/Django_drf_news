from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Subscription, PinnedPost, SubscriptionHistory


@receiver(post_save, sender=Subscription)
def subscription_post_save(sender, instance, created, **kwargs):
    """Save handler for Subscription model"""
    if created:
        # Create history record for new subscription
        SubscriptionHistory.objects.create(
            subscription=instance,
            action="created",
            description=f"Subscription created for plan {instance.plan.name}",
        )
    else:
        # Check for status changes
        if hasattr(instance, "_previous_status"):
            if instance._previous_status != instance.status:
                SubscriptionHistory.objects.create(
                    subscription=instance,
                    action=instance.status,
                    description=f"Subscription status changed from {instance._previous_status} to {instance.status}",
                )


@receiver(pre_delete, sender=Subscription)
def subscription_pre_delete(sender, instance, **kwargs):
    """Handle subscription deletion"""
    # Delete pinned post if exists
    try:
        instance.user.pinned_post.delete()
    except PinnedPost.DoesNotExist:
        pass


@receiver(post_save, sender=PinnedPost)
def pinned_post_post_save(sender, instance, created, **kwargs):
    """Handler for saving pinned posts"""
    if created:
        # Check if user has an active subscription
        if (
            not hasattr(instance.user, "subscription")
            or not instance.user.subscription.is_active
        ):
            instance.delete()
            return

        # Write to subscription history
        SubscriptionHistory.objects.create(
            subscription=instance.user.subscription,
            action="post_pinned",
            description=f'Post "{instance.post.title}" pinned',
            metadata={"post_id": instance.post.id, "post_title": instance.post.title},
        )


@receiver(pre_delete, sender=PinnedPost)
def pinned_post_pre_delete(sender, instance, **kwargs):
    """Handler for deleting pinned posts"""
    # Write to subscription history
    if hasattr(instance.user, "subscription"):
        SubscriptionHistory.objects.create(
            subscription=instance.user.subscription,
            action="post_unpinned",
            description=f'Post "{instance.post.title}" unpinned',
            metadata={"post_id": instance.post.id, "post_title": instance.post.title},
        )
