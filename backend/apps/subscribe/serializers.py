from rest_framework import serializers
from django.utils import timezone
from .models import SubscriptionPlan, Subscription, PinnedPost, SubscriptionHistory


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for Subscription Plan"""

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "name",
            "price",
            "duration_days",
            "features",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def to_representation(self, instance):
        """Representation with features as object"""
        data = super().to_representation(instance)

        # Features as object
        if not data.get("features"):
            data["features"] = {}

        return data


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Subscription"""

    plan_info = SubscriptionPlanSerializer(source="plan", read_only=True)
    user_info = serializers.SerializerMethodField()
    is_active = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()

    class Meta:
        model = Subscription
        fields = [
            "id",
            "user",
            "user_info",
            "plan",
            "plan_info",
            "status",
            "start_date",
            "end_date",
            "auto_renew",
            "is_active",
            "days_remaining",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "status",
            "start_date",
            "end_date",
            "created_at",
            "updated_at",
        ]

    def get_user_info(self, obj):
        """Back user info"""
        return {
            "id": obj.user.id,
            "username": obj.user.username,
            "full_name": obj.user.full_name,
            "email": obj.user.email,
        }


class SubscriptionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Subscription"""

    class Meta:
        model = Subscription
        fields = ["plan"]

    def validate_plan(self, value):
        """Tarif plan validation"""
        if not value.is_active:
            raise serializers.ValidationError("Selected plan is not active.")
        return value

    def validate(self, attrs):
        """General validation"""
        user = self.context["request"].user

        # Check for existing active subscription
        if hasattr(user, "subscription") and user.subscription.is_active():
            raise serializers.ValidationError(
                {"non_field_errors": ["User already has an active subscription."]}
            )

        return attrs

    def create(self, validated_data):
        """Create subscription with default values"""
        validated_data["user"] = self.context["request"].user
        validated_data["status"] = "pending"
        validated_data["start_date"] = timezone.now()
        validated_data["end_date"] = timezone.now()
        return super().create(validated_data)


class PinnedPostSerializer(serializers.ModelSerializer):
    """Serializer for Pinned Post"""

    post_info = serializers.SerializerMethodField()

    class Meta:
        model = PinnedPost
        fields = ["id", "post", "post_info", "pinned_at"]
        read_only_fields = ["id", "pinned_at"]

    def get_post_info(self, obj):
        """Back post info"""
        request = self.context.get('request')
        post = obj.post
        image_url = None
        if post.image:
            image_url = (
                request.build_absolute_uri(post.image.url)
                if request else post.image.url
            )

        return {
            "id": post.id,
            "title": post.title,
            "slug": post.slug,
            "content": post.content,
            "image": image_url,  # 
            "views_count": post.views_count,
            "created_at": post.created_at,
        }
            
        
        # return {
        #     "id": obj.post.id,
        #     "title": obj.post.title,
        #     "slug": obj.post.slug,
        #     "content": obj.post.content,
        #     "image": obj.post.image,
        #     "views_count": obj.post.views_count,
        #     "created_at": obj.post.created_at,
        # }

    def validate_post(self, value):
        """Validation of the post to be pinned"""
        user = self.context["request"].user

        # Check post ownership
        if value.author != user:
            raise serializers.ValidationError("You can ony pinned your posts.")

        # Check post status
        if value.status != "published":
            raise serializers.ValidationError("Only published posts can be pinned.")

        return value

    def validete(self, attrs):
        """General validation"""
        user = self.context["request"].user

        # Check active subscription
        if not hasattr(user, "subscription") or not user.subscription.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": ["Active subscription required to pin posts."]}
            )

        return attrs

    def create(self, validated_data):
        """Create pinned post"""
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class SubscriptionHistorySerializer(serializers.ModelSerializer):
    """Serializer for Subscription History"""

    class Meta:
        model = SubscriptionHistory
        fields = ["id", "action", "description", "metadata", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserSubscriptionStatusSerializer(serializers.Serializer):
    """Serializer for user's subscription status"""

    has_subscription = serializers.BooleanField()
    is_active = serializers.BooleanField()
    subscription = SubscriptionSerializer(allow_null=True)
    pinned_post = PinnedPostSerializer(allow_null=True)
    can_pin_posts = serializers.BooleanField()

    def to_representation(self, instance):
        """Formatting representation of the user's subscription status"""
        user = instance
        has_subscription = hasattr(user, "subscription")
        subscription = user.subscription if has_subscription else None
        is_active = subscription.is_active if subscription else False
        pinned_post = getattr(user, "pinned_post", None) if is_active else None

        return {
            "has_subscription": has_subscription,
            "is_active": is_active,
            "subscription": (
                SubscriptionSerializer(subscription).data if subscription else None
            ),
            "pinned_post": (
                PinnedPostSerializer(pinned_post).data if pinned_post else None
            ),
            "can_pin_posts": is_active,
        }


class PinPostSerializer(serializers.Serializer):
    """Serializer for pinning a post"""

    post_id = serializers.IntegerField()

    def validate_post_id(self, value):
        """Validation of the post to be pinned"""
        from apps.main.models import Post

        try:
            post = Post.objects.get(id=value, status="published")
        except Post.DoesNotExist:
            raise serializers.ValidationError("Post not found or not published.")

        user = self.context["request"].user
        if post.author != user:
            raise serializers.ValidationError("You can only pin your own posts.")

        return value

    def validate(self, attrs):
        """General validation"""
        user = self.context["request"].user

        # Check active subscription
        if not hasattr(user, "subscription") or not user.subscription.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": ["Active subscription required to pin posts."]}
            )

        return attrs


class UnpinPostSerializer(serializers.Serializer):
    """Serializer for unpinning a post"""

    def validate(self, attrs):
        """Validation of existing pinned post"""
        user = self.context["request"].user

        if not hasattr(user, "pinned_post"):
            raise serializers.ValidationError(
                {"non_field_errors": ["No pinned post found."]}
            )

        return attrs
