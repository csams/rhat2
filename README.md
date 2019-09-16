rhat2
-----

Create service accounts with oc apply -f specs/service-account.yaml

The SA is tied to the Driver job in specs/job.yaml.

Repos
-----
- UI/API and DB
- CronJob to Watch the Job Queue and start Driver Pods
- Driver to launch a rule analysis
- Custom Dask Worker Image to pip install insights core and dependencies and download rule egg
