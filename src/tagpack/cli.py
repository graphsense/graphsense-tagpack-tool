import json
import os
import sys
import tempfile
import time
from argparse import ArgumentParser
from multiprocessing import Pool, cpu_count

import pandas as pd
import yaml

# colorama fixes issues with redirecting colored outputs to files
from colorama import init
from git import Repo
from tabulate import tabulate
from yaml.parser import ParserError, ScannerError

from tagpack import get_version
from tagpack.actorpack import ActorPack
from tagpack.actorpack_schema import ActorPackSchema
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

DEFAULT_CONFIG = {
    "taxonomies": {
        "entity": "src/tagpack/db/entities.yaml",
        "abuse": "src/tagpack/db/abuses.yaml",
        "confidence": "src/tagpack/db/confidence.csv",
        "country": "src/tagpack/db/countries.csv",
    }
}


_DEFAULT_SCHEMA = "tagstore"


def _load_taxonomies(config):
    if "taxonomies" not in config:
        return None
    return {key: _load_taxonomy(config, key) for key in config["taxonomies"]}


def _load_taxonomy(config, key):
    if "taxonomies" not in config:
        return None
    uri = config["taxonomies"][key]
    taxonomy = Taxonomy(key, uri)
    remote = uri.startswith("http")
    if remote:
        taxonomy.load_from_remote()
    else:
        taxonomy.load_from_local()
    return taxonomy


def list_taxonomies(args=None):
    config = _load_config(args.config)

    print_line("Show configured taxonomies")
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
    uri = config["taxonomies"][args.taxonomy]
    print(f"URI: {uri}\n")
    taxonomy = _load_taxonomy(config, args.taxonomy)
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
            taxonomy = _load_taxonomy(config, t)
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


def low_quality_addresses(args):
    if not args.csv:
        print_line("Addresses with low quality")
    tagstore = TagStore(args.url, args.schema)

    try:
        th, curr, cat = args.threshold, args.currency, args.category
        la = tagstore.low_quality_address_labels(th, curr, cat)
        if la:
            if not args.csv:
                c = args.currency if args.currency else "all"
                print(f"List of {c} addresses and labels ({len(la)}):")
            else:
                print("currency,address,labels")

            intersections = []
            for (currency, address), labels in la.items():
                if args.csv:
                    labels_str = "|".join(labels)
                    print(f"{currency},{address},{labels_str}")
                else:
                    print(f"\t{currency}\t{address}\t{labels}")

                if not args.cluster:
                    continue

                # Produce clusters of addresses based on tag intersections
                seen = set()
                for i, (e, n) in enumerate(intersections):
                    seen = e.intersection(labels)
                    if seen:
                        e.update(labels)
                        n += 1
                        intersections[i] = (e, n)
                        break
                if not seen:
                    intersections.append((set(labels), 1))

            if args.cluster:
                print("\nSets of tags appearing in several addresses:")
                s_int = sorted(intersections, key=lambda x: x[1], reverse=True)
                for (k, v) in s_int:
                    if v > 1:
                        print(f"\t{v}: {', '.join(k)}")
        else:
            if not args.csv:
                print("\tNone")

    except Exception as e:
        print_fail(e)
        print_line("Operation failed", "fail")


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
        return DEFAULT_CONFIG
    return yaml.safe_load(open(cfile, "r"))


def show_config(args):
    if os.path.exists(args.config):
        print("Using Config File:", args.config)
    else:
        print_info(
            f"No override config file found at {args.config}. Using default values."
        )
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
    return f"GraphSense TagPack management tool {get_version()}"


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
    headers = (
        ["creator", "category", "is_public", "currency", "labels_count", "tags_count"]
        if args.by_currency
        else ["creator", "category", "is_public", "labels_count", "tags_count"]
    )
    df = pd.DataFrame(
        tagstore.get_tagstore_composition(by_currency=args.by_currency), columns=headers
    )

    if args.csv:
        print(df.to_csv(header=True, sep=",", index=True))
    else:
        with pd.option_context(
            "display.max_rows", None, "display.max_columns", None
        ):  # more options can be specified also
            print(tabulate(df, headers=headers, tablefmt="psql"))


