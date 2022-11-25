import json
import os
import sys
import time
from argparse import ArgumentParser
from multiprocessing import Pool, cpu_count

import pandas as pd
import yaml

# colorama fixes issues with redirecting colored outputs to files
from colorama import init
from tabulate import tabulate

from tagpack import __version__ as version
from tagpack.cmd_utils import (
    print_fail,
    print_info,
    print_line,
    print_success,
    print_warn,
)
from tagpack.graphsense import GraphSense
from tagpack.tagpack import (
    TagPack,
    TagPackFileError,
    collect_tagpack_files,
    get_repository,
    get_uri_for_tagpack,
)
from tagpack.tagpack_schema import TagPackSchema, ValidationError
from tagpack.tagstore import TagStore
from tagpack.taxonomy import Taxonomy

init()

CONFIG_FILE = "config.yaml"

TAXONOMY_URL = "https://graphsense.github.io"

DEFAULT_CONFIG = {
    "taxonomies": {
        "entity": f"{TAXONOMY_URL}/DW-VA-Taxonomy/assets/data/entities.csv",
        "abuse": f"{TAXONOMY_URL}/DW-VA-Taxonomy/assets/data/abuses.csv",
        "confidence": "src/tagpack/db/confidence.csv",
    }
}


_DEFAULT_SCHEMA = "tagstore"


def _load_taxonomies(config):
    if "taxonomies" not in config:
        return None
    taxonomies = {}
    for key in config["taxonomies"]:
        remote = not (key == "confidence")
        taxonomy = _load_taxonomy(config, key, remote=remote)
        taxonomies[key] = taxonomy
    return taxonomies


def _load_taxonomy(config, key, remote=False):
    if "taxonomies" not in config:
        return None
    uri = config["taxonomies"][key]
    taxonomy = Taxonomy(key, uri)
    if remote:
        taxonomy.load_from_remote()
    else:
        taxonomy.load_from_local()
    return taxonomy


def list_taxonomies(args=None):
    config = _load_config(args.config)

    print_line("Show configured taxonomies")
    print_line(f"Configuration: {args.config}", "info")
    count = 0
    if "taxonomies" not in config:
        print_line("No configured taxonomies", "fail")
    else:
        for key, value in config["taxonomies"].items():
            print_line(value)
            count += 1
        print_line(f"{count} configured taxonomies", "success")


def show_taxonomy_concepts(args, remote=False):
    config = _load_config(args.config)

    if "taxonomies" not in config:
        print_line("No taxonomies configured", "fail")
        return

    print_line("Showing concepts of taxonomy {}".format(args.taxonomy))
    remote = not (args.taxonomy == "confidence")
    uri = config["taxonomies"][args.taxonomy]
    print(f"{'Remote' if remote else 'Local'} URI: {uri}\n")
    taxonomy = _load_taxonomy(config, args.taxonomy, remote=remote)
    if args.verbose:
        headers = ["Id", "Label", "Level", "Uri", "Description"]
        table = [
            [c.id, c.label, c.level, c.uri, c.description] for c in taxonomy.concepts
        ]
    elif args.taxonomy == "confidence":
        headers = ["Level", "Label"]
        table = [[c.level, c.label] for c in taxonomy.concepts]
    else:
        headers = ["Id", "Label"]
        table = [[c.id, c.label] for c in taxonomy.concepts]

    print(tabulate(table, headers=headers))
    print_line(f"{len(taxonomy.concepts)} taxonomy concepts", "success")


def insert_taxonomy(args, remote=False):
    config = _load_config(args.config)

    if "taxonomies" not in config:
        print_line("No taxonomies configured", "fail")
        return

    tax_keys = [args.taxonomy]

    if not args.taxonomy:  # insert all available taxonomies
        tax_keys = config["taxonomies"].keys()

    t0 = time.time()
    print_line("Taxonomy insert starts")

    tagstore = TagStore(args.url, args.schema)

    for t in tax_keys:
        print(f"Taxonomy: {t}")
        try:
            # TODO this should change when having local taxonomies
            remote = not (t == "confidence")
            taxonomy = _load_taxonomy(config, t, remote=remote)
            tagstore.insert_taxonomy(taxonomy)

            print(f"{taxonomy.key} | {taxonomy.uri}:", end=" ")
            print_success("INSERTED")

            duration = round(time.time() - t0, 2)
            print_line(
                f"Inserted {len(taxonomy.concepts)} concepts in {duration}s", "success"
            )
        except Exception as e:
            print_fail(e)
            print_line("Aborted insert", "fail")


