# -*- coding: utf-8 -*-
import pytest
from tagpack.tagstore import _perform_address_modifications, TagStore

from tagstore.db import TagstoreDbAsync


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

    assert list(composition) == [('GraphSense Team', 'private', 'BTC', 2, 2), ('GraphSense Team', 'public', 'BTC', 2, 6)]

    actorc = ts.get_tags_with_actors_count()

    assert actorc == 1

    usedActorC = ts.get_used_actors_count()

    assert usedActorC == 1

    tags = ts.list_tags()

    full_tags = ts.dump_tags()

    assert len(tags) == len(full_tags)

    tags = ts.list_tags(unique=True)

    label_index = 2
    indent_index = 13
    tag_type_index = 17
    tag_subject_index = 18

    assert {x[label_index] for x in tags} == {"othertag", "sometag", "sometag.info", "test"}
    assert {x[indent_index] for x in full_tags} == {"0xdeadbeef", "1bacdeddg32dsfk5692dmn23", "3bacadsfg3sdfafd2deddg32"}
    assert {x[tag_type_index] for x in full_tags} == {"actor"}
    assert {x[tag_subject_index] for x in full_tags} == {"address", "tx"}

    assert {x[indent_index] for x in full_tags if x[tag_subject_index] == "tx"} == {"0xdeadbeef"}

    actors = ts.list_actors()

    actor_id_index = 1

    assert {x[actor_id_index] for x in actors} == {"binance","internet_archive"}

@pytest.mark.asyncio
async def test_db_url(db_setup):
    db = TagstoreDbAsync.from_url(db_setup["db_connection_string_async"])
    assert list(await db.get_acl_groups()) == ['private', 'public']

    tags = await db.get_tags_by_subjectid("1bacdeddg32dsfk5692dmn23", offset=None, page_size=None, groups=['private', 'public'])

    tags_pub = await db.get_tags_by_subjectid("1bacdeddg32dsfk5692dmn23", offset=None, page_size=None, groups=['private'])

    assert len(tags) == 5
    assert len(tags_pub) == 0


    addr = {t.identifier for t in tags }
    assert  addr == {"1bacdeddg32dsfk5692dmn23"}

    tags = await db.get_tags_by_subjectid("0xdeadbeef", offset=None, page_size=None, groups=['private', 'public'])

    tags_pub = await db.get_tags_by_subjectid("0xdeadbeef", offset=None, page_size=None, groups=['public'])


    assert len(tags) == 1
    assert len(tags_pub) == 0

    addr = {t.identifier for t in tags }
    assert  addr == {"0xdeadbeef"}
