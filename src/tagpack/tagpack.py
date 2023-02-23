"""TagPack - A wrapper for TagPacks files"""
import glob
import json
import os
import pathlib
import sys
from collections import defaultdict

import coinaddrvalidator
import giturlparse as gup
import yaml
from git import Repo
from yamlinclude import YamlIncludeConstructor

from tagpack import TagPackFileError, UniqueKeyLoader, ValidationError
from tagpack.cmd_utils import get_user_choice, print_info, print_warn


def get_repository(path: str) -> pathlib.Path:
    """Parse '/home/anna/graphsense/graphsense-tagpacks/public/packs' ->
    and return pathlib object with the repository root
    """
    repo_path = pathlib.Path(path)

    while str(repo_path) != repo_path.root:
        try:
            Repo(repo_path)
            return repo_path
        except:
            pass
        repo_path = repo_path.parent
    raise ValidationError(f"No repository root found in path {path}")


def get_uri_for_tagpack(repo_path, tagpack_file, strict_check, no_git):
    """For a given path string
        '/home/anna/graphsense/graphsense-tagpacks/public/packs'

    and tagpack file string
        '/home/anna/graphsense/graphsense-tagpacks/public/packs/a/2021/01/2010101.yaml'

    return remote URI
        'https://github.com/anna/tagpacks/blob/develop/public/packs/a/2021/01/2010101.yaml'

        and relative path
        'a/2021/01/2010101.yaml'

    If no_git is set, return tagpack file string. For the relative path,
    try to split at '/packs/', or as fallback return the absolute path.

    Local git copy will be checked for modifications by default.
    Toggle strict_check param to change this.

    If path does not contain any git information, the original path
    is returned.
    """
    if no_git:
        if "/packs/" in tagpack_file:
            rel_path = tagpack_file.split("/packs/")[1]
        else:
            rel_path = tagpack_file
        return tagpack_file, rel_path

    repo = Repo(repo_path)

    if strict_check and repo.is_dirty():
        msg = f"Local modifications in {repo.common_dir} detected, please "
        msg += "push first."
        print_info(msg)
        sys.exit(0)

    if len(repo.remotes) > 1:
        msg = "Multiple remotes present, cannot decide on backlink."
        raise ValidationError(msg)

    rel_path = str(pathlib.Path(tagpack_file).relative_to(repo_path))

    u = next(repo.remotes[0].urls)
    g = gup.parse(u).url2https.replace(".git", "")
    res = f"{g}/tree/{repo.active_branch.name}/{rel_path}"
    return res, rel_path


def collect_tagpack_files(path):
    """
    Collect Tagpack YAML files from the given path. This function returns a
    dict made of sets. Each key of the dict is the corresponding header path of
    the values included in its set (the one in the closest parent directory).
    The None value is the key for files without header path. By convention, the
    name of a header file should be header.yaml
    """
    tagpack_files = {}

    if os.path.isdir(path):
        files = set(glob.glob(path + "/**/*.yaml", recursive=True))
    elif os.path.isfile(path):  # validate single file
        files = {path}
    else:  # TODO Error! Should we validate the path within __main__?
        print_warn(f"Not a valid path: {path}")
        return {}

    files = {f for f in files if not f.endswith("config.yaml")}

    # Sort files, deepest first
    sfiles = sorted(files, key=lambda x: len(x.split(os.sep)), reverse=True)
    # Select headers
    hfiles = [f for f in sfiles if f.endswith("header.yaml")]
    # Remove header files from the search
    files -= set(hfiles)
    # Map files and headers
    for f in hfiles:
        header = os.path.dirname(f)
        # Select files in the same path than header, subdirs only
        match_files = {
            mfile
            for mfile in files
            if (header in mfile and len(mfile.split(os.sep)) > len(f.split(os.sep)))
        }
        tagpack_files[header] = match_files
        files -= match_files

    # Files without headers
    if files:
        tagpack_files[None] = files

    # Avoid to include header files without files
    for t, fs in tagpack_files.items():
        if not fs:
            msj = f"\tThe header file in {os.path.realpath(t)} won't be "
            msj += "included in any tagpack"
            print_warn(msj)

    tagpack_files = {k: v for k, v in tagpack_files.items() if v}

    return tagpack_files


