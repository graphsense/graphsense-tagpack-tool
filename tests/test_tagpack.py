import json
from datetime import date

import pytest

from tagpack import ValidationError
from tagpack.tagpack import TagPack, Tag, collect_tagpack_files
from tagpack.tagpack_schema import TagPackSchema
from tagpack.taxonomy import Taxonomy


@pytest.fixture
def schema(monkeypatch):
    tagpack_schema = TagPackSchema()

    return tagpack_schema


@pytest.fixture
def taxonomies():
    tax_entity = Taxonomy('entity', 'http://example.com/entity')
    tax_entity.add_concept('exchange', 'Exchange', 'Some description')

    tax_abuse = Taxonomy('abuse', 'http://example.com/abuse')
    tax_abuse.add_concept('bad_coding', 'Bad coding', 'Really bad')

    taxonomies = {'entity': tax_entity, 'abuse': tax_abuse}
    return taxonomies


@pytest.fixture
def tagpack(schema, taxonomies):
    return TagPack('http://example.com',
                   {'title': 'Test TagPack',
                    'creator': 'GraphSense Team',
                    'source': 'http://example.com/my_addresses',
                    'currency': 'BTC',
                    'lastmod': date.fromisoformat('2021-04-21'),
                    'tags': [
                        {'label': 'Some attribution tag',
                         'address': '123Bitcoin45'
                         },  # inherits all header fields
                        {'label': 'Another attribution tag',
                         'address': '123Bitcoin66',
                         'context': '{"counts": 1}',
                         'currency': 'ETH',
                         }  # overrides currency
                    ]},
                   schema,
                   taxonomies)


def test_all_header_fields(tagpack, schema):
    h = ['title', 'creator', 'source', 'currency', 'lastmod', 'tags']

    assert all(field in tagpack.all_header_fields
               for field in
               h)
    assert len(h) == len(tagpack.all_header_fields)

    assert tagpack.all_header_fields.get('creator') == 'GraphSense Team'
    assert tagpack.all_header_fields.get('title') == 'Test TagPack'


def test_header_fields(tagpack):
    h = ['title', 'creator', 'tags']

    assert all(field in tagpack.header_fields
               for field in h)
    assert len(h) == len(tagpack.header_fields)


def test_explicit_tag_fields(tagpack):
    tag = tagpack.tags[0]
    t = ['label', 'address']
    assert all(field in tag.explicit_fields for field in t)
    assert len(t) == len(tag.explicit_fields)

    tag = tagpack.tags[1]
    t = ['label', 'address', 'context', 'currency']
    assert all(field in tag.explicit_fields for field in t)
    assert len(t) == len(tag.explicit_fields)


def test_tag_inherits_from_header(tagpack):
    t = tagpack.tags[0]

    assert t.all_fields.get('currency') == 'BTC'


def test_tag_overrides_header(tagpack):
    t = tagpack.tags[1]

    assert t.all_fields.get('currency') == 'ETH'


def test_init(tagpack):
    assert tagpack.uri == 'http://example.com'
    assert isinstance(tagpack.contents, dict)
    assert tagpack.contents['title'] == 'Test TagPack'
    assert isinstance(tagpack.schema, TagPackSchema)
    assert 'title' in tagpack.schema.header_fields
    assert isinstance(tagpack.taxonomies, dict)


def test_tag_fields(tagpack):
    assert 'lastmod' in tagpack.tag_fields
    assert 'creator' not in tagpack.tag_fields
    tagpack.contents['currency'] = 'BTC'
    assert 'currency' in tagpack.tag_fields


def test_tags(tagpack):
    assert len(tagpack.tags) == 2
    tagpack.contents['tags'] = [
        {'label': 'Some attribution tag',
         'address': '123Bitcoin45'},
        {'label': 'Some attribution tag',
         'address': 1234},
    ]
    assert len(tagpack.tags) == 2
    assert isinstance(tagpack.tags[0], Tag)
    assert isinstance(tagpack.tags[1], Tag)


def test_tags_from_contents(tagpack):
    contents = {'label': 'Some attribution tag', 'address': '12dv44'}
    assert isinstance(Tag.from_contents(contents, tagpack), Tag)


def test_tags_explicit_fields(tagpack):
    assert len(tagpack.tags) == 2
    all(x in ['label', 'address'] for x in tagpack.tags[0].explicit_fields)
    tagpack.contents['tags'] = [
        {'label': 'Some attribution tag',
         'entity': 1234},
    ]
    all(x in ['label', 'entity'] for x in tagpack.tags[0].explicit_fields)


def test_tags_all_fields(tagpack):
    assert len(tagpack.tags) == 2
    all(x in ['label', 'address', 'lastmod']
        for x in tagpack.tags[0].all_fields)
    tagpack.contents['tags'] = [
        {'label': 'Some attribution tag',
         'entity': 1234},
    ]
    all(x in ['label', 'entity', 'lastmod']
        for x in tagpack.tags[0].all_fields)


def test_tag_to_json(tagpack):
    for tag in tagpack.tags:
        json = tag.to_json()
        assert 'lastmod' in json
        assert 'address' in json
        assert 'label' in json


def test_tag_to_str(tagpack):
    assert 'label' in tagpack.tags[0].__str__()
    assert 'lastmod' in tagpack.tags[0].__str__()
    assert '123Bitcoin45' in tagpack.tags[0].__str__()


def test_tagpack_to_json(tagpack):
    json = tagpack.to_json()
    assert 'uri' in json
    assert 'title' in json
    assert 'creator' in json
    assert 'lastmod' not in json


def test_tagpack_to_str(tagpack):
    s = tagpack.__str__()
    assert 'Test TagPack' in s
    assert 'GraphSense Team' in s

# TagPack validation tests


def test_validate(tagpack):
    assert tagpack.validate()


def test_context_is_valid_json(tagpack):
    assert json.loads(tagpack.contents['tags'][1]['context'])

    assert "context" not in tagpack.contents['tags'][0].keys()


def test_validate_undefined_field(tagpack):
    tagpack.contents['failfield'] = 'some value'

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Field failfield not allowed in header" in str(e.value)


def test_validate_fail_type_text(tagpack):
    tagpack.contents['title'] = 5

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Field title must be of type text" in str(e.value)


def test_validate_fail_type_date(tagpack):
    tagpack.contents['lastmod'] = 5

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Field lastmod must be of type datetime" in str(e.value)


def test_validate_fail_missing(tagpack):
    del tagpack.contents['creator']

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Mandatory header field creator missing" in str(e.value)


def test_validate_fail_missing_body(tagpack):
    del tagpack.contents['tags'][0]['label']

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Mandatory tag field label missing" in str(e.value)


def test_validate_fail_missing_address(tagpack):
    del tagpack.contents['tags'][0]['address']

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    print(e.value)
    assert "Mandatory tag field address missing" in str(e.value)


def test_validate_fail_is_cluster_definer(tagpack):
    tagpack.contents['is_cluster_definer'] = 3

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Field is_cluster_definer must be of type boolean" in str(e.value)


def test_validate_fail_taxonomy(tagpack):
    tagpack.contents['tags'][1]['category'] = 'UNKNOWN'

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Undefined concept UNKNOWN in field category" in str(e.value)


def test_validate_fail_taxonomy_header(tagpack):
    tagpack.contents['category'] = 'unknown'

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Undefined concept unknown in field category" in str(e.value)


def test_validate_fail_empty_header_field(tagpack):
    tagpack.contents['label'] = None

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Value of header field label must not be empty (None)" \
        in str(e.value)


def test_validate_fail_empty_body_field(tagpack):
    tagpack.contents['tags'][0]['label'] = None

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Value of body field label must not be empty (None)" \
        in str(e.value)


def test_simple_file_collection():
    prefix = 'tests/testfiles/simple/'
    files, headerfile_path = collect_tagpack_files(prefix)

    assert len(files) == 4
    assert f'{prefix}ex_addr_tagpack.yaml' in files
    assert f'{prefix}duplicate_tag.yaml' in files
    assert f'{prefix}empty_tag_list.yaml' in files
    assert f'{prefix}multiple_tags_for_address.yaml' in files


