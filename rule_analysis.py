#!/usr/bin/env python
import argparse
import json

import dask.bag as db
import pandas as pd

from dask.distributed import Client

from sklearn.metrics.pairwise import pairwise_distances

from insights import condition, incident, rule, dr, load_default_plugins, make_response
from insights.combiners.redhat_release import RedHatRelease
from insights.core.archives import extract
from insights.core.hydration import create_context
from insights.core.plugins import is_type


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("-i", "--input", default="input.txt", help="one archive path per line.")
    p.add_argument("-p", "--plugin", help="The fully qualified name of the rule: examples.rules.bash_version.report")
    return p.parse_args()


def load_archives(path):
    with open(path) as f:
        return [l.rstrip() for l in f]


def extract_hits(components, results):
    hits = {}
    for c in sorted(components, key=dr.get_name):
        val = results.get(c)
        if val is not None:
            hits[c.__name__] = True if val else False
        else:
            hits[c.__name__] = None
    return hits


DEP_CACHE = {}


def _get_deps(rule_func):
    graph = dr.get_dependency_graph(rule_func)
    graph.update(dr.get_dependency_graph(RedHatRelease))

    deps = [c for c in graph if is_type(c, condition) or is_type(c, incident)]
    return graph, deps


def get_deps(rule_func):
    if rule_func not in DEP_CACHE:
        DEP_CACHE[rule_func] = _get_deps(rule_func)
    return DEP_CACHE[rule_func]


LOADED = [False]


def get_rule_hit_info(archive, rule_name, timeout=None, tmp_dir=None):
    # We have to load everything again for multiprocessing or clustering to
    # work. Even though imports are cached internally after the first call,  we
    # can still optimize a bit with this LOADED hack.
    rule_func = dr.get_component(rule_name)

    if not LOADED[0]:
        load_default_plugins()
        LOADED[0] = True

    # this is also cached behind get_deps after the first call.
    graph, bool_deps = get_deps(rule_func)

    with extract(archive, timeout=timeout, extract_dir=tmp_dir) as arc:
        ctx = create_context(arc.tmp_dir, None)
        broker = dr.Broker()
        broker[ctx.__class__] = ctx

        results = dr.run(graph, broker=broker)

        rule_result = results.get(rule_func)
        rhr = results.get(RedHatRelease)

        result = extract_hits(bool_deps, results)

        result["archive"] = archive
        result["key"] = rule_result.get_key() if rule_result else None
        result["type"] = rule_result.__class__.__name__ if rule_result else None
        result["make_fail"] = True if rule_result and isinstance(rule_result, make_response) else False
        result["major"] = rhr.major if rhr else -1
        result["minor"] = rhr.minor if rhr else -1
        return result


def run_rule(archives, rule_func, part_size=10):
    graph, bool_deps = _get_deps(rule_func)
    bool_deps = sorted([c.__name__ for c in bool_deps])

    # dask needs the dataframe schema up front when converting a bag.
    meta = {d: "bool" for d in bool_deps}
    meta["archive"] = "str"
    meta["key"] = "str"
    meta["type"] = "str"
    meta["major"] = "Int8"
    meta["minor"] = "Int8"
    meta["make_fail"] = "bool"

    bag = db.from_sequence(archives, partition_size=part_size)
    result = bag.map(get_rule_hit_info, dr.get_name(rule_func))
    df = result.to_dataframe(meta)
    return df


def analyze(hit_data, rule_func):
    """
    Calculate how many times the conditions, incidents, and rule fired for each
    major version of RHEL.

    How many times each (response type, key) pair was seen for each version of
    RHEL.

    Correlation matrix between conditions, incidents, and make_fails.
    """
    _, bool_deps = _get_deps(rule_func)
    cols = [d.__name__ for d in bool_deps] + ["make_fail"]

    num_archives = hit_data["archive"].count()
    num_archives_by_rhel = hit_data["major"].value_counts()
    hits_by_rhel = hit_data.groupby("major")[cols].sum()
    hits_by_vtk = hit_data.groupby(["major", "type", "key"]).size()

    # here we pull data back and have a local pandas dataframe for just the
    # condition, incidents, and "make_fail" columns. They're all bools and so
    # should easily fit into local memory even with many archives.
    parts = hit_data[cols].compute()

    # similarity matrix for all conditions, incidents, and make_fail.
    # see https://stackoverflow.com/a/37004489/1451664
    # we can use sklearn on local pandas dataframes.
    jac_sim = 1 - pairwise_distances(parts.T, metric="hamming")
    jac_sim = pd.DataFrame(jac_sim, index=parts.columns, columns=parts.columns)

    results = {
        "num_archives": int(num_archives.compute()),
        "num_archives_by_rhel": num_archives_by_rhel.compute().to_dict(),
        "hits_by_rhel": hits_by_rhel.astype(int).compute().to_dict(),
        "hits_by_vtk": hits_by_vtk.astype(int).compute().reset_index(name="counts").to_dict(orient="records"),
        "grand_totals": parts.sum().to_dict(),
        "similarity": jac_sim.to_dict(orient="records")
    }

    return results


def main(client):
    args = parse_args()

    rule_func = dr.get_component(args.plugin)
    if not is_type(rule_func, rule):
        print(f"{dr.get_name(rule_func)} is not a rule.")
        return

    archives = load_archives(args.input)
    hit_data = run_rule(archives, rule_func)

    hit_data = client.persist(hit_data)
    analysis = analyze(hit_data, rule_func)
    print(json.dumps(analysis))


if __name__ == "__main__":
    with Client(n_workers=1, threads_per_worker=1) as client:
        main(client)
