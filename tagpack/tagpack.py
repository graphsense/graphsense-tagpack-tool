"""TagPack - A wrapper for TagPacks files"""
import json
import os
import sys
import yaml

from tagpack import TagPackFileError, ValidationError


class TagPack(object):
    """Represents a TagPack"""

    def __init__(self, uri, contents, schema, taxonomies):
        self.uri = uri
        self.contents = contents
        self.schema = schema
        self.taxonomies = taxonomies

    def load_from_file(baseuri, pathname, schema, taxonomies):
        if not os.path.isfile(pathname):
            sys.exit("This program requires {} to be a file"
                     .format(pathname))
        contents = yaml.safe_load(open(pathname, 'r'))
        if not baseuri.endswith(os.path.sep):
            baseuri = baseuri + os.path.sep
        uri = baseuri + pathname
        return TagPack(uri, contents, schema, taxonomies)

    @property
    def all_header_fields(self):
        """Returns all TagPack header fields, including generic tag fields"""
        try:
            return {k: v for k, v in self.contents.items()}
        except AttributeError:
            raise TagPackFileError("Cannot extract TagPack fields")

    @property
    def header_fields(self):
        """Returns only TagPack header fields that are defined as such"""
        try:
            return {k: v for k, v in self.contents.items()
                    if k in self.schema.header_fields}
        except AttributeError:
            raise TagPackFileError("Cannot extract TagPack fields")

    @property
    def generic_tag_fields(self):
        """Returns generic tag fields defined in the TagPack header"""
        try:
            return {k: v for k, v in self.contents.items()
                    if k != 'tags' and k in self.schema.all_tag_fields}
        except AttributeError:
            raise TagPackFileError("Cannot extract TagPack fields")

    @property
    def tags(self):
        """Returns all tags defined in a TagPack's body"""
        try:
            return [Tag.from_contents(tag, self)
                    for tag in self.contents['tags']]
        except AttributeError:
            raise TagPackFileError("Cannot extract tags from tagpack")

    def validate(self):
        """Validates a TagPack against its schema and used taxonomies"""

        # check if mandatory header fields are used by a TagPack
        for schema_field in self.schema.mandatory_header_fields:
            if schema_field not in self.header_fields:
                raise ValidationError("Mandatory header field {} missing"
                                      .format(schema_field))

        # check header fields' types, taxonomy and mandatory use
        for field, value in self.all_header_fields.items():
            # check a field is defined
            if field not in self.schema.all_fields:
                raise ValidationError("Field {} not allowed in header"
                                      .format(field))
            # check for None values
            if value is None:
                raise ValidationError(
                    "Value of header field {} must not be empty (None)"
                    .format(field))

            self.schema.check_type(field, value)
            self.schema.check_taxonomies(field, value, self.taxonomies)

        # iterate over all tags and check types, taxonomy and mandatory use
        for tag in self.tags:

            # check if mandatory tag fields are defined
            if isinstance(tag, AddressTag):
                mandatory_tag_fields = self.schema.mandatory_address_tag_fields
                tag_fields = self.schema.address_tag_fields
            elif isinstance(tag, EntityTag):
                mandatory_tag_fields = self.schema.mandatory_entity_tag_fields
                tag_fields = self.schema.entity_tag_fields
            else:
                raise ValidationError("Unknown tag type {}".format(tag))

            for schema_field in mandatory_tag_fields:
                if schema_field not in tag.explicit_fields and \
                   schema_field not in self.generic_tag_fields:
                    raise ValidationError("Mandatory tag field {} missing"
                                          .format(schema_field))

            for field, value in tag.explicit_fields.items():
                # check whether field is defined as body field
                if field not in tag_fields:
                    raise ValidationError("Field {} not allowed in tag"
                                          .format(field))

                # check for None values
                if value is None:
                    raise ValidationError(
                        "Value of body field {} must not be empty (None)"
                        .format(field))

                # check types and taxomomy use
                self.schema.check_type(field, value)
                self.schema.check_taxonomies(field, value, self.taxonomies)

            return True

    def to_json(self):
        """Returns a JSON representation of a TagPack's header"""
        tagpack = {}
        tagpack['uri'] = self.uri
        for k, v in self.header_fields.items():
            if k != 'tags':
                tagpack[k] = v
        return json.dumps(tagpack, indent=4, sort_keys=True, default=str)

    def __str__(self):
        """Returns a string serialization of the entire TagPack"""
        return str(self.contents)


class Tag(object):
    """A generic attribution tag"""

    def __init__(self, contents, tagpack):
        self.contents = contents
        self.tagpack = tagpack

    @staticmethod
    def from_contents(contents, tagpack):
        if 'address' in contents:
            return AddressTag(contents, tagpack)
        elif 'entity' in contents:
            return EntityTag(contents, tagpack)
        else:
            raise TagPackFileError('Tag must be assigned to address or entity')

    @property
    def explicit_fields(self):
        """Return only explicitly defined tag fields"""
        return {k: v for k, v in self.contents.items()}

    @property
    def all_fields(self):
        """Return all tag fields (explicit and generic)"""
        return {**self.explicit_fields, **self.tagpack.generic_tag_fields}

    def to_json(self):
        """Returns a JSON serialization of all tag fields"""
        tag = self.all_fields
        tag['tagpack_uri'] = self.tagpack.uri
        return json.dumps(tag, indent=4, sort_keys=True, default=str)

    def __str__(self):
        """"Returns a string serialization of a Tag"""
        return str(self.all_fields)


class AddressTag(Tag):
    """A tag attributing contextual information to an address"""

    def __init__(self, contents, tagpack):
        super().__init__(contents, tagpack)


class EntityTag(Tag):
    """A tag attributing contextual information to an entity"""

    def __init__(self, contents, tagpack):
        super().__init__(contents, tagpack)
