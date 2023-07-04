# -*- coding: utf-8 -*-

import numpy as np
from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent_with_args
from cassandra.query import dict_factory
from pandas import DataFrame
from pandas import pandas as pd


def eth_address_to_hex(address):
    if type(address) != bytes:
        return address
    return "0x" + address.hex()


def eth_address_from_hex(address):
    # eth addresses are case insensitive
    try:
        b = bytes.fromhex(address[2:].lower())
    except Exception:
        return None
    return b


_CONCURRENCY = 100


class GraphSense(object):
    def __init__(self, hosts: list, ks_map: dict):
        self.hosts = hosts
        self.ks_map = ks_map
        self.cluster = Cluster(hosts)
        self.session = self.cluster.connect()
        self.session.row_factory = dict_factory

    def close(self):
        self.cluster.shutdown()
        print(f"Disconnected from {self.hosts}")

    def _execute_query(self, statement, parameters):
        """Generic query execution"""
        results = execute_concurrent_with_args(
            self.session, statement, parameters, concurrency=_CONCURRENCY
        )

        i = 0
        all_results = []
        for success, result in results:
            if not success:
                print("failed" + result)
            else:
                for row in result:
                    i = i + 1
                    all_results.append(row)
        return pd.DataFrame.from_dict(all_results)

    def contains_keyspace_mapping(self, currency: str) -> bool:
        return currency in self.ks_map

    def _check_passed_params(self, df: DataFrame, currency: str, req_column: str):
        if df.empty:
            raise Exception(f"Received empty dataframe for currency {currency}")
        if req_column not in df.columns:
            raise Exception(f"Missing column {req_column}")
        if not self.contains_keyspace_mapping(currency):
            raise Exception(f"Currency {currency} not in keyspace mapping")

    def _query_keyspace_config(self, keyspace: str) -> dict:
        self.session.set_keyspace(keyspace)
        query = "SELECT * FROM configuration"
        result = self.session.execute(query)
        return result[0]

    def keyspace_for_curreny_exists(self, currency: str) -> bool:
        if self.contains_keyspace_mapping(currency):
            for k, keyspace in self.ks_map.items():
                query = "SELECT keyspace_name FROM system_schema.keyspaces"
                result = self.session.execute(query)
                keyspaces = [row.keyspace_name for row in result]
                if keyspace not in keyspaces:
                    return False

            return True
        else:
            return False

    def get_address_ids(self, df: DataFrame, currency: str) -> DataFrame:
        """Get address ids for all passed addresses"""
        self._check_passed_params(df, currency, "address")

        keyspace = self.ks_map[currency]["transformed"]
        ks_config = self._query_keyspace_config(keyspace)
        self.session.set_keyspace(keyspace)

        df_temp = df[["address"]].copy()
        df_temp = df_temp.drop_duplicates()
        if currency == "ETH":
            df_temp["address_prefix"] = df_temp["address"].str[
                2 : 2 + ks_config["address_prefix_length"]
            ]
            df_temp["address_prefix"] = df_temp["address_prefix"].apply(
                lambda x: x.upper()
            )
            df_temp["address"] = df["address"].apply(lambda x: eth_address_from_hex(x))
        else:
            if "bech_32_prefix" in ks_config:
                df_temp["a"] = df_temp["address"].apply(
                    lambda x: x.replace(ks_config["bech_32_prefix"], "")
                )

            df_temp["address_prefix"] = df_temp["a"].str[
                : ks_config["address_prefix_length"]
            ]

        query = (
            "SELECT address, address_id "
            + "FROM address_ids_by_address_prefix "
            + "WHERE address_prefix=? and address=?"
        )

        statement = self.session.prepare(query)
        parameters = df_temp[["address_prefix", "address"]].to_records(index=False)

        result = self._execute_query(statement, parameters)
        if currency == "ETH":
            result["address"] = result["address"].apply(lambda x: eth_address_to_hex(x))

        return result

    def get_cluster_ids(self, df: DataFrame, currency: str) -> DataFrame:
        """Get cluster ids for all passed address ids"""
        self._check_passed_params(df, currency, "address_id")

        if currency == "ETH":
            raise Exception("eth does not have clusters")

        keyspace = self.ks_map[currency]["transformed"]
        ks_config = self._query_keyspace_config(keyspace)
        self.session.set_keyspace(keyspace)

        df_temp = df[["address_id"]].copy()
        df_temp = df_temp.drop_duplicates()
        df_temp["address_id_group"] = np.floor(
            df_temp["address_id"] / ks_config["bucket_size"]
        ).astype(int)

        query = (
            "SELECT address_id, cluster_id "
            + "FROM address WHERE address_id_group=? and address_id=?"
        )
        statement = self.session.prepare(query)
        parameters = df_temp[["address_id_group", "address_id"]].to_records(index=False)

        return self._execute_query(statement, parameters)

    def get_clusters(self, df: DataFrame, currency: str) -> DataFrame:
        """Get clusters for all passed cluster ids"""
        self._check_passed_params(df, currency, "cluster_id")

        if currency == "ETH":
            raise Exception("eth does not have clusters")

        keyspace = self.ks_map[currency]["transformed"]
        ks_config = self._query_keyspace_config(keyspace)
        self.session.set_keyspace(keyspace)

        df_temp = df[["cluster_id"]].copy()
        df_temp = df_temp.drop_duplicates()
        df_temp["cluster_id_group"] = np.floor(
            df_temp["cluster_id"] / ks_config["bucket_size"]
        ).astype(int)

        query = "SELECT * FROM cluster " + "WHERE cluster_id_group=? and cluster_id=?"
        statement = self.session.prepare(query)
        parameters = df_temp[["cluster_id_group", "cluster_id"]].to_records(index=False)

        return self._execute_query(statement, parameters)

    def _get_cluster_definers(self, df: DataFrame, currency: str) -> DataFrame:
        keyspace = self.ks_map[currency]["transformed"]
        ks_config = self._query_keyspace_config(keyspace)
        self.session.set_keyspace(keyspace)

        df_temp = df[["cluster_id"]].copy()
        df_temp.rename(columns={"cluster_id": "address_id"}, inplace=True)
        df_temp = df_temp.drop_duplicates()
        df_temp["address_id_group"] = np.floor(
            df_temp["address_id"] / ks_config["bucket_size"]
        ).astype(int)

        query = (
            "SELECT address_id as cluster_id, "
            "address as cluster_defining_address FROM address "
            + "WHERE address_id_group=? and address_id=?"
        )
        statement = self.session.prepare(query)
        parameters = df_temp[["address_id_group", "address_id"]].to_records(index=False)

        return self._execute_query(statement, parameters)

    def get_address_clusters(self, df: DataFrame, currency: str) -> DataFrame:
        self._check_passed_params(df, currency, "address")

        addresses = df.copy()

        if currency == "ETH":
            # tagpacks include invalid ETH addresses, ignore those
            addresses.drop(
                addresses[~addresses.address.str.startswith("0x")].index, inplace=True
            )
            addresses.rename(columns={"address": "checksum_address"}, inplace=True)
            addresses.loc[:, "address"] = addresses["checksum_address"].str.lower()

        df_address_ids = self.get_address_ids(addresses, currency)
        if len(df_address_ids) == 0:
            return DataFrame()
        if currency == "ETH":
            df_address_ids["cluster_id"] = df_address_ids["address_id"]
            df_address_ids["no_addresses"] = 1

            result = df_address_ids.merge(addresses, on="address")

            result.drop("address", axis="columns", inplace=True)
            result.rename(columns={"checksum_address": "address"}, inplace=True)
            result["cluster_defining_address"] = result["address"]

            return result

        df_cluster_ids = self.get_cluster_ids(df_address_ids, currency)
        if len(df_cluster_ids) == 0:
            return DataFrame()

        df_cluster_definers = self._get_cluster_definers(df_cluster_ids, currency)

        df_address_clusters = self.get_clusters(df_cluster_ids, currency)
        if len(df_address_clusters) == 0:
            return DataFrame()

        result = (
            df_address_ids.merge(df_cluster_ids, on="address_id", how="left")
            .merge(df_address_clusters, on="cluster_id", how="left")
            .merge(df_cluster_definers, on="cluster_id", how="left")
        )

        return result
