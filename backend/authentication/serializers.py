from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "projects",
            "selected_project",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "date_joined", "projects"]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs.get("new_password") != attrs.get("confirm_password"):
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match"}
            )
        return attrs


class SetRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "username", "password", "role", "projects"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        # Use create_user for proper password hashing
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class ProjectSerializer(serializers.Serializer):
    """Serializer for Plane Project data"""

    id = serializers.CharField()
    name = serializers.CharField()
    identifier = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    workspace = serializers.CharField(required=False)
    members = serializers.ListField(required=False)
    created_at = serializers.CharField(required=False)
    updated_at = serializers.CharField(required=False)


class SelectedProjectSerializer(serializers.Serializer):
    """Serializer for setting selected project"""

    project_id = serializers.CharField(required=True)

class UserAPIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        from .models import UserAPIKey
        model = UserAPIKey
        fields = ["provider", "api_key", "updated_at"]
        extra_kwargs = {'api_key': {'write_only': True}}
