def apply_filters(query, model_class, filters):
    """
    Apply simple equality and like filters to a SQLAlchemy query based on filters dict.
    """
    for key, value in filters.items():
        if hasattr(model_class, key):
            column = getattr(model_class, key)
            if isinstance(value, str) and '%' in value:
                query = query.filter(column.like(value))
            else:
                query = query.filter(column == value)
    return query
