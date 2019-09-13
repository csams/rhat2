#!/usr/bin/env python
import logging
import distributed
import dask.array as da
from dask_kubernetes import KubeCluster


logging.basicConfig(level=logging.INFO)

with KubeCluster.from_yaml('/usr/src/app/specs/worker-spec.yaml') as cluster:
    cluster.scale(4)
    # Connect dask to the cluster
    client = distributed.Client(cluster)

    # Create an array and calculate the mean
    array = da.ones((1000, 1000, 1000), chunks=(100, 100, 10))
    print(array.mean().compute())  # Should print 1.0
