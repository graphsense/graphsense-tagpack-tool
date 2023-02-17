from datetime import datetime


def try_parse_date(date, format="%Y-%m-%d"):
    """Trys to parse a date from a given object.

    Args:
        date (object): Description
        format (str, optional): date format string

    Returns:
        Union[str|object]: Either returns a parsed date or the original object
    """
    if date is not None and type(date) == str:
        try:
            return datetime.strptime(date, format)
        except ValueError:
            return date
    else:
        return date


def apply_to_dict_field(dictlike, field, fun, fail=True):
    if field in dictlike:
        dictlike[field] = fun(dictlike[field])
    elif fail:
        raise ValueError(f"Field {field} is not present in dictionary.")
