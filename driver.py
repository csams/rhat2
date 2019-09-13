#!/usr/bin/env python
import logging
import distributed
import dask.array as da
from dask_kubernetes import KubeCluster


logging.basicConfig(level=logging.DEBUG)

with KubeCluster.from_yaml('/usr/src/app/worker-spec.yaml') as cluster:
    # Connect dask to the cluster
    client = distributed.Client(cluster)

    # Create an array and calculate the mean
    array = da.ones((1000, 1000, 1000), chunks=(100, 100, 10))
    print(array.mean().compute())  # Should print 1.0
