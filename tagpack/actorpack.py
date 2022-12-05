"""ActorPack - A wrapper for ActorPack files"""
import os
import sys
import yaml
import json
from yamlinclude import YamlIncludeConstructor
from tagpack.cmd_utils import print_info
from tagpack import TagPackFileError, ValidationError, UniqueKeyLoader


class ActorPack(object):
    """Represents an ActorPack"""

    def __init__(self, uri, contents, schema, taxonomies):
        self.uri = uri
        self.contents = contents
        self.schema = schema
        self.taxonomies = taxonomies
        self._unique_actors = []
        self._duplicates = []

    def load_from_file(uri, pathname, schema, taxonomies, header_dir=None):
        YamlIncludeConstructor.add_to_loader_class(
            loader_class=yaml.FullLoader, base_dir=header_dir
        )

        if not os.path.isfile(pathname):
            sys.exit("This program requires {} to be a file".format(pathname))
        contents = yaml.load(open(pathname, "r"), UniqueKeyLoader)

        if "header" in contents.keys():
            for k, v in contents["header"].items():
                contents[k] = v
            contents.pop("header")
        return ActorPack(uri, contents, schema, taxonomies)

    @property
    def all_header_fields(self):
        """Returns all ActorPack header fields, including generic actor fields"""
        try:
            return {k: v for k, v in self.contents.items()}
        except AttributeError:
            raise TagPackFileError("Cannot extract ActorPack fields")

    @property
    def header_fields(self):
        """Returns only ActorPack header fields that are defined as such"""
        try:
            return {
                k: v for k, v in self.contents.items() if k in self.schema.header_fields
            }
        except AttributeError:
            raise TagPackFileError("Cannot extract ActorPack fields")

    @property
    def actor_fields(self):
        """Returns actor fields defined in the ActorPack header"""
        try:
            return {
                k: v
                for k, v in self.contents.items()
                if k != "actors" and k in self.schema.actor_fields
            }
        except AttributeError:
            raise TagPackFileError("Cannot extract ActorPack fields")

    @property
    def actors(self):
        """Returns all actors defined in a ActorPack's body"""
        try:
            return [
                Actor.from_contents(actor, self)
                for actor in self.contents["actors"]
            ]
        except AttributeError:
            raise TagPackFileError("Cannot extract actors from ActorPack")

    def get_unique_actors(self):
        if self._unique_actors:
            return self._unique_actors

        seen = set()
        duplicates = []

        for actor in self.actors:
            # check if duplicate entry
            t = tuple(
                str(actor.all_fields.get(k)).lower() for k in ["id", "label"]
            )
            if t in seen:
                duplicates.append(t)
            else:
                seen.add(t)
                self._unique_actors.append(actor)

        self._duplicates = duplicates
        return self._unique_actors

    def validate(self):
        """Validates an ActorPack against its schema and used taxonomies"""

        # check if mandatory header fields are used by an ActorPack
        for schema_field in self.schema.mandatory_header_fields:
            if schema_field not in self.header_fields:
                msg = f"Mandatory header field {schema_field} missing"
                raise ValidationError(msg)

        # check header fields' types, taxonomy and mandatory use
        for field, value in self.all_header_fields.items():
            # check a field is defined
            if field not in self.schema.all_fields:
                raise ValidationError(f"Field {field} not allowed in header")
            # check for None values
            if value is None:
                msg = f"Value of header field {field} must not be empty (None)"
                raise ValidationError(msg)

            self.schema.check_type(field, value)
            self.schema.check_taxonomies(field, value, self.taxonomies)

        if len(self.actors) < 1:
            raise ValidationError("No actors found.")

        # iterate over all tags, check types, taxonomy and mandatory use
        e2 = "Mandatory tag field {} missing in {}"
        e3 = "Field {} not allowed in {}"
        e4 = "Value of body field {} must not be empty (None) in {}"
        for actor in self.get_unique_actors():
            # check if mandatory actor fields are defined
            if not isinstance(actor, Actor):
                raise ValidationError(f"Unknown actor type {type(actor)}")

            for schema_field in self.schema.mandatory_actor_fields:
                if schema_field not in actor.explicit_fields \
                    and schema_field not in self.actor_fields:
                    raise ValidationError(e2.format(schema_field, actor))

            for field, value in actor.explicit_fields.items():
                # check whether field is defined as body field
                if field not in self.schema.actor_fields:
                    raise ValidationError(e3.format(field, actor))

                # check for None values
                if value is None:
                    raise ValidationError(e4.format(field, actor))

                # check types and taxomomy use
                try:
                    self.schema.check_type(field, value)
                    self.schema.check_taxonomies(field, value, self.taxonomies)
                except ValidationError as e:
                    raise ValidationError(f"{e} in {actor}")

        if self._duplicates:
            msg = f"{len(self._duplicates)} duplicate(s) found, starting "\
                  f"with {self._duplicates[0]}\n"
            print_info(msg)
        return True

    def to_json(self):
        """Returns a JSON representation of an ActorPack's header"""
        actorpack = {}
        for k, v in self.header_fields.items():
            if k != "actors":
                actorpack[k] = v
        return json.dumps(actorpack, indent=4, sort_keys=True, default=str)

    def __str__(self):
        """Returns a string serialization of the entire ActorPack"""
        return str(self.contents)


class Actor(object):
    """An actor"""

    def __init__(self, contents, actorpack):
        self.contents = contents
        self.actorpack = actorpack

    @staticmethod
    def from_contents(contents, actorpack):
        return Actor(contents, actorpack)

    @property
    def explicit_fields(self):
        """Return only explicitly defined actor fields"""
        return {k: v for k, v in self.contents.items()}

    @property
    def all_fields(self):
        """Return all actor fields (explicit and generic)"""
        return {
            **self.actorpack.actor_fields,
            **self.explicit_fields,
        }

    def to_json(self):
        """Returns a JSON serialization of all actor fields"""
        actor = self.all_fields
        return json.dumps(actor, indent=4, sort_keys=True, default=str)

    def __str__(self):
        """ "Returns a string serialization of an Actor"""
        return str(self.all_fields)
