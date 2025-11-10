import stripe
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.subscribe.models import SubscriptionPlan

stripe.api_key = settings.STRIPE_SECRET_KEY


class Command(BaseCommand):
    help = "Fix Stripe integration by creating real products and prices"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreate even if stripe_price_id exists",
        )

    def handle(self, *args, **options):
        force = options["force"]

        # Check connection to Stripe
        try:
            stripe.Balance.retrieve()
            self.stdout.write(self.style.SUCCESS("✅ connection to Stripe worked!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error connecting to Stripe: {e}"))
            return

        # Handle subscription plans
        plans = SubscriptionPlan.objects.filter(is_active=True)

        for plan in plans:
            self.stdout.write(f"Handling plan: {plan.name}")

            # Check if we need to skip
            if (
                plan.stripe_price_id
                and not force
                and plan.stripe_price_id.startswith("price_1")
            ):
                self.stdout.write(
                    f"  ⏭️ Plan already has Stripe ID: {plan.stripe_price_id}"
                )
                continue

            try:
                # Create or update product
                product = stripe.Product.create(
                    name=plan.name,
                    description=f"Subscription plan: {plan.name}",
                    metadata={
                        "plan_id": plan.id,
                        "django_model": "SubscriptionPlan",
                        "created_by": "django_management_command",
                    },
                )
                self.stdout.write(f"  ✅ Product created: {product.id}")

                # Create price
                price = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(plan.price * 100),  # Per cents
                    currency="usd",
                    recurring={"interval": "month"},
                    metadata={"plan_id": plan.id, "django_model": "SubscriptionPlan"},
                )
                self.stdout.write(f"  ✅ Price created: {price.id}")

                # Update local plan
                old_id = plan.stripe_price_id
                plan.stripe_price_id = price.id
                plan.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ The plan has been updated: {old_id} → {price.id}"
                    )
                )

            except stripe.error.StripeError as e:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Error for plan {plan.name}: {e}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ General error for plan {plan.name}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS("🎉 Processing complete! Check Stripe Dashboard.")
        )
