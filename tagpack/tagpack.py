"""TagPack - A wrapper for TagPacks files"""
import glob
import json
import os
import sys
import yaml
from git import Repo
import giturlparse as gup
import pathlib
import coinaddrvalidator
from collections import defaultdict
from tagpack import TagPackFileError, ValidationError
from yamlinclude import YamlIncludeConstructor

from tagpack.cmd_utils import print_info, print_warn


def get_repository(path: str) -> pathlib.Path:
    """ Parse '/home/anna/graphsense/graphsense-tagpacks/public/packs' ->
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
    raise ValidationError(f'No repository root found in path {path}')


def get_uri_for_tagpack(repo_path, tagpack_file, strict_check, no_git):
    """ For a given path string
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
        if '/packs/' in tagpack_file:
            rel_path = tagpack_file.split('/packs/')[1]
        else:
            rel_path = tagpack_file
        return tagpack_file, rel_path

    repo = Repo(repo_path)

    if strict_check and repo.is_dirty():
        print_info(f"Local modifications in {repo.common_dir} detected, please push first.")
        sys.exit(0)

    if len(repo.remotes) > 1:
        raise ValidationError("Multiple remotes present, cannot decide on backlink. ")

    rel_path = str(pathlib.Path(tagpack_file).relative_to(repo_path))

    u = next(repo.remotes[0].urls)
    g = gup.parse(u).url2https.replace('.git', '')
    res = f'{g}/tree/{repo.active_branch.name}/{rel_path}'
    return res, rel_path


def collect_tagpack_files(path):
    """Collect Tagpack YAML files from given paths"""
    tagpack_files = []
    header_path = None

    if os.path.isdir(path):
        files = glob.glob(path + '/**/*.yaml', recursive=True)
        tagpack_files = tagpack_files + files
    elif os.path.isfile(path):  # validate single file
        tagpack_files.append(path)

    # check if corresponding yaml header file exists in a parent directory
    header_dir = path
    while header_dir and header_dir != os.path.sep:
        header_dir, _ = os.path.split(header_dir)
        res = glob.glob(os.path.join(header_dir, 'header.yaml'))
        if res:
            tagpack_files += res
            break

    # deal with yaml includes
    tagpack_files = set(tagpack_files)
    for p in tagpack_files:
        if p.endswith('header.yaml'):
            header_path = p
    if header_path:
        tagpack_files.remove(header_path)
        header_path = os.path.dirname(header_path)

    tagpack_files = [a for a in tagpack_files if not a.endswith('config.yaml')]

    return tagpack_files, header_path


# https://gist.github.com/pypt/94d747fe5180851196eb
class UniqueKeyLoader(yaml.FullLoader):
    def construct_mapping(self, node, deep=False):
        mapping = set()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValidationError(f"Duplicate {key!r} key found in YAML.")
            mapping.add(key)
        return super().construct_mapping(node, deep)


class TagPack(object):
    """Represents a TagPack"""

    def __init__(self, uri, contents, schema, taxonomies):
        self.uri = uri
        self.contents = contents
        self.schema = schema
        self.taxonomies = taxonomies
        self._unique_tags = []
        self._duplicates = []

    verifiable_currencies = [a.ticker \
            for a in coinaddrvalidator.currency.Currencies.instances.values()]

    def load_from_file(uri, pathname, schema, taxonomies, header_dir=None):
        YamlIncludeConstructor.add_to_loader_class(loader_class=yaml.FullLoader, base_dir=header_dir)

        if not os.path.isfile(pathname):
            sys.exit("This program requires {} to be a file"
                     .format(pathname))
        contents = yaml.load(open(pathname, 'r'), UniqueKeyLoader)

        if 'header' in contents.keys():
            for k, v in contents['header'].items():
                contents[k] = v
            contents.pop('header')
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
    def tag_fields(self):
        """Returns tag fields defined in the TagPack header"""
        try:
            return {k: v for k, v in self.contents.items()
                    if k != 'tags' and k in self.schema.tag_fields}
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

    def get_unique_tags(self):
        if self._unique_tags:
            return self._unique_tags

        seen = set()
        duplicates = []

        for tag in self.tags:
            # check if duplicate entry
            t = tuple([str(tag.all_fields.get(k)).lower() if k in tag.all_fields.keys() else ''
                       for k in ['address', 'currency', 'label', 'source']])
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

        if len(self.tags) < 1:
            raise ValidationError("no tags found.")

        # iterate over all tags, check types, taxonomy and mandatory use
        for tag in self.get_unique_tags():
            # check if mandatory tag fields are defined
            if not isinstance(tag, Tag):
                raise ValidationError("Unknown tag type {}".format(tag))

            for schema_field in self.schema.mandatory_tag_fields:
                if schema_field not in tag.explicit_fields and \
                   schema_field not in self.tag_fields:
                    raise ValidationError(f"Mandatory tag field {schema_field} missing in {tag} ")

            for field, value in tag.explicit_fields.items():
                # check whether field is defined as body field
                if field not in self.schema.tag_fields:
                    raise ValidationError(f"Field {field} not allowed in {tag} ")

                # check for None values
                if value is None:
                    raise ValidationError(
                        f"Value of body field {field} must not be empty (None) in {tag}")

                # check types and taxomomy use
                try:
                    self.schema.check_type(field, value)
                    self.schema.check_taxonomies(field, value, self.taxonomies)
                except ValidationError as e:
                    raise ValidationError(f'{e} in {tag}')

        if self._duplicates:
            print_info(f"{len(self._duplicates)} duplicate(s) found, starting with {self._duplicates[0]}\n")
        return True


    def verify_addresses(self):
        """
        Verify valid blockchain addresses using coinaddrvalidator library. In
        general, this is done by decoding the address (e.g. to base58) and
        calculating a checksum using the first bytes of the decoded value,
        which should match with the last bytes of the decoded value.
        """

        unsupported = defaultdict(set)

        for tag in self.get_unique_tags():

            currency = tag.all_fields.get('currency', '').lower()
            cupper = currency.upper()
            address = tag.all_fields.get('address')
            if len(address) != len(address.strip()):
                print_warn(f"\tAddress contains whitespace: {repr(address)}")
            elif currency in self.verifiable_currencies:
                v = coinaddrvalidator.validate(currency, address)
                if not v.valid:
                    print_warn(f"\tPossible invalid {cupper} address: {address}")
            else:
                unsupported[cupper].add(address)

        for c, addrs in unsupported.items():
            print_warn(f"\tAddress verification is not supported for {c}:")
            for a in sorted(addrs):
                print_warn(f"\t\t{a}")


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
        return {**self.tagpack.tag_fields, **self.explicit_fields, }

    def to_json(self):
        """Returns a JSON serialization of all tag fields"""
        tag = self.all_fields
        tag['tagpack_uri'] = self.tagpack.uri
        return json.dumps(tag, indent=4, sort_keys=True, default=str)

    def __str__(self):
        """"Returns a string serialization of a Tag"""
        return str(self.all_fields)
