import stripe
import json
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import Payment, PaymentAttempt, Refund, WebhookEvent
from .serializers import (
    PaymentSerializer,
    PaymentCreateSerializer,
    PaymentAttemptSerializer,
    RefundSerializer,
    RefundCreateSerializer,
    StripeCheckoutSessionSerializer,
    PaymentStatusSerializer,
)
from .services import StripeService, PaymentService, WebhookService
from apps.subscribe.models import SubscriptionPlan
from drf_spectacular.utils import extend_schema

# =====================
# 💳 PAYMENTS
# =====================


@extend_schema(
    tags=["Payments"],
    summary="List user payments",
    description="Returns a list of all payments made by the authenticated user, including related subscriptions and plans.",
)
class PaymentListView(generics.ListAPIView):
    """List of user payments"""

    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Background queryset for user payments"""
        return (
            Payment.objects.filter(user=self.request.user)
            .select_related("subscription", "subscription__plan")
            .order_by("-created_at")
        )


@extend_schema(
    tags=["Payments"],
    summary="Retrieve payment details",
    description="Returns detailed information about a specific user payment, including subscription and plan data.",
)
class PaymentDetailView(generics.RetrieveAPIView):
    """Detail information about a payment"""

    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Back ground queryset for payment detail"""
        return Payment.objects.filter(user=self.request.user).select_related(
            "subscription", "subscription__plan"
        )


