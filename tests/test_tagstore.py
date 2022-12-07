# -*- coding: utf-8 -*-

from tagpack.tagstore import _perform_address_modifications


def test_bch_conversion():
    cashaddr = 'bitcoincash:prseh0a4aejjcewhc665wjqhppgwrz2lw5txgn666a'

    # as per https://bch.btc.com/tools/address-converter
    expected = '3NFvYKuZrxTDJxgqqJSfouNHjT1dAG1Fta'
    result = _perform_address_modifications(cashaddr, 'BCH')

    assert expected == result


def test_eth_conversion():
    checksumaddr = '0xC61b9BB3A7a0767E3179713f3A5c7a9aeDCE193C'

    expected = '0xc61b9bb3a7a0767e3179713f3a5c7a9aedce193c'
    result = _perform_address_modifications(checksumaddr, 'ETH')

    assert expected == result