class TagPack(object):
    """Represents a TagPack"""

    def __init__(self, uri, contents, schema, taxonomies):
        self.uri = uri
        self.contents = contents
        self.schema = schema
        self.taxonomies = taxonomies
        self._unique_tags = []
        self._duplicates = []

    verifiable_currencies = [
        a.ticker for a in coinaddrvalidator.currency.Currencies.instances.values()
    ]

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
            return {
                k: v for k, v in self.contents.items() if k in self.schema.header_fields
            }
        except AttributeError:
            raise TagPackFileError("Cannot extract TagPack fields")

    @property
    def tag_fields(self):
        """Returns tag fields defined in the TagPack header"""
        try:
            return {
                k: v
                for k, v in self.contents.items()
                if k != "tags" and k in self.schema.tag_fields
            }
        except AttributeError:
            raise TagPackFileError("Cannot extract TagPack fields")

    @property
    def tags(self):
        """Returns all tags defined in a TagPack's body"""
        try:
            return [Tag.from_contents(tag, self) for tag in self.contents["tags"]]
        except AttributeError:
            raise TagPackFileError("Cannot extract tags from tagpack")

    def get_unique_tags(self):
        if self._unique_tags:
            return self._unique_tags

        seen = set()
        duplicates = []

        for tag in self.tags:
            # check if duplicate entry
            t = tuple(
                [
                    str(tag.all_fields.get(k)).lower()
                    if k in tag.all_fields.keys()
                    else ""
                    for k in ["address", "currency", "label", "source"]
                ]
            )
            if t in seen:
                duplicates.append(t)
            else:
                seen.add(t)
                self._unique_tags.append(tag)

        self._duplicates = duplicates
        return self._unique_tags

    def validate(self):
        """Validates a TagPack against its schema and used taxonomies"""

        # check if mandatory header fields are used by a TagPack
        for schema_field in self.schema.mandatory_header_fields:
            if schema_field not in self.header_fields:
                raise ValidationError(
                    "Mandatory header field {} missing".format(schema_field)
                )

        # check header fields' types, taxonomy and mandatory use
        for field, value in self.all_header_fields.items():
            # check a field is defined
            if field not in self.schema.all_fields:
                raise ValidationError("Field {} not allowed in header".format(field))
            # check for None values
            if value is None:
                raise ValidationError(
                    "Value of header field {} must not be empty (None)".format(field)
                )

            self.schema.check_type(field, value)
            self.schema.check_taxonomies(field, value, self.taxonomies)

        if len(self.tags) < 1:
            raise ValidationError("no tags found.")

        # iterate over all tags, check types, taxonomy and mandatory use
        e2 = "Mandatory tag field {} missing in {}"
        e3 = "Field {} not allowed in {}"
        e4 = "Value of body field {} must not be empty (None) in {}"
        for tag in self.get_unique_tags():
            # check if mandatory tag fields are defined
            if not isinstance(tag, Tag):
                raise ValidationError("Unknown tag type {}".format(tag))

            for schema_field in self.schema.mandatory_tag_fields:
                if (
                    schema_field not in tag.explicit_fields
                    and schema_field not in self.tag_fields
                ):
                    raise ValidationError(e2.format(schema_field, tag))

            for field, value in tag.explicit_fields.items():
                # check whether field is defined as body field
                if field not in self.schema.tag_fields:
                    raise ValidationError(e3.format(field, tag))

                # check for None values
                if value is None:
                    raise ValidationError(e4.format(field, tag))

                # check types and taxomomy use
                try:
                    self.schema.check_type(field, value)
                    self.schema.check_taxonomies(field, value, self.taxonomies)
                except ValidationError as e:
                    raise ValidationError(f"{e} in {tag}")

        if self._duplicates:
            msg = f"{len(self._duplicates)} duplicate(s) found, starting "
            msg += f"with {self._duplicates[0]}\n"
            print_info(msg)
        return True

    def verify_addresses(self):
        """
        Verify valid blockchain addresses using coinaddrvalidator library. In
        general, this is done by decoding the address (e.g. to base58) and
        calculating a checksum using the first bytes of the decoded value,
        which should match with the last bytes of the decoded value.
        """

        unsupported = defaultdict(set)
        msg = "\tPossible invalid {} address: {}"
        for tag in self.get_unique_tags():
            currency = tag.all_fields.get("currency", "").lower()
            cupper = currency.upper()
            address = tag.all_fields.get("address")
            if len(address) != len(address.strip()):
                print_warn(f"\tAddress contains whitespace: {repr(address)}")
            elif currency in self.verifiable_currencies:
                v = coinaddrvalidator.validate(currency, address)
                if not v.valid:
                    print_warn(msg.format(cupper, address))
            else:
                unsupported[cupper].add(address)

        for c, addrs in unsupported.items():
            print_warn(f"\tAddress verification is not supported for {c}:")
            for a in sorted(addrs):
                print_warn(f"\t\t{a}")

    def add_actors(self, get_actors, max_suggestions):
        """Suggest actors for labels that have no actors assigned"""
        suggestions_found = False

        if "label" in self.all_header_fields and "actor" not in self.all_header_fields:
            hl = self.all_header_fields.get("label")
            candidates = get_actors(hl, max_suggestions)
            actor = get_user_choice(hl, candidates)
            if actor:
                self.contents["actor"] = actor
                suggestions_found = True

        # update tags and trace if all labels carry the same actor
        actors = set()
        all_tags_carry_actor = True
        for tag in self.get_unique_tags():
            if "label" in tag.explicit_fields and "actor" not in tag.explicit_fields:
                tl = tag.explicit_fields.get("label")
                candidates = get_actors(tl, max_suggestions)
                actor = get_user_choice(tl, candidates)
                if actor:
                    tag.contents["actor"] = actor
                    actors.add(actor)
                    suggestions_found = True
                else:
                    all_tags_carry_actor = False

        if all_tags_carry_actor and len(actors) == 1:
            # promote actor to header field
            self.contents["actor"] = actors.pop()
            for tag in self.get_unique_tags():
                tag.contents.pop("actor")

        return suggestions_found

    def to_json(self):
        """Returns a JSON representation of a TagPack's header"""
        tagpack = {}
        tagpack["uri"] = self.uri
        for k, v in self.header_fields.items():
            if k != "tags":
                tagpack[k] = v
        return json.dumps(tagpack, indent=4, sort_keys=True, default=str)

    def __str__(self):
        """Returns a string serialization of the entire TagPack"""
        return str(self.contents)


class Tag(object):
    """An attribution tag"""

    def __init__(self, contents, tagpack):
        self.contents = contents
        self.tagpack = tagpack

    @staticmethod
    def from_contents(contents, tagpack):
        return Tag(contents, tagpack)

    @property
    def explicit_fields(self):
        """Return only explicitly defined tag fields"""
        return {k: v for k, v in self.contents.items()}

    @property
    def all_fields(self):
        """Return all tag fields (explicit and generic)"""
        return {
            **self.tagpack.tag_fields,
            **self.explicit_fields,
        }

    def to_json(self):
        """Returns a JSON serialization of all tag fields"""
        tag = self.all_fields
        tag["tagpack_uri"] = self.tagpack.uri
        return json.dumps(tag, indent=4, sort_keys=True, default=str)

    def __str__(self):
        """ "Returns a string serialization of a Tag"""
        return str(self.all_fields)
