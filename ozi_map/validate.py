import types


class ValidationError(Exception):
    pass


def validate_number(value):
    assert isinstance(value, (str,))
    try:
        return int(value)
    except ValueError:
        raise ValidationError('"%s" is not a number' % value[:50])


def validate_float(value):
    assert isinstance(value, (str,))
    try:
        return float(value)
    except ValueError:
        raise ValidationError('"%s" is not a floating point number' % value[:50])


def validate_string_start(value, pattern):
    assert isinstance(value, (str,))
    if not value.startswith(pattern):
        raise ValidationError(' does not start with "%s"' % (pattern[:50]))
    else:
        return value


def validate_value(value, pattern):
    assert isinstance(value, (str,))
    if value != pattern:
        raise ValidationError('"%s" instead of "%s"' % (value[:50], pattern[:50]))
    else:
        return value


def validate_notempty(value):
    assert isinstance(value, (str,))
    if value == '':
        raise ValidationError('String empty')
    else:
        return value


def validate_values(value, patterns):
    assert isinstance(value, (str,))
    if value not in patterns:
        raise ValidationError('"%s" is not one of %s' % (value[:50], ', '.join(['"%s"' % s for s in patterns])))
    else:
        return value
