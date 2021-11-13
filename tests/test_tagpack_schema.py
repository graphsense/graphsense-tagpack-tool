from datetime import date
import pytest

from tagpack.tagpack_schema import TagPackSchema, ValidationError
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


def test_init(schema):
    assert isinstance(schema, TagPackSchema)
    assert schema.definition == 'tagpack_schema.yaml'


def test_header_fields(schema):
    assert isinstance(schema.header_fields, dict)
    assert 'tags' in schema.header_fields
    assert 'title' in schema.header_fields
    assert 'type' in schema.header_fields['title']
    assert 'text' in schema.header_fields['title']['type']
    assert 'mandatory' in schema.header_fields['title']
    assert schema.header_fields['title']['mandatory'] is True


def test_mandatory_header_fields(schema):
    assert isinstance(schema.mandatory_header_fields, dict)
    assert 'title' in schema.mandatory_header_fields
    assert 'tags' in schema.mandatory_header_fields
    assert 'notmandatory' not in schema.mandatory_header_fields


def test_generic_tag_fields(schema):
    assert isinstance(schema.generic_tag_fields, dict)
    assert 'label' in schema.generic_tag_fields
    assert 'type' in schema.generic_tag_fields['label']
    assert 'mandatory' in schema.generic_tag_fields['label']


def test_address_tag_fields(schema):
    assert 'address' in schema.address_tag_fields
    assert 'label' in schema.address_tag_fields
    assert 'entity' not in schema.address_tag_fields
    assert isinstance(schema.address_tag_fields, dict)


def test_mandatory_address_tag_fields(schema):
    assert isinstance(schema.mandatory_address_tag_fields, dict)
    assert 'address' in schema.mandatory_address_tag_fields
    assert 'label' in schema.mandatory_address_tag_fields
    assert 'created' not in schema.mandatory_address_tag_fields
    assert 'lastmod' not in schema.mandatory_address_tag_fields


def test_entity_tag_fields(schema):
    assert 'entity' in schema.entity_tag_fields
    assert 'label' in schema.entity_tag_fields
    assert 'address' not in schema.entity_tag_fields
    assert isinstance(schema.entity_tag_fields, dict)


def test_mandatory_entity_tag_fields(schema):
    assert isinstance(schema.mandatory_entity_tag_fields, dict)
    assert 'entity' in schema.mandatory_entity_tag_fields
    assert 'label' in schema.mandatory_entity_tag_fields
    assert 'lastmod' not in schema.mandatory_entity_tag_fields


def test_all_tag_fields(schema):
    assert isinstance(schema.all_tag_fields, dict)
    assert 'address' in schema.all_tag_fields
    assert 'entity' in schema.all_tag_fields
    assert 'label' in schema.all_tag_fields


def test_all_address_tag_fields(schema):
    assert isinstance(schema.all_address_tag_fields, dict)
    assert 'address' in schema.all_address_tag_fields
    assert 'entity' not in schema.all_address_tag_fields


def test_all_entity_tag_fields(schema):
    assert isinstance(schema.all_entity_tag_fields, dict)
    assert 'entity' in schema.all_entity_tag_fields
    assert 'address' not in schema.all_entity_tag_fields


def test_all_fields(schema):
    assert isinstance(schema.all_fields, dict)
    assert all(field in schema.all_fields
               for field in ['title', 'label', 'address', 'entity'])


def test_field_type(schema):
    assert schema.field_type('title') == 'text'
    assert schema.field_type('lastmod') == 'datetime'
    assert schema.field_type('entity') == 'int'
    assert schema.field_type('is_cluster_definer') == 'boolean'


def test_field_taxonomy(schema):
    assert schema.field_taxonomy('category') == 'entity'


def test_field_no_taxonomy(schema):
    assert schema.field_taxonomy('title') is None


def test_check_type(schema):
    assert schema.check_type('title', 'some test string')
    with(pytest.raises(ValidationError)) as e:
        assert schema.check_type('title', 5)
    assert "Field title must be of type text" in str(e.value)

    assert schema.check_type('lastmod', date.fromisoformat('2021-04-21'))
    with(pytest.raises(ValidationError)) as e:
        assert schema.check_type('lastmod', 5)
    assert "Field lastmod must be of type datetime" in str(e.value)

    assert schema.check_type('entity', 5)
    with(pytest.raises(ValidationError)) as e:
        assert schema.check_type('entity', '56abc')
    assert "Field entity must be of type integer" in str(e.value)

    assert schema.check_type('tags', [{'a': 1}, {'b': 2}])
    with(pytest.raises(ValidationError)) as e:
        assert schema.check_type('tags', '56abc')
    assert "Field tags must be of type list" in str(e.value)


def test_check_taxonomies(schema, taxonomies):
    assert schema.check_taxonomies('category', 'exchange', taxonomies)
    with(pytest.raises(ValidationError)) as e:
        assert schema.check_taxonomies('category', 'test', taxonomies)
    assert "Undefined concept test in field category" in str(e.value)

    schema.schema['generic_tag']['dummy'] = {'taxonomy': 'test'}
    with(pytest.raises(ValidationError)) as e:
        assert schema.check_taxonomies('dummy', 'test', taxonomies)
    assert "Unknown taxonomy test" in str(e.value)
