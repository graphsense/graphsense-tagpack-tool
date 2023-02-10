"""ActorPack - A wrappers ActorPack Schema"""
import datetime
import importlib.resources as pkg_resources
import json
from json import JSONDecodeError

import pandas as pd
import yaml

from tagpack import ValidationError

from . import conf, db

ACTORPACK_SCHEMA_FILE = "actorpack_schema.yaml"
COUNTRIES_FILE = "countries.csv"


class ActorPackSchema(object):
    """Defines the structure of an ActorPack and supports validation"""

    def __init__(self):
        schema = pkg_resources.read_text(conf, ACTORPACK_SCHEMA_FILE)
        self.schema = yaml.safe_load(schema)
        countries = pkg_resources.open_text(db, COUNTRIES_FILE)
        self.countries = pd.read_csv(countries, index_col="id")
        self.definition = ACTORPACK_SCHEMA_FILE

    @property
    def header_fields(self):
        return {k: v for k, v in self.schema["header"].items()}

    @property
    def mandatory_header_fields(self):
        return {k: v for k, v in self.schema["header"].items() if v["mandatory"]}

    @property
    def actor_fields(self):
        return {k: v for k, v in self.schema["actor"].items()}

    @property
    def mandatory_actor_fields(self):
        return {k: v for k, v in self.actor_fields.items() if v["mandatory"]}

    @property
    def all_fields(self):
        """Returns all header and body fields"""
        return {**self.header_fields, **self.actor_fields}

    def field_type(self, field):
        return self.all_fields[field]["type"]

    def field_taxonomy(self, field):
        try:
            return self.all_fields[field].get("taxonomy")
        except KeyError:
            return None

    def check_type(self, field, value):
        """Checks whether a field's type matches the definition"""
        schema_type = self.field_type(field)
        if schema_type == "text":
            if not isinstance(value, str):
                raise ValidationError("Field {} must be of type text".format(field))
            if len(value.strip()) == 0:
                raise ValidationError("Empty value in text field {}".format(field))
            if field == "context":
                try:
                    json.loads(value)
                except JSONDecodeError as e:
                    raise ValidationError(
                        f"Invalid JSON in field context with value {value}: {e}"
                    )
        elif schema_type == "datetime":
            if not isinstance(value, datetime.date):
                raise ValidationError(f"Field {field} must be of type datetime")
        elif schema_type == "boolean":
            if not isinstance(value, bool):
                raise ValidationError(f"Field {field} must be of type boolean")
        elif schema_type == "list":
            if not isinstance(value, list):
                raise ValidationError(f"Field {field} must be of type list")
        else:
            raise ValidationError("Unsupported schema type {}".format(schema_type))
        return True

    def check_taxonomies(self, field, value, taxonomies):
        """Checks whether a field uses values from given taxonomies"""
        if not self.field_taxonomy(field):
            # No taxonomy was requested
            return True
        elif not taxonomies:
            raise ValidationError("No taxonomies loaded")

        expected_taxonomy_id = self.field_taxonomy(field)
        expected_taxonomy = taxonomies.get(expected_taxonomy_id)

        if expected_taxonomy is None:
            raise ValidationError(f"Unknown taxonomy {expected_taxonomy_id}")

        for v in value if isinstance(value, list) else [value]:
            if v not in expected_taxonomy.concept_ids:
                msg = f"Undefined concept {v} for {field} field"
                raise ValidationError(msg)

        return True