def validate_actorpack(args):
    config = _load_config(args.config)

    t0 = time.time()
    print_line("ActorPack validation starts")
    print(f"Path: {args.path}")

    taxonomies = _load_taxonomies(config)
    taxonomy_keys = taxonomies.keys()
    print(f"Loaded taxonomies: {taxonomy_keys}")

    schema = ActorPackSchema()
    print(f"Loaded schema: {schema.definition}")

    actorpack_files = collect_tagpack_files(args.path, search_actorpacks=True)
    n_actorpacks = len([f for fs in actorpack_files.values() for f in fs])
    print_info(f"Collected {n_actorpacks} ActorPack files\n")

    no_passed = 0
    try:
        for headerfile_dir, files in actorpack_files.items():
            for actorpack_file in files:
                actorpack = ActorPack.load_from_file(
                    "", actorpack_file, schema, taxonomies, headerfile_dir
                )

                print(f"{actorpack_file}: ", end="")

                actorpack.validate()
                print_success("PASSED")

                no_passed += 1
    except (ValidationError, TagPackFileError, ParserError, ScannerError) as e:
        print_fail("FAILED", e)

    status = "fail" if no_passed < n_actorpacks else "success"

    duration = round(time.time() - t0, 2)
    msg = f"{no_passed}/{n_actorpacks} ActorPacks passed in {duration}s"
    print_line(msg, status)


def insert_actorpacks(args):
    t0 = time.time()
    print_line("ActorPack insert starts")
    print(f"Path: {args.path}")

    if args.no_git:
        base_url = args.path
        print_line("No repository detection done.")
    else:
        base_url = get_repository(args.path)
        print_line(f"Detected repository root in {base_url}")

    tagstore = TagStore(args.url, args.schema)

    schema = ActorPackSchema()
    print_info(f"Loaded ActorPack schema definition: {schema.definition}")

    config = _load_config(args.config)
    taxonomies = _load_taxonomies(config)
    taxonomy_keys = taxonomies.keys()
    print(f"Loaded taxonomies: {taxonomy_keys}")

    actorpack_files = collect_tagpack_files(args.path, search_actorpacks=True)

    # resolve backlinks to remote repository and relative paths
    # For the URI we use the same logic for ActorPacks than for TagPacks
    scheck, nogit = not args.no_strict_check, args.no_git
    prepared_packs = [
        (m, h, n[0], n[1])
        for m, h, n in [
            (a, h, get_uri_for_tagpack(base_url, a, scheck, nogit))
            for h, fs in actorpack_files.items()
            for a in fs
        ]
    ]

    prefix = config.get("prefix", "")
    if args.add_new:  # don't re-insert existing tagpacks
        print_info("Checking which ActorPacks are new to the tagstore:")
        prepared_packs = [
            (t, h, u, r)
            for (t, h, u, r) in prepared_packs
            if not tagstore.actorpack_exists(prefix, r)
        ]

    n_ppacks = len(prepared_packs)
    print_info(f"Collected {n_ppacks} ActorPack files\n")

    no_passed = 0
    no_actors = 0
    public, force = args.public, args.force

    for i, pack in enumerate(sorted(prepared_packs), start=1):
        actorpack_file, headerfile_dir, uri, relpath = pack

        actorpack = ActorPack.load_from_file(
            uri, actorpack_file, schema, taxonomies, headerfile_dir
        )

        print(f"{i} {actorpack_file}: ", end="")
        try:
            tagstore.insert_actorpack(actorpack, public, force, prefix, relpath)
            print_success(f"PROCESSED {len(actorpack.actors)} Actors")
            no_passed += 1
            no_actors += len(actorpack.actors)
        except Exception as e:
            print_fail("FAILED", e)

    status = "fail" if no_passed < n_ppacks else "success"

    duration = round(time.time() - t0, 2)
    msg = "Processed {}/{} ActorPacks with {} Actors in {}s."
    print_line(msg.format(no_passed, n_ppacks, no_actors, duration), status)


def list_actors(args):
    t0 = time.time()
    if not args.csv:
        print_line("List actors starts")

    tagstore = TagStore(args.url, args.schema)

    try:
        qm = tagstore.list_actors(category=args.category)
        if not args.csv:
            print(f"{len(qm)} Actors found")
        else:
            print("actorpack,actor_id,actor_label,concept_label")

        for row in qm:
            print(("," if args.csv else ", ").join(map(str, row)))

        duration = round(time.time() - t0, 2)
        if not args.csv:
            print_line(f"Done in {duration}s", "success")
    except Exception as e:
        print_fail(e)
        print_line("Operation failed", "fail")


def list_tags(args):
    t0 = time.time()
    if not args.csv:
        print_line("List tags starts")

    tagstore = TagStore(args.url, args.schema)

    try:
        uniq, cat, curr = args.unique, args.category, args.currency
        qm = tagstore.list_tags(unique=uniq, category=cat, currency=curr)
        if not args.csv:
            print(f"{len(qm)} Tags found")
        else:
            print("currency,tp_title,tag_label")
        for row in qm:
            print(("," if args.csv else ", ").join(map(str, row)))

        duration = round(time.time() - t0, 2)
        if not args.csv:
            print_line(f"Done in {duration}s", "success")
    except Exception as e:
        print_fail(e)
        print_line("Operation failed", "fail")


