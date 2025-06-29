from rest_framework import serializers
from .models import Category, Transaction, Tag


# Tag Serializer
class TagSerializer(serializers.ModelSerializer):
    """
    Serializer for the Tag model.
    Handles converting Tag instances to JSON format and vice versa.
    """
    class Meta:
        model = Tag
        fields = ['id', 'name']
        read_only_fields = ['id']


# Category Serializer
class CategorySerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    transaction_count = serializers.SerializerMethodField()
    """
    Serializer for the Category model.
    Handles the conversion of Category model instances to JSON format and vice versa.
    """
    class Meta:
        model = Category  # Specifies the model to serialize
        fields = ['id', 'name', 'created_by', 'transaction_count']  # Fields to include in the serialized output
        # 'id' is an auto-generated unique identifier
        # 'name' is the category name
        # 'created_by' is the user who created the category
        read_only_fields = ['id', 'created_by']

    def get_transaction_count(self, obj):
        # Count transactions linked to this category
        return obj.transactions.count()

    
# Transaction Serializer
class TransactionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)  # shows username
    category = serializers.CharField() 
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        write_only=True
    )
    is_recurring = serializers.BooleanField(required=False) 
    date = serializers.SerializerMethodField()
    time = serializers.SerializerMethodField()
    """
    Serializer for the Transaction model.
    Manages the representation of Transaction instances in API requests and responses.
    """
    class Meta:
        model = Transaction  # Specifies the model to serialize
        fields = ['id', 'user', 'category', 'amount', 'transaction_type', 'tags', 'is_recurring', 'description', 'date', 'time']
        # 'id': Auto-generated unique identifier for the transaction
        # 'user': ForeignKey to the user who created the transaction (read-only)
        # 'category': ForeignKey to the associated Category
        # 'amount': Monetary amount of the transaction
        # 'transaction_type': Specifies if the transaction is a 'credit' or 'debit'
        # 'date_time': The date and time the transaction was created
        read_only_fields = ['id', 'user', 'date', 'time']  # Ensures the fields is populated automatically and not editable by the client

    def get_date(self, obj):
        return obj.date_time.date().isoformat()  # e.g., "2025-04-16"

    def get_time(self, obj):
        return obj.date_time.time().strftime('%H:%M:%S')  # e.g., "09:26:19"
    
    def validate_category(self, value):
        """
        Convert category name to a Category instance.
        """
        user = self.context['request'].user
        try:
            return Category.objects.get(name__iexact=value.strip(), created_by=user)
        except Category.DoesNotExist:
            raise serializers.ValidationError(f'Category "{value}" does not exist for this user.')
        
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value
        
    def validate_transaction_type(self, value):
        """
        Ensure the transaction_type is either 'credit' or 'debit'.
        This will raise a ValidationError if the input is invalid.
        """
        if value not in ['credit', 'debit']:
            raise serializers.ValidationError("Transaction type must be 'credit' or 'debit'.")
        return value
    
    def _get_or_create_tags(self, tag_names, user):
        """
        Helper to fetch existing tags or create new ones for this user.
        """
        tags = []
        for tag_name in tag_names:
            tag, _ = Tag.objects.get_or_create(name=tag_name.strip(), created_by=user)
            tags.append(tag)
        return tags

    def create(self, validated_data):
        user = self.context['request'].user
        category = self.validate_category(self.initial_data['category'])
        tag_names = self.initial_data.get('tags', [])

        transaction = Transaction.objects.create(
            user=user,
            category=category,
            amount=validated_data['amount'],
            transaction_type=validated_data['transaction_type'],
            is_recurring=validated_data.get('is_recurring', False),
            description=validated_data.get('description', '')
        )
        tags = self._get_or_create_tags(tag_names, user)
        transaction.tags.set(tags)
        return transaction
    
    def update(self, instance, validated_data):
        """
        Handle update of an existing Transaction instance.

        - Only update fields that are passed
        - If 'category' is present in the request, re-validate it
        - Save and return the updated instance
        """
        # Update amount and type (if provided)
        instance.amount = validated_data.get('amount', instance.amount) 
        instance.transaction_type = validated_data.get('transaction_type', instance.transaction_type)
        instance.is_recurring = validated_data.get('is_recurring', instance.is_recurring)  # ✅ Add this line

        # If category is being updated, validate and assign it
        if 'category' in self.initial_data:
            instance.category = self.validate_category(self.initial_data['category'])

        # Update description
        instance.description = validated_data.get('description', instance.description)

        # Save and return the updated transaction
        instance.save()

        if 'tags' in self.initial_data:
            tag_names = self.initial_data.get('tags', [])
            tags = self._get_or_create_tags(tag_names, self.context['request'].user)
            instance.tags.set(tags)

        return instance
    
    def to_representation(self, instance):
        """
        Convert tag objects into list of tag names for output.
        """
        data = super().to_representation(instance)
        # Add tags back manually for output
        data['tags'] = [tag.name for tag in instance.tags.all()]
        return data

 
# SMS message parsing serializer
class MessageInputSerializer(serializers.Serializer):
    """
    For validating the message input to Smart Message Parser.
    """
    message = serializers.CharField()

# SMS-csv file parsing serializer 
class CSVUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    save_to_db = serializers.BooleanField(default=False)