def show_quality_measures(args):
    print_line("Show quality measures")
    tagstore = TagStore(args.url, args.schema)

    try:
        qm = tagstore.get_quality_measures(args.currency)
        c = args.currency if args.currency else "Global "
        print(f"{c} quality measures:")
        if qm:
            print(f"\tCOUNT:  {qm['count']}")
            print(f"\tAVG:    {qm['avg']}")
            print(f"\tSTDDEV: {qm['stddev']}")
        else:
            print("\tNone")

    except Exception as e:
        print_fail(e)
        print_line("Operation failed", "fail")


def calc_quality_measures(args):
    t0 = time.time()
    print_line("Calculate quality measures starts")

    tagstore = TagStore(args.url, args.schema)

    try:
        qm = tagstore.calculate_quality_measures()
        print("Global quality measures:")
        if qm is not None:
            print(f"\tCOUNT:  {qm['count']}")
            print(f"\tAVG:    {qm['avg']}")
            print(f"\tSTDDEV: {qm['stddev']}")
        else:
            print("\tNone")

        duration = round(time.time() - t0, 2)
        print_line(f"Done in {duration}s", "success")
    except Exception as e:
        print_fail(e)
        print_line("Operation failed", "fail")


def _load_config(cfile):
    if not os.path.isfile(cfile):
        print_line("Could not find TagPack repository configuration file.", "fail")
        print_info(f"Creating a new default configuration file: {cfile}")
        with open("config.yaml", "a") as the_file:
            yaml.dump(DEFAULT_CONFIG, the_file, allow_unicode=True)
    return yaml.safe_load(open(cfile, "r"))


def show_config(args):
    if not os.path.exists(args.config):
        _load_config(args.config)
    print("Config File:", args.config)
    if args.verbose:
        list_taxonomies(args)


def validate_tagpack(args):
    config = _load_config(args.config)

    t0 = time.time()
    print_line("TagPack validation starts")
    print(f"Path: {args.path}")

    taxonomies = _load_taxonomies(config)
    taxonomy_keys = taxonomies.keys()
    print(f"Loaded taxonomies: {taxonomy_keys}")

    schema = TagPackSchema()
    print(f"Loaded schema: {schema.definition}")

    tagpack_files = collect_tagpack_files(args.path)
    n_tagpacks = len([f for fs in tagpack_files.values() for f in fs])
    print_info(f"Collected {n_tagpacks} TagPack files\n")

    no_passed = 0
    try:
        for headerfile_dir, files in tagpack_files.items():
            for tagpack_file in files:
                tagpack = TagPack.load_from_file(
                    "", tagpack_file, schema, taxonomies, headerfile_dir
                )

                print(f"{tagpack_file}: ", end="")

                tagpack.validate()
                print_success("PASSED")

                # verify valid blockchain addresses using internal checksum
                if not args.no_address_validation:
                    tagpack.verify_addresses()

                no_passed += 1
    except (ValidationError, TagPackFileError) as e:
        print_fail("FAILED", e)

    status = "fail" if no_passed < n_tagpacks else "success"

    duration = round(time.time() - t0, 2)
    print_line(
        "{}/{} TagPacks passed in {}s".format(no_passed, n_tagpacks, duration), status
    )