def test_file_collection_with_yaml_include():
    files, headerfile_path = collect_tagpack_files('tests/testfiles/yaml_inclusion/')

    assert len(files) == 4
    assert 'tests/testfiles/yaml_inclusion/2021/01/20210101.yaml' in files
    assert 'tests/testfiles/yaml_inclusion/2021/01/20210102.yaml' in files
    assert 'tests/testfiles/yaml_inclusion/2021/02/20210201.yaml' in files
    assert 'tests/testfiles/yaml_inclusion/2021/01/special/20210106-special.yaml' in files

    assert headerfile_path == 'tests/testfiles/yaml_inclusion'


def test_file_collection_with_missing_yaml_include_raises_exception():
    files, headerfile_path = collect_tagpack_files('tests/testfiles/yaml_inclusion_missing_header/')

    assert not headerfile_path

    with pytest.raises(FileNotFoundError) as e:
        TagPack.load_from_file(None, files[0], None, None, headerfile_path)
    assert "No such file or directory: 'header.yaml'" \
        in str(e.value)


def test_load_from_file_addr_tagpack(taxonomies):
    tagpack = TagPack.load_from_file('http://example.com/packs/ex_addr_tagpack.yaml',
                                     'tests/testfiles/simple/ex_addr_tagpack.yaml',
                                     TagPackSchema(),
                                     taxonomies)
    assert isinstance(tagpack, TagPack)
    assert tagpack.uri == \
        'http://example.com/packs/ex_addr_tagpack.yaml'
    assert tagpack.contents['title'] == 'Test Address TagPack'
    assert isinstance(tagpack.schema, TagPackSchema)
    assert 'title' in tagpack.schema.header_fields
    assert isinstance(tagpack.taxonomies, dict)


def test_yaml_inclusion(taxonomies):
    tagpack = TagPack.load_from_file('http://example.com/',
                                     'tests/testfiles/yaml_inclusion/2021/01/20210101.yaml',
                                     TagPackSchema(),
                                     taxonomies,
                                     'tests/testfiles/yaml_inclusion')
    assert isinstance(tagpack, TagPack)
    assert 'title' in tagpack.schema.header_fields
    assert tagpack.contents['title'] == 'BadHack TagPack'
    assert tagpack.contents['abuse'] == 'scam'
    assert tagpack.tags[0].contents['address'] == 'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh'
    assert tagpack.tags[0].contents['context'] == '{"validated": true}'


def test_yaml_inclusion_overwrite_abuse(taxonomies):
    tagpack = TagPack.load_from_file('http://example.com/',
                                     'tests/testfiles/yaml_inclusion/2021/02/20210201.yaml',
                                     TagPackSchema(),
                                     taxonomies,
                                     'tests/testfiles/yaml_inclusion')
    assert isinstance(tagpack, TagPack)
    assert tagpack.contents['title'] == 'BadHack TagPack'
    assert tagpack.tags[0].contents['address'] == '1Ai52Uw6usjhpcDrwSmkUvjuqLpcznUuyF'
    assert tagpack.tags[0].contents['abuse'] == 'sextortion'


def test_empty_tag_list_raises():
    tagpack = TagPack.load_from_file('http://example.com/packs',
                                     'tests/testfiles/simple/empty_tag_list.yaml',
                                     TagPackSchema(),
                                     taxonomies)

    with pytest.raises(ValidationError) as e:
        tagpack.validate()


def test_multiple_tags_for_one_address_work():
    tagpack = TagPack.load_from_file('http://example.com/packs',
                                     'tests/testfiles/simple/multiple_tags_for_address.yaml',
                                     TagPackSchema(),
                                     taxonomies)
    assert len(tagpack.tags) == 2
    tagpack.validate()


def test_duplicate_does_not_raise_only_inform(capsys):
    tagpack = TagPack.load_from_file('http://example.com/packs',
                                     'tests/testfiles/simple/duplicate_tag.yaml',
                                     TagPackSchema(),
                                     taxonomies)

    tagpack.validate()
    captured = capsys.readouterr()

    assert "1 duplicate(s) found" in captured.out
    assert len(tagpack.get_unique_tags()) == 1
