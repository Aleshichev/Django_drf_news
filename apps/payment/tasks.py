from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Payment, WebhookEvent


@shared_task
def cleanup_old_payments():
    """Clean up old failed or cancelled payments"""
    cutoff_date = timezone.now() - timedelta(days=90)
    
    # Delete payments that are older than cutoff date and are either failed or cancelled
    old_payments = Payment.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['failed', 'cancelled']
    )
    
    deleted_payments, _ = old_payments.delete()
    
    return {'deleted_payments': deleted_payments}

@shared_task
def cleanup_old_webhook_events():
    """Clean up old processed webhook events"""
    cutoff_date = timezone.now() - timedelta(days=30)
    
    # Delet old webhook events that are older than cutoff date and are either processed or ignored
    old_events = WebhookEvent.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['processed', 'ignored']
    )
    
    deleted_events, _ = old_events.delete()
    
    return {'deleted_webhook_events': deleted_events}

@shared_task
def retry_failed_webhook_events():
    """Retry processing of failed webhook events from Stripe"""
    from .services import WebhookService
    
    # Find failed webhook events from the last 24 hours
    retry_cutoff = timezone.now() - timedelta(hours=24)
    
    failed_events = WebhookEvent.objects.filter(
        status='failed',
        created_at__gte=retry_cutoff
    )[:50]  # Limit to 50 events per task run
    
    processed_count = 0
    
    for event in failed_events:
        success = WebhookService.process_stripe_webhook(event.data)
        if success:
            event.mark_as_processed()
            processed_count += 1
    
    return {'reprocessed_events': processed_count}