def list_address_actors(args):
    t0 = time.time()
    if not args.csv:
        print_line("List addresses with actor tags starts")

    tagstore = TagStore(args.url, args.schema)

    try:
        qm = tagstore.list_address_actors(currency=args.currency)
        if not args.csv:
            print(f"{len(qm)} addresses found")
        else:
            print("tag_id,tag_label,tag_address,tag_category,actor_label")

        for row in qm:
            print((", " if not args.csv else ",").join(map(str, row)))

        duration = round(time.time() - t0, 2)
        if not args.csv:
            print_line(f"Done in {duration}s", "success")
    except Exception as e:
        print_fail(e)
        print_line("Operation failed", "fail")


def update_tags_actors(args):
    """
    This function is for testing puposes. It allows to update some entries in
    the table `tag` using actors, and then update the corresponding entries in
    the table `address_quality`.
    """
    t0 = time.time()
    print_line("Update tag.actor field from actor table (fixed list)")

    tagstore = TagStore(args.url, args.schema)

    try:
        qm = tagstore.update_tags_actors()
        print(f"{qm} tags updated with values from table actor")

        qm = tagstore.update_quality_actors()
        print(f"{qm} entries in address_quality were updated")

        duration = round(time.time() - t0, 2)
        print_line(f"Done in {duration}s", "success")
    except Exception as e:
        print_fail(e)
        print_line("Operation failed", "fail")


def exec_cli_command(arguments):
    saved_argv = sys.argv
    try:
        sys.argv[1:] = arguments
        main()
    finally:
        sys.argv = saved_argv


def sync_repos(args):
    from shutil import rmtree

    if os.path.isfile(args.repos):
        with open(args.repos, "r") as f:
            repos = f.readlines()
        temp_dir = tempfile.gettempdir()
        temp_dir_tt = os.path.join(temp_dir, "tagpacks_to_sync")

        print_line("Init db taxonomies ...")
        exec_cli_command(["tagstore", "init"])

        for repo_url in repos:
            repo_url = repo_url.strip()
            print_line(f"Syncing {repo_url}. Temp files in: {temp_dir_tt}")

            try:
                print_line("Cloning...")
                Repo.clone_from(repo_url, temp_dir_tt)

                print_line("Inserting actorpacks ...")
                exec_cli_command(["actorpack", "insert", "--add_new", temp_dir_tt])

                print_line("Inserting tagpacks ...")
                exec_cli_command(["tagpack", "insert", "--add_new", temp_dir_tt])
            finally:
                print_line(f"Removing temp files in: {temp_dir_tt}")
                rmtree(temp_dir_tt)

        print_line("Removeing duplicates  ...")
        exec_cli_command(["tagstore", "remove_duplicates"])

        print_line("Refreshing db views ...")
        exec_cli_command(["tagstore", "refresh_views"])

        print_success("Your tagstore is now up-to-date again.")

    else:
        print_fail(f"Repos to sync file {args.repos} does not exist.")


def main():
    if sys.version_info < (3, 7):
        sys.exit("This program requires python version 3.7 or later")

    parser = ArgumentParser(
        description="GraphSense TagPack validation and insert tool",
        epilog="GraphSense TagPack Tool v{} - https://graphsense.info".format(
            get_version()
        ),
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

    # parser for sync command
    parser_c = subparsers.add_parser(
        "sync", help="git-repos to automatically keep track off."
    )
    parser_c.add_argument(
        "-r",
        "--repos",
        help="List of repos to sync to the database.",
        default=os.path.join(os.getcwd(), "tagpack-repos.config"),
    )
    parser_c.set_defaults(func=sync_repos)

    # parsers for tagpack command
    parser_tp = subparsers.add_parser("tagpack", help="tagpack commands")

    ptp = parser_tp.add_subparsers(title="TagPack commands")

    # parser for list tags command
    ptp_l = ptp.add_parser("list", help="list Tags")

    ptp_l.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for tagpack tables",
    )
    ptp_l.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    ptp_l.add_argument(
        "--unique",
        action="store_true",
        help="List Tags removing duplicates",
    )
    ptp_l.add_argument(
        "--category", default="", help="List Tags of a specific category"
    )
    ptp_l.add_argument(
        "--currency",
        default="",
        choices=["BCH", "BTC", "ETH", "LTC", "ZEC"],
        help="List Tags of a specific crypto-currency",
    )
    ptp_l.add_argument("--csv", action="store_true", help="Show csv output.")
    ptp_l.set_defaults(func=list_tags, url=def_url)

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

    # parsers for actorpack command
    parser_ap = subparsers.add_parser("actorpack", help="actorpack commands")

    app = parser_ap.add_subparsers(title="ActorPack commands")

    # parser for list actors command
    app_l = app.add_parser("list", help="list Actors")

    app_l.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for tagpack tables",
    )
    app_l.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    app_l.add_argument(
        "--category", default="", help="List Actors of a specific category"
    )
    app_l.add_argument("--csv", action="store_true", help="Show csv output.")
    app_l.set_defaults(func=list_actors, url=def_url)

    # parser for list addresses with actor-tags command
    app_a = app.add_parser("list_address_actor", help="list addresses-actors")

    app_a.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for tagpack tables",
    )
    app_a.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    app_a.add_argument(
        "--currency",
        default="",
        choices=["BCH", "BTC", "ETH", "LTC", "ZEC"],
        help="List addresses of a specific crypto-currency",
    )
    app_a.add_argument("--csv", action="store_true", help="Show csv output.")
    app_a.set_defaults(func=list_address_actors, url=def_url)

    # parser for list addresses with actor-tags command
    app_u = app.add_parser("update_tags_actors", help="Update tag.actor with actors")

    app_u.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for tagpack tables",
    )
    app_u.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    app_u.set_defaults(func=update_tags_actors, url=def_url)

    # parser for validate command
    app_v = app.add_parser("validate", help="validate ActorPacks")
    app_v.add_argument(
        "path",
        nargs="?",
        metavar="PATH",
        default=os.getcwd(),
        help="ActorPack file or folder root path (current folder by default)",
    )
    app_v.set_defaults(func=validate_actorpack)

    # parser for insert command
    app_i = app.add_parser("insert", help="insert ActorPacks")
    app_i.add_argument(
        "path",
        nargs="?",
        metavar="PATH",
        default=os.getcwd(),
        help="ActorPacks file or folder root path",
    )
    app_i.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for actorpack tables",
    )
    app_i.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    app_i.add_argument(
        "-b",
        "--batch_size",
        nargs="?",
        type=int,
        default=1000,
        help="batch size for insert",
    )
    app_i.add_argument(
        "--public",
        action="store_true",
        help="By default, actorpacks are declared private in the database.\
                    Use this switch to declare them public.",
    )
    app_i.add_argument(
        "--force",
        action="store_true",
        help="By default, actorpack insertion stops when an already inserted \
                actorpack exists in the database. Use this switch to force \
                re-insertion.",
    )
    app_i.add_argument(
        "--add_new",
        action="store_true",
        help="By default, actorpack insertion stops when an already inserted \
                actorpack exists in the database. Use this switch to insert \
                new actorpacks while skipping over existing ones.",
    )
    app_i.add_argument(
        "--no_strict_check",
        action="store_true",
        help="Disables check for local modifications in git repository",
    )
    app_i.add_argument(
        "--no_git", action="store_true", help="Disables check for local git repository"
    )
    app_i.set_defaults(func=insert_actorpacks, url=def_url)

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
        choices=["abuse", "entity", "confidence", "country"],
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
        choices=["abuse", "entity", "confidence", "country"],
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
    psc.add_argument(
        "--by-currency", action="store_true", help="Include currency in statistic."
    )
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

    # parser for quality measures list
    pqp_l = pqp.add_parser("list", help="list low quality addresses")
    pqp_l.add_argument(
        "--category", default="", help="List addresses of a specific category"
    )
    pqp_l.add_argument(
        "--currency",
        default="",
        choices=["BCH", "BTC", "ETH", "LTC", "ZEC"],
        help="Show low quality addresses of a specific crypto-currency",
    )
    pqp_l.add_argument(
        "--threshold",
        default=0.25,
        help="List addresses having a quality lower than this threshold",
    )
    pqp_l.add_argument(
        "-c",
        "--cluster",
        action="store_true",
        help="Cluster addresses having intersections of similar tags",
    )
    pqp_l.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        metavar="DB_SCHEMA",
        help="PostgreSQL schema for quality measures tables",
    )
    pqp_l.add_argument(
        "-u", "--url", help="postgresql://user:password@db_host:port/database"
    )
    pqp_l.add_argument("--csv", action="store_true", help="Show csv output.")
    pqp_l.set_defaults(func=low_quality_addresses, url=def_url)

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
