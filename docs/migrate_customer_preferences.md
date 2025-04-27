# Migrating Customer Preferences from JSONFields to ManyToMany

This document explains how to migrate the Customer model's preference fields from JSONFields to proper ManyToMany relationships.

## Background

Previously, the Customer model used JSONFields for:
- `field_of_activity`
- `product_preferences`
- `purchase_preferences`

These fields have been converted to ManyToMany relationships with the following models:
- `ActivityField`
- `ProductPreference`
- `PaymentPreference`

## Benefits of the Change

1. **Better data integrity**: Values will be constrained to valid choices
2. **Easier querying**: More efficient querying of customers by preferences
3. **Consistent UI**: Multiple-choice widgets in admin and forms work properly
4. **Improved performance**: ManyToMany relations perform better than large JSON fields
5. **Better migrations**: Django handles ManyToMany changes better than JSON fields

## How to Apply the Changes

There are two ways to apply these changes:

### Option 1: Run Django Migrations

```bash
python manage.py migrate
```

The migration files `0080_create_preference_models_and_relations.py` and `0081_replace_jsonfields_with_manytomany.py` will:
1. Create the new models
2. Create temporary ManyToMany fields
3. Migrate data from JSONFields to the temporary fields
4. Remove the JSONFields
5. Rename the temporary fields to their final names

### Option 2: Custom Management Command

For more control over the migration process, you can use the custom management command:

```bash
python manage.py migrate_customer_preferences
```

This command will:
1. Create all necessary preference objects
2. Migrate existing customer data to use the new relationships

## After Migration

After the migration is complete, the Customer model will have these fields:

```python
field_of_activity = models.ManyToManyField(
    ActivityField,
    verbose_name=_("حیطه فعالیت"),
    blank=True,
    related_name='customers'
)

purchase_preferences = models.ManyToManyField(
    PaymentPreference,
    verbose_name=_("ترجیحات پرداخت"),
    blank=True,
    related_name='customers'
)

product_preferences = models.ManyToManyField(
    ProductPreference,
    verbose_name=_("ترجیحات کالایی"),
    blank=True,
    related_name='customers'
)
```

The model also provides property methods for easy access to codes:
- `field_of_activity_list` (getter and setter)
- `purchase_preferences_list` (getter and setter)
- `product_preferences_list` (getter and setter)

## Troubleshooting

If you encounter any issues during the migration:

1. Check that all new models exist: `ActivityField`, `ProductPreference`, and `PaymentPreference`
2. Verify that each preference choice has a corresponding object in its model
3. Run the management command to manually fill in any missing data:
   ```bash
   python manage.py migrate_customer_preferences
   ```
4. Check the Customer forms in the admin interface to make sure the fields display correctly

## Code Compatibility

All existing code that used the properties like `customer.field_of_activity_list` will continue to work
as before. These properties now interact with the ManyToMany relationships instead of JSONFields.

## Admin Usage

The new related models are registered in the admin interface, allowing you to:
1. View all preference objects
2. See which customers are using each preference
3. Modify the display names of preferences if needed 