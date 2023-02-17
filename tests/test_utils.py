from tagpack.utils import get_secondlevel_domain


def test_tld_extraction():
    assert get_secondlevel_domain("abc.co.uk") == "abc.co.uk"
    assert get_secondlevel_domain("spam.abc.co.uk") == "abc.co.uk"
    assert get_secondlevel_domain("spam.uk") == "spam.uk"
    assert get_secondlevel_domain("www.spam.uk") == "spam.uk"
