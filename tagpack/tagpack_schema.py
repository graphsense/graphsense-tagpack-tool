"""TagPack - A wrappers TagPack Schema"""
import datetime
import yaml

import importlib.resources as pkg_resources

from . import conf
from tagpack import ValidationError

TAGPACK_SCHEMA_FILE = 'tagpack_schema.yaml'


class TagPackSchema(object):
    """Defines the structure of a TagPack and supports validation"""

    def __init__(self):
        self.load_schema()
        self.definition = TAGPACK_SCHEMA_FILE

    def load_schema(self):
        schema = pkg_resources.read_text(conf, TAGPACK_SCHEMA_FILE)
        self.schema = yaml.safe_load(schema)

    @property
    def header_fields(self):
        return {k: v for k, v in self.schema['header'].items()}

    @property
    def mandatory_header_fields(self):
        return {k: v for k, v in self.schema['header'].items()
                if v['mandatory']}

    @property
    def generic_tag_fields(self):
        return {k: v for k, v in self.schema['generic_tag'].items()}

    @property
    def address_tag_fields(self):
        explicit_fields = {k: v for k, v in self.schema['address_tag'].items()}
        inherited_fields = self.generic_tag_fields
        return {**explicit_fields, **inherited_fields}

    @property
    def mandatory_address_tag_fields(self):
        return {k: v for k, v in self.address_tag_fields.items()
                if v['mandatory']}

    @property
    def entity_tag_fields(self):
        explicit_fields = {k: v for k, v in self.schema['entity_tag'].items()}
        inherited_fields = self.generic_tag_fields
        return {**explicit_fields, **inherited_fields}

    @property
    def mandatory_entity_tag_fields(self):
        return {k: v for k, v in self.entity_tag_fields.items()
                if v['mandatory']}

    @property
    def all_tag_fields(self):
        addr_tags = {k: v for k, v in self.schema['address_tag'].items()}
        entity_tags = {k: v for k, v in self.schema['entity_tag'].items()}
        generic_tags = {k: v for k, v in self.schema['generic_tag'].items()}
        return {**addr_tags, **entity_tags, **generic_tags}

    @property
    def all_address_tag_fields(self):
        """Returns all address tag header and body fields"""
        return {**self.header_fields, **self.address_tag_fields}

    @property
    def all_entity_tag_fields(self):
        """Returns all address tag header and body fields"""
        return {**self.header_fields, **self.entity_tag_fields}

    @property
    def all_fields(self):
        """Returns all address tag header and body fields"""
        return {**self.header_fields,
                **self.generic_tag_fields,
                **self.entity_tag_fields,
                **self.address_tag_fields}

    def field_type(self, field):
        return self.all_fields[field]['type']

    def field_taxonomy(self, field):
        return self.all_fields[field].get('taxonomy')

    def check_type(self, field, value):
        """Checks whether a field's type matches the definition"""
        schema_type = self.field_type(field)
        if schema_type == 'text':
            if not isinstance(value, str):
                raise ValidationError("Field {} must be of type text"
                                      .format(field))
            if not len(value) >= 1:
                raise ValidationError("Empty value in text field {}"
                                      .format(field))
        elif schema_type == 'datetime':
            if not isinstance(value, datetime.date):
                raise ValidationError("Field {} must be of type datetime"
                                      .format(field))
        elif schema_type == 'int':
            if not isinstance(value, int):
                raise ValidationError("Field {} must be of type integer"
                                      .format(field))
        elif schema_type == 'list':
            if not isinstance(value, list):
                raise ValidationError("Field {} must be of type list"
                                      .format(field))
        else:
            raise ValidationError("Unsupported schema type {}"
                                  .format(schema_type))
        return True

    def check_taxonomies(self, field, value, taxonomies):
        """Checks whether a field uses values from given taxonomies"""
        if taxonomies and self.field_taxonomy(field):
            expected_taxonomy_id = self.field_taxonomy(field)
            expected_taxonomy = taxonomies.get(expected_taxonomy_id)

            if expected_taxonomy is None:
                raise ValidationError("Unknown taxonomy {}"
                                      .format(expected_taxonomy_id))

            if value not in expected_taxonomy.concept_ids:
                raise ValidationError("Undefined concept {} in field {}"
                                      .format(value, field))
        return True