def insert_tagpack(args):
    t0 = time.time()
    print_line("TagPack insert starts")
    print(f"Path: {args.path}")

    if args.no_git:
        base_url = args.path
        print_line("No repository detection done.")
    else:
        base_url = get_repository(args.path)
        print_line(f"Detected repository root in {base_url}")

    tagstore = TagStore(args.url, args.schema)

    schema = TagPackSchema()
    print_info(f"Loaded TagPack schema definition: {schema.definition}")

    config = _load_config(args.config)
    taxonomies = _load_taxonomies(config)
    taxonomy_keys = taxonomies.keys()
    print(f"Loaded taxonomies: {taxonomy_keys}")

    tagpack_files = collect_tagpack_files(args.path)

    # resolve backlinks to remote repository and relative paths
    scheck, nogit = not args.no_strict_check, args.no_git
    prepared_packs = [
        (m, h, n[0], n[1])
        for m, h, n in [
            (a, h, get_uri_for_tagpack(base_url, a, scheck, nogit))
            for h, fs in tagpack_files.items()
            for a in fs
        ]
    ]

    prefix = config.get("prefix", "")
    if args.add_new:  # don't re-insert existing tagpacks
        print_info("Checking which files are new to the tagstore:")
        prepared_packs = [
            (t, h, u, r)
            for (t, h, u, r) in prepared_packs
            if not tagstore.tp_exists(prefix, r)
        ]

    n_ppacks = len(prepared_packs)
    print_info(f"Collected {n_ppacks} TagPack files\n")

    no_passed = 0
    no_tags = 0
    public, force = args.public, args.force
    supported = tagstore.supported_currencies
    for i, tp in enumerate(sorted(prepared_packs), start=1):
        tagpack_file, headerfile_dir, uri, relpath = tp

        tagpack = TagPack.load_from_file(
            uri, tagpack_file, schema, taxonomies, headerfile_dir
        )

        print(f"{i} {tagpack_file}: ", end="")
        try:
            tagstore.insert_tagpack(tagpack, public, force, prefix, relpath)
            print_success(f"PROCESSED {len(tagpack.tags)} Tags")
            no_passed += 1
            no_tags = no_tags + len(tagpack.tags)
        except Exception as e:
            print_fail("FAILED", e)

    status = "fail" if no_passed < n_ppacks else "success"

    duration = round(time.time() - t0, 2)
    msg = "Processed {}/{} TagPacks with {} Tags in {}s. "
    msg += "Only tags for supported currencies {} are inserted."
    print_line(msg.format(no_passed, n_ppacks, no_tags, duration, supported), status)
    msg = "Don't forget to run 'tagstore refresh_views' soon to keep the database"
    msg += " consistent!"
    print_info(msg)


def _split_into_chunks(seq, size):
    return (seq[pos : pos + size] for pos in range(0, len(seq), size))


def insert_cluster_mapping_wp(currency, ks_mapping, args, batch):
    tagstore = TagStore(args.url, args.schema)
    gs = GraphSense(args.db_nodes, ks_mapping)
    clusters = gs.get_address_clusters(batch, currency)
    clusters["currency"] = currency
    tagstore.insert_cluster_mappings(clusters)
    return (currency, len(clusters))


def insert_cluster_mapping(args, batch_size=5_000):
    t0 = time.time()
    tagstore = TagStore(args.url, args.schema)
    df = pd.DataFrame(
        tagstore.get_addresses(args.update), columns=["address", "currency"]
    )
    ks_mapping = json.load(open(args.ks_file))
    currencies = ks_mapping.keys()
    gs = GraphSense(args.db_nodes, ks_mapping)

    processed_currencies = []

    workpackages = []
    for currency, data in df.groupby("currency"):
        if gs.contains_keyspace_mapping(currency):
            for batch in _split_into_chunks(data, batch_size):
                workpackages.append((currency, ks_mapping, args, batch))

    nr_workers = int(cpu_count() / 2)
    print(
        f"Processing {len(workpackages)} batches for "
        f"{len(currencies)} currencies on {nr_workers} workers."
    )

    with Pool(processes=nr_workers, maxtasksperchild=1) as pool:
        processed_workpackages = pool.starmap(insert_cluster_mapping_wp, workpackages)

    processed_currencies = {currency for currency, _ in processed_workpackages}

    for pc in processed_currencies:
        mappings_count = sum(
            [items for currency, items in processed_workpackages if currency == pc]
        )
        print_success(f"INSERTED/UPDATED {mappings_count} {pc} cluster mappings")

    tagstore.finish_mappings_update(currencies)
    duration = round(time.time() - t0, 2)
    print_line(
        f"Inserted {'missing' if not args.update else 'all'} cluster mappings "
        f"for {processed_currencies} in {duration}s",
        "success",
    )


def init_db(args):
    config = _load_config(args.config)

    if "taxonomies" not in config:
        print_line("No taxonomies configured to init the db", "fail")
        return

    t0 = time.time()
    print_line("Init database starts")
    insert_taxonomy(args)
    duration = round(time.time() - t0, 2)
    print_line(f"Init database in {duration}s", "success")


def update_db(args):
    tagstore = TagStore(args.url, args.schema)
    tagstore.refresh_db()
    print_info("All relevant views have been updated.")


def remove_duplicates(args):
    tagstore = TagStore(args.url, args.schema)
    rows_deleted = tagstore.remove_duplicates()
    msg = f"{rows_deleted} duplicate tags have been deleted from the database."
    print_info(msg)


def show_version():
    return "GraphSense TagPack management tool v" + version


