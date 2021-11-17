from datetime import date
import pytest

from tagpack import TagPackFileError, ValidationError
from tagpack.tagpack import TagPack, Tag, AddressTag, EntityTag
from tagpack.tagpack_schema import TagPackSchema
from tagpack.taxonomy import Taxonomy


@pytest.fixture
def schema(monkeypatch):

    def mock_load_schema(*args, **kwargs):
        pass

    tagpack_schema = TagPackSchema()

    return tagpack_schema


@pytest.fixture
def taxonomies():
    tax_entity = Taxonomy('entity', 'http://example.com/entity')
    tax_entity.add_concept('exchange', 'Exchange', 'Some description')

    tax_abuse = Taxonomy('abuse', 'http://example.com/abuse')
    tax_abuse.add_concept('bad_coding', 'Bad coding', 'Really bad')

    taxonomies = {}
    taxonomies['entity'] = tax_entity
    taxonomies['abuse'] = tax_abuse
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
                         }
                    ]},
                   schema,
                   taxonomies)


def test_init(tagpack):
    assert tagpack.uri == 'http://example.com'
    assert isinstance(tagpack.contents, dict)
    assert tagpack.contents['title'] == 'Test TagPack'
    assert isinstance(tagpack.schema, TagPackSchema)
    assert 'title' in tagpack.schema.header_fields
    assert isinstance(tagpack.taxonomies, dict)


def test_load_from_file_addr_tagpack(schema, taxonomies):
    tagpack = TagPack.load_from_file('http://example.com/',
                                     'tests/testfiles/ex_addr_tagpack.yaml',
                                     schema,
                                     taxonomies)
    assert isinstance(tagpack, TagPack)
    assert tagpack.uri == \
        'http://example.com/tests/testfiles/ex_addr_tagpack.yaml'
    assert tagpack.contents['title'] == 'Test Address TagPack'
    assert isinstance(tagpack.schema, TagPackSchema)
    assert 'title' in tagpack.schema.header_fields
    assert isinstance(tagpack.taxonomies, dict)


def test_load_from_file_entity_tagpack(schema, taxonomies):
    tagpack = TagPack.load_from_file('http://example.com/',
                                     'tests/testfiles/ex_entity_tagpack.yaml',
                                     schema,
                                     taxonomies)
    assert isinstance(tagpack, TagPack)
    assert tagpack.uri == \
        'http://example.com/tests/testfiles/ex_entity_tagpack.yaml'
    assert tagpack.contents['title'] == 'Test Entity TagPack'
    assert isinstance(tagpack.schema, TagPackSchema)
    assert 'title' in tagpack.schema.header_fields
    assert isinstance(tagpack.taxonomies, dict)


def test_all_header_fields(tagpack, schema):
    assert all(field in tagpack.all_header_fields
               for field in ['title', 'creator', 'lastmod', 'tags'])


def test_header_fields(tagpack):
    assert all(field in tagpack.header_fields
               for field in ['title', 'creator'])


def test_generic_tag_fields(tagpack):
    assert 'lastmod' in tagpack.generic_tag_fields
    assert 'creator' not in tagpack.generic_tag_fields
    tagpack.contents['currency'] = 'BTC'
    assert 'currency' in tagpack.generic_tag_fields


def test_tags(tagpack):
    assert len(tagpack.tags) == 1
    assert isinstance(tagpack.tags[0], AddressTag)
    tagpack.contents['tags'] = [
        {'label': 'Some attribution tag',
         'address': '123Bitcoin45'},
        {'label': 'Some attribution tag',
         'entity': 1234},
    ]
    assert len(tagpack.tags) == 2
    assert isinstance(tagpack.tags[0], AddressTag)
    assert isinstance(tagpack.tags[1], EntityTag)


def test_tags_from_contents(tagpack):
    contents = {'label': 'Some attribution tag', 'address': '12dv44'}
    assert isinstance(Tag.from_contents(contents, tagpack), AddressTag)
    contents = {'label': 'Some attribution tag', 'entity': 1234}
    assert isinstance(Tag.from_contents(contents, tagpack), EntityTag)
    contents = {'label': 'Some attribution tag', 'something': 'bla'}
    with(pytest.raises(TagPackFileError)) as e:
        assert isinstance(Tag.from_contents(contents, tagpack), EntityTag)
    assert "Tag must be assigned to address or entity" in str(e.value)


def test_tags_explicit_fields(tagpack):
    assert len(tagpack.tags) == 1
    all(x in ['label', 'address'] for x in tagpack.tags[0].explicit_fields)
    tagpack.contents['tags'] = [
        {'label': 'Some attribution tag',
         'entity': 1234},
    ]
    all(x in ['label', 'entity'] for x in tagpack.tags[0].explicit_fields)


def test_tags_all_fields(tagpack):
    assert len(tagpack.tags) == 1
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

    with pytest.raises(TagPackFileError) as e:
        tagpack.validate()
    assert "Tag must be assigned to address or entity" in str(e.value)


def test_validate_fail_is_cluster_definer(tagpack):
    tagpack.contents['is_cluster_definer'] = 3

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Field is_cluster_definer must be of type boolean" in str(e.value)


def test_validate_fail_taxonomy(tagpack):
    tagpack.contents['tags'][0]['category'] = 'unknown'

    with pytest.raises(ValidationError) as e:
        tagpack.validate()
    assert "Undefined concept unknown in field category" in str(e.value)


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
