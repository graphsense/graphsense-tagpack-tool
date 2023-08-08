"""TagPack - A wrappers TagPack Schema"""
import importlib.resources as pkg_resources

import pandas as pd
import yaml

from tagpack import ValidationError
from tagpack.schema import check_type

from . import conf, db

TAGPACK_SCHEMA_FILE = "tagpack_schema.yaml"
CONFIDENCE_FILE = "confidence.csv"


class TagPackSchema(object):
    """Defines the structure of a TagPack and supports validation"""

    def __init__(self):
        schema = pkg_resources.read_text(conf, TAGPACK_SCHEMA_FILE)
        self.schema = yaml.safe_load(schema)
        confidence = pkg_resources.open_text(db, CONFIDENCE_FILE)
        self.confidences = pd.read_csv(confidence, index_col="id")
        self.definition = TAGPACK_SCHEMA_FILE

    @property
    def header_fields(self):
        return {k: v for k, v in self.schema["header"].items()}  # noqa: C416

    @property
    def mandatory_header_fields(self):
        return {k: v for k, v in self.schema["header"].items() if v["mandatory"]}

    @property
    def tag_fields(self):
        return {k: v for k, v in self.schema["tag"].items()}  # noqa: C416

    @property
    def mandatory_tag_fields(self):
        return {k: v for k, v in self.tag_fields.items() if v["mandatory"]}

    @property
    def all_fields(self):
        """Returns all header and body fields"""
        return {**self.header_fields, **self.tag_fields}

    def field_type(self, field):
        return self.all_fields[field]["type"]

    def field_definition(self, field):
        return self.all_fields.get(field, None)

    def field_taxonomy(self, field):
        return self.all_fields[field].get("taxonomy")

    def check_type(self, field, value):
        """Checks whether a field's type matches the definition"""
        # schema_type = self.field_type(field)
        field_def = self.field_definition(field)
        if field_def is None:
            raise ValidationError(f"Field {field} not defined in schema.")
        return check_type(self.schema, field, field_def, value)

    def check_taxonomies(self, field, value, taxonomies):
        """Checks whether a field uses values from given taxonomies"""
        if not self.field_taxonomy(field):
            # No taxonomy was requested
            return True
        elif not taxonomies:
            raise ValidationError("No taxonomies loaded")

        expected_taxonomy_ids = self.field_taxonomy(field)
        if type(expected_taxonomy_ids) == str:
            expected_taxonomy_ids = [expected_taxonomy_ids]

        expected_taxonomies = [taxonomies.get(i) for i in expected_taxonomy_ids]
        if None in expected_taxonomies:
            raise ValidationError(f"Unknown taxonomy {expected_taxonomy_ids}")

        for v in value if isinstance(value, list) else [value]:
            in_one_tax = False
            for t in expected_taxonomies:
                if v in t.concept_ids:
                    in_one_tax = True
                    break
            if not in_one_tax:
                msg = f"Undefined concept {v} for {field} field"
                raise ValidationError(msg)

        return True
