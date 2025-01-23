# -*- coding: utf-8 -*-

from tagpack.tagstore import _perform_address_modifications, TagStore


def test_bch_conversion():
    cashaddr = "bitcoincash:prseh0a4aejjcewhc665wjqhppgwrz2lw5txgn666a"

    # as per https://bch.btc.com/tools/address-converter
    expected = "3NFvYKuZrxTDJxgqqJSfouNHjT1dAG1Fta"
    result = _perform_address_modifications(cashaddr, "BCH")

    assert expected == result


def test_eth_conversion():
    checksumaddr = "0xC61b9BB3A7a0767E3179713f3A5c7a9aeDCE193C"

    expected = "0xc61b9bb3a7a0767e3179713f3a5c7a9aedce193c"
    result = _perform_address_modifications(checksumaddr, "ETH")

    assert expected == result


def test_db_consistency(db_setup):
    # this is all based on the tagpacks inserted in conftest.py

    ts = TagStore(db_setup["db_connection_string"], 'public')

    repos = ts.tagstore_source_repos()

    assert(len(repos) == 5)

    addresses = ts.get_addresses(update_existing=True)

    assert list(addresses) == [('3bacadsfg3sdfafd2deddg32', 'BTC'), ('1bacdeddg32dsfk5692dmn23', 'BTC')]

    composition = ts.get_tagstore_composition(by_network=True)

    assert list(composition) == [('GraphSense Team', 'private', 'BTC', 1, 1), ('GraphSense Team', 'public', 'BTC', 2, 6)]

    actorc = ts.get_tags_with_actors_count()

    assert actorc == 1

    usedActorC = ts.get_used_actors_count()

    assert usedActorC == 1