@extend_schema(
    tags=["Payments"],
    summary="Create Stripe Checkout session",
    description="Creates a new Stripe Checkout session for the selected subscription plan and returns a redirect URL for the user.",
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def create_checkout_session(request):
    """Create Stripe Checkout session for subscription payment"""
    serializer = PaymentCreateSerializer(
        data=request.data, context={"request": request}
    )

    if serializer.is_valid():
        try:
            with transaction.atomic():
                plan_id = serializer.validated_data["subscription_plan_id"]
                plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)

                # Create payment and subscription
                payment, subscription = PaymentService.create_subscription_payment(
                    request.user, plan
                )

                # Get URLs from request or use defaults
                success_url = serializer.validated_data.get(
                    "success_url",
                    f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                )
                cancel_url = serializer.validated_data.get(
                    "cancel_url", f"{settings.FRONTEND_URL}/payment/cancel"
                )

                # Create Stripe session
                session_data = StripeService.create_checkout_session(
                    payment, success_url, cancel_url
                )

                if session_data:
                    response_serializer = StripeCheckoutSessionSerializer(session_data)
                    return Response(
                        response_serializer.data, status=status.HTTP_201_CREATED
                    )
                else:
                    return Response(
                        {"error": "Failed to create checkout session"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["Payments"],
    summary="Check payment status",
    description="Checks the current status of a payment both in the local system and in Stripe. Updates the status if necessary.",
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def payment_status(request, payment_id):
    """Check the status of a payment"""
    try:
        payment = get_object_or_404(Payment, id=payment_id, user=request.user)

        # If session_id, check status in Stripe
        if payment.stripe_session_id and payment.status in ["pending", "processing"]:
            session_info = StripeService.retrieve_session(payment.stripe_session_id)

            if session_info:
                if session_info["status"] == "complete":
                    PaymentService.process_successful_payment(payment)
                elif session_info["status"] == "failed":
                    PaymentService.process_failed_payment(payment, "Session failed")

        response_data = {
            "payment_id": payment.id,
            "status": payment.status,
            "message": f"Payment is {payment.status}",
            "subscription_activated": False,
        }

        if payment.is_successful and payment.subscription:
            response_data["subscription_activated"] = payment.subscription.is_active
            response_data["message"] = "Payment successful and subscription activated"

        serializer = PaymentStatusSerializer(response_data)
        return Response(serializer.data)

    except Payment.DoesNotExist:
        return Response(
            {"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND
        )


@extend_schema(
    tags=["Payments"],
    summary="Cancel a pending payment",
    description="Allows the user to cancel a pending payment. If the payment is linked to an active subscription, the subscription will also be cancelled.",
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def cancel_payment(request, payment_id):
    """Cancel a pending payment"""
    try:
        payment = get_object_or_404(Payment, id=payment_id, user=request.user)

        if not payment.is_pending:
            return Response(
                {"error": "Can only cancel pending payments"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment.status = "cancelled"
        payment.save()

        # Cancel associated subscription if exists
        if payment.subscription:
            payment.subscription.cancel()

        return Response({"message": "Payment cancelled successfully"})

    except Payment.DoesNotExist:
        return Response(
            {"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND
        )


@extend_schema(
    tags=["Payments"],
    summary="Get user payment history",
    description="Returns a complete payment history for the authenticated user, ordered by creation date.",
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def user_payment_history(request):
    """History of user payments"""
    payments = (
        Payment.objects.filter(user=request.user)
        .select_related("subscription", "subscription__plan")
        .order_by("-created_at")
    )

    serializer = PaymentSerializer(payments, many=True)
    return Response({"count": payments.count(), "results": serializer.data})


@extend_schema(
    tags=["Payments"],
    summary="Retry a failed payment",
    description="Creates a new Stripe Checkout session to retry a previously failed payment attempt.",
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def retry_payment(request, payment_id):
    """Retry a failed payment by creating a new Stripe Checkout session"""
    try:
        payment = get_object_or_404(
            Payment, id=payment_id, user=request.user, status="failed"
        )

        # Create new Stripe Checkout session
        success_url = request.data.get(
            "success_url",
            f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        )
        cancel_url = request.data.get(
            "cancel_url", f"{settings.FRONTEND_URL}/payment/cancel"
        )

        session_data = StripeService.create_checkout_session(
            payment, success_url, cancel_url
        )

        if session_data:
            # Update payment status to processing
            payment.status = "processing"
            payment.save()

            response_serializer = StripeCheckoutSessionSerializer(session_data)
            return Response(response_serializer.data)
        else:
            return Response(
                {"error": "Failed to create checkout session"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except Payment.DoesNotExist:
        return Response(
            {"error": "Payment not found or cannot be retried"},
            status=status.HTTP_404_NOT_FOUND,
        )


# =====================
# 💰 REFUNDS (ADMIN)
# =====================


@extend_schema(
    tags=["Refunds"],
    summary="List all refunds (admin only)",
    description="Returns a list of all refund records in the system. Accessible only to admin users.",
)
class RefundListView(generics.ListAPIView):
    """List of all refunds (admin only)"""

    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return (
            Refund.objects.all()
            .select_related("payment", "payment__user", "created_by")
            .order_by("-created_at")
        )


@extend_schema(
    tags=["Refunds"],
    summary="Retrieve refund details (admin only)",
    description="Returns detailed information about a specific refund record. Accessible only to admin users.",
)
class RefundDetailView(generics.RetrieveAPIView):
    """Detail of a refund (admin only)"""

    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Refund.objects.all().select_related(
        "payment", "payment__user", "created_by"
    )


@extend_schema(
    tags=["Refunds"],
    summary="Create a refund (admin only)",
    description="Creates a refund for a specific payment. Automatically triggers the Stripe refund API and updates the refund status accordingly.",
)
@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def create_refund(request, payment_id):
    """Create a refund for a payment"""
    try:
        payment = get_object_or_404(Payment, id=payment_id)

        if not payment.can_be_refunded:
            return Response(
                {"error": "This payment cannot be refunded"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RefundCreateSerializer(
            data=request.data, context={"payment_id": payment_id}
        )

        if serializer.is_valid():
            with transaction.atomic():
                # Create refund
                refund = serializer.save(payment=payment, created_by=request.user)

                # Handle refund in Stripe
                success = StripeService.refund_payment(
                    payment, refund.amount, refund.reason
                )

                if success:
                    refund.process_refund()

                    # If full refund, cancel subscription
                    if refund.amount == payment.amount and payment.subscription:
                        PaymentService.cancel_subscription(payment.subscription)

                    response_serializer = RefundSerializer(refund)
                    return Response(
                        response_serializer.data, status=status.HTTP_201_CREATED
                    )
                else:
                    refund.status = "failed"
                    refund.save()
                    return Response(
                        {"error": "Failed to process refund"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Payment.DoesNotExist:
        return Response(
            {"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND
        )


# =====================
# ⚙️ STRIPE WEBHOOK
# =====================


@extend_schema(
    tags=["Stripe"],
    summary="Stripe Webhook endpoint",
    description="Webhook endpoint that handles Stripe events (e.g. successful payments, failed payments, refunds). Validates the event using Stripe signature.",
)
@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Webhook endpoint for Stripe"""
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        # Verify the event by constructing it with the Stripe library
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Failed to construct event from payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Failed signature verification
        return HttpResponse(status=400)

    # Handle the event
    success = WebhookService.process_stripe_webhook(event)

    if success:
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=400)


# =====================
# 📊 ANALYTICS
# =====================


@extend_schema(
    tags=["Analytics"],
    summary="Payment analytics and statistics (admin only)",
    description=(
        "Returns aggregated payment analytics, including total count, success rate, total and monthly revenue, "
        "average payment amount, and number of active subscriptions. Accessible only to admin users."
    ),
)
@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def payment_analytics(request):
    """Analytics and statistics about payments"""
    from django.db.models import Count, Sum, Avg
    from django.utils import timezone
    from datetime import timedelta

    # General statistics
    total_payments = Payment.objects.count()
    successful_payments = Payment.objects.filter(status="succeeded").count()
    total_revenue = (
        Payment.objects.filter(status="succeeded").aggregate(total=Sum("amount"))[
            "total"
        ]
        or 0
    )

    # Last month statistics
    last_month = timezone.now() - timedelta(days=30)
    monthly_payments = Payment.objects.filter(
        created_at__gte=last_month, status="succeeded"
    )
    monthly_revenue = monthly_payments.aggregate(total=Sum("amount"))["total"] or 0
    monthly_count = monthly_payments.count()

    # Middle payment amount
    avg_payment = (
        Payment.objects.filter(status="succeeded").aggregate(avg=Avg("amount"))["avg"]
        or 0
    )

    # Statistics about active subscriptions
    active_subscriptions = Payment.objects.filter(
        status="succeeded", subscription__status="active"
    ).count()

    return Response(
        {
            "total_payments": total_payments,
            "successful_payments": successful_payments,
            "success_rate": (
                (successful_payments / total_payments * 100)
                if total_payments > 0
                else 0
            ),
            "total_revenue": float(total_revenue),
            "monthly_revenue": float(monthly_revenue),
            "monthly_payments": monthly_count,
            "average_payment": float(avg_payment),
            "active_subscriptions": active_subscriptions,
            "period": {
                "from": last_month.isoformat(),
                "to": timezone.now().isoformat(),
            },
        }
    )
