from datetime import datetime
from urllib.parse import urlparse


def strip_values(listlike, values):
    return [x for x in listlike if x not in values]


def strip_none(listlike):
    return strip_values(listlike, [None])


def strip_empty(listlike):
    return strip_values(listlike, [None, "", []])


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


def apply_to_dict_field(dictlike, field: str, fun, fail=True):
    """Summary

    Args:
        dictlike (dict): something dict like
        field (str): Field to apply the function on
        fun (TYPE): Function to apply, must take one parameter
        fail (bool, optional): If True the function throws and error
        if field is not present

    Raises:
        ValueError: Description
    """
    if field in dictlike:
        dictlike[field] = fun(dictlike[field])
    elif fail:
        raise ValueError(f"Field {field} is not present in dictionary.")


def get_secondlevel_domain(url: str) -> str:
    """Summary

    Args:
        url (str): url to parse

    Returns:
        str: top level domain
    """
    if not url.startswith("http"):
        url = f"http://{url}"
    pu = urlparse(url).netloc
    frag = pu.split(".")
    if len(frag) < 2:
        return ".".join(frag)
    else:
        co_domain = frag[-2] == "co"
        return ".".join(frag[-3:] if co_domain else frag[-2:])