def read_url_from_env():
    """
    Read environment variables from the OS, and build a postgresql connection
    URL. If the URL cannot be built, return None and an error message.
    """
    ev = dict(os.environ)
    try:
        url = f"postgresql://{ev['POSTGRES_USER']}:{ev['POSTGRES_PASSWORD']}"
        url += f"@{ev['POSTGRES_HOST']}:5432/{ev['POSTGRES_DB']}"
        msg = ""
    except KeyError:
        fields = ["USER", "PASSWORD", "HOST", "DB"]
        miss = {f"POSTGRES_{a}" for a in fields}
        miss -= set(ev.keys())
        msg = "Unable to build postgresql URL from environmnet variables: "
        msg += ", ".join(miss) + " not found."
        url = None
    return url, msg


def show_tagstore_composition(args):
    tagstore = TagStore(args.url, args.schema)
    headers = ["creator", "category", "is_public", "labels_count", "tags_count"]
    df = pd.DataFrame(tagstore.get_tagstore_composition(), columns=headers)

    if args.csv:
        print(df.to_csv(header=True, sep=",", index=True))
    else:
        with pd.option_context(
            "display.max_rows", None, "display.max_columns", None
        ):  # more options can be specified also
            print(tabulate(df, headers=headers, tablefmt="psql"))


def main():
    if sys.version_info < (3, 7):
        sys.exit("This program requires python version 3.7 or later")

    parser = ArgumentParser(
        description="GraphSense TagPack validation and insert tool",
        epilog="GraphSense TagPack Tool v{} - https://graphsense.info".format(version),
    )
    parser.add_argument("-v", "--version", action="version", version=show_version())
    parser.add_argument(
        "--config",
        help="path to config.yaml",
        default=os.path.join(os.getcwd(), CONFIG_FILE),
    )

    # Read the default URL from the .env file
    def_url, url_msg = read_url_from_env()

    subparsers = parser.add_subparsers(title="Commands")

    # parser for config command
    parser_c = subparsers.add_parser("config", help="show TagPack Repository config")
    parser_c.add_argument(
        "-v", "--verbose", action="store_true", help="verbose configuration"
    )
    parser_c.set_defaults(func=show_config)

    # parsers for tagpack command
    parser_tp = subparsers.add_parser("tagpack", help="tagpack commands")

    ptp = parser_tp.add_subparsers(title="TagPack commands")

    # parser for validate command
    ptp_v = ptp.add_parser("validate", help="validate TagPacks")
    ptp_v.add_argument(
        "path",
        nargs="?",
        metavar="PATH",
        default=os.getcwd(),
        help="TagPack file or folder root path (current folder by \
                    default)",
    )
    ptp_v.add_argument(
        "--no_address_validation",
        action="store_true",
        help="Disables checksum validation of addresses",
    )
    ptp_v.set_defaults(func=validate_tagpack)

    # parser for insert command
    ptp_i = ptp.add_parser("insert", help="insert TagPacks")
    ptp_i.add_argument(
        "path",
        nargs="?",
        metavar="PATH",
        default=os.getcwd(),
        help="TagPacks file or folder root path",
    )
    ptp_i.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for tagpack tables",
    )
    ptp_i.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    ptp_i.add_argument(
        "-b",
        "--batch_size",
        nargs="?",
        type=int,
        default=1000,
        help="batch size for insert)",
    )
    ptp_i.add_argument(
        "--public",
        action="store_true",
        help="By default, tagpacks are declared private in the database.\
                    Use this switch to declare them public.",
    )
    ptp_i.add_argument(
        "--force",
        action="store_true",
        help="By default, tagpack insertion stops when an already inserted\
                    tagpack exists in the database. Use this switch to force \
                    re-insertion.",
    )
    ptp_i.add_argument(
        "--add_new",
        action="store_true",
        help="By default, tagpack insertion stops when an already inserted\
                    tagpack exists in the database. Use this switch to insert \
                    new tagpacks while skipping over existing ones.",
    )
    ptp_i.add_argument(
        "--no_strict_check",
        action="store_true",
        help="Disables check for local modifications in git repository",
    )
    ptp_i.add_argument(
        "--no_git", action="store_true", help="Disables check for local git repository"
    )
    ptp_i.set_defaults(func=insert_tagpack, url=def_url)

    # parser for taxonomy command
    parser_t = subparsers.add_parser("taxonomy", help="taxonomy commands")
    parser_t.set_defaults(func=list_taxonomies)

    pxp = parser_t.add_subparsers(title="Taxonomy commands")

    # parser for taxonomy list command
    pxp_l = pxp.add_parser("list", help="list taxonomy concepts")
    pxp_l.set_defaults(func=list_taxonomies)

    # parser for taxonomy show command
    pxp_s = pxp.add_parser("show", help="show taxonomy concepts")
    pxp_s.add_argument(
        "taxonomy",
        metavar="TAXONOMY_KEY",
        choices=["abuse", "entity", "confidence"],
        help="the selected taxonomy",
    )
    pxp_s.add_argument("-v", "--verbose", action="store_true", help="verbose concepts")
    pxp_s.set_defaults(func=show_taxonomy_concepts)

    # parser for taxonomy insert command
    pxp_i = pxp.add_parser("insert", help="insert taxonomy into GraphSense")
    pxp_i.add_argument(
        "taxonomy",
        metavar="TAXONOMY_KEY",
        nargs="?",
        choices=["abuse", "entity", "confidence"],
        default=None,
        help="the selected taxonomy",
    )
    pxp_i.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for taxonomy tables",
    )
    pxp_i.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    pxp_i.set_defaults(func=insert_taxonomy, url=def_url)

    # parsers for database housekeeping
    parser_db = subparsers.add_parser("tagstore", help="database housekeeping commands")

    pdp = parser_db.add_subparsers(title="TagStore commands")

    # init the database
    pbp = pdp.add_parser("init", help="init the database")
    pbp.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for GraphSense cluster mapping table",
    )
    pbp.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    pbp.set_defaults(func=init_db, url=def_url, taxonomy=None)

    # insert_cluster_mappings [update]
    pc = pdp.add_parser("insert_cluster_mappings", help="insert cluster mappings")
    pc.add_argument(
        "-d",
        "--db_nodes",
        nargs="+",
        default=["localhost"],
        metavar="DB_NODE",
        help='Cassandra node(s); default "localhost")',
    )
    pc.add_argument(
        "-f",
        "--ks_file",
        metavar="KEYSPACE_FILE",
        help="JSON file with Cassandra keyspaces that contain GraphSense \
                    cluster mappings",
    )
    pc.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for GraphSense cluster mapping table",
    )
    pc.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    pc.add_argument("--update", action="store_true", help="update all cluster mappings")
    pc.set_defaults(func=insert_cluster_mapping, url=def_url)

    # refresh_views
    pd = pdp.add_parser("refresh_views", help="update views")
    pd.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for GraphSense cluster mapping table",
    )
    pd.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    pd.set_defaults(func=update_db, url=def_url)

    # remove_duplicates
    pr = pdp.add_parser("remove_duplicates", help="remove duplicate tags")
    pr.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for GraphSense cluster mapping table",
    )
    pr.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    pr.set_defaults(func=remove_duplicates, url=def_url)

    # show composition summary of the current tagstore.
    psc = pdp.add_parser(
        "show_composition",
        help="Shows the tag composition grouped by creator and category.",
    )
    psc.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for tagpack tables",
    )
    psc.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    psc.add_argument("--csv", action="store_true", help="Show csv output.")
    psc.set_defaults(func=show_tagstore_composition, url=def_url)

    # parser for quality measures
    parser_q = subparsers.add_parser("quality", help="calculate tags quality measures")
    parser_q.set_defaults(
        func=show_quality_measures, url=def_url, schema=_DEFAULT_SCHEMA, currency=""
    )

    pqp = parser_q.add_subparsers(title="Quality commands")

    # parser for quality measures calculation
    pqp_i = pqp.add_parser(
        "calculate", help="calculate quality measures for all tags in the DB"
    )
    pqp_i.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for quality measures tables",
    )
    pqp_i.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    pqp_i.set_defaults(func=calc_quality_measures, url=def_url)

    # parser for quality measures show
    pqp_s = pqp.add_parser("show", help="show average quality measures")
    pqp_s.add_argument(
        "--currency",
        default="",
        choices=["BCH", "BTC", "ETH", "LTC", "ZEC"],
        help="Show the avg quality measure for a specific crypto-currency",
    )
    pqp_s.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for quality measures tables",
    )
    pqp_s.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    pqp_s.set_defaults(func=show_quality_measures, url=def_url)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    if hasattr(args, "url") and not args.url:
        print_warn(url_msg)
        parser.error("No postgresql URL connection was provided. Exiting.")

    if not hasattr(args, "func"):
        parser.error("No action was requested. Exiting.")

    args.func(args)


if __name__ == "__main__":
    main()