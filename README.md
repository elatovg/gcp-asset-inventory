# gcp-asset-inventory

## Prereqs
First let's install the necessary libraries for python:

```bash
pip3 install -U -r requirements.txt
```

Now let's set the necessary environment variable:

```bash
> export DOMAIN="YOUR_DOMAIN"
> export GCP_ORG_ID=$(gcloud organizations list --filter displayName=${DOMAIN} --format 'value(name)')
```

Confirm it's set:

```bash
> echo $GCP_ORG_ID
2785XXXXXX
```

### Service Account, GCP Roles, and API
Let's create a dedicated service account the script will be executed as:

```bash
> export SA_NAME="asset-viewer"
> gcloud iam service-accounts create asset-viewer
```

Let's assign the role of `roles/cloudasset.viewer` at the organization level:

```bash
> export SA_EMAIL=$(gcloud iam service-accounts list --filter="email:${SA_NAME}" --format='value(email)')
> gcloud organizations add-iam-policy-binding ${GCP_ORG_ID} --member "serviceAccount:${SA_EMAIL}" --role 'roles/cloudasset.viewer'
```

If necessary generate and download a service account private key:

```bash
> gcloud iam service-accounts keys create ${SA_NAME}.json --iam-account ${SA_EMAIL}
```

Now authenticate as the service account to `gcloud`:

```bash
> gcloud auth activate-service-account ${SA_EMAIL} --key-file ${SA_NAME}.json
```

And lastly enable the **cloud asset** API:

```bash
> gcloud services enable cloudasset.googleapis.com
```

Now run a simple command to make sure you have permissions as the org level:

```bash
> gcloud asset search-all-resources --scope=organizations/${GCP_ORG_ID} --asset-types="iam.googleapis.com/ServiceAccount" --limit 1
```

Else if you are allowed to impersonate the account you can run the following without generating a service account key file:

```bash
> gcloud asset search-all-resources --scope=organizations/${GCP_ORG_ID} --asset-types="iam.googleapis.com/ServiceAccount" --limit 1 --impersonate-service-account ${SA_EMAIL}

WARNING: This command is using service account impersonation. All API calls will be executed as [asset-viewer@<PROJECT_ID>o.iam.gserviceaccount.com].
```

That should be it.

### Create a Storage Bucket (Optional)
If you are planning on storing the results in a storage bucket, first create the storage bucket:

```bash
> export BUCKET_NAME="my-globally-unique-bucket"
> export BUCKET_REGION="us-central1"
> gsutil mb -l ${BUCKET_REGION} gs://${BUCKET_NAME}
```

Then give write permission to your service account:

```bash
# get the project ID of the currently selected GCP Project
> export PROJECT_ID=$(gcloud config list --format 'value(core.project)')
# assign the roles/storage.objectAdmin role to your Service Account
> gcloud projects add-iam-policy-binding ${PROJECT_ID} --member "serviceAccount:${SA_EMAIL}" --role roles/storage.objectAdmin
```

## Execute it from your local machine
The script has two modes: local and remote. By default it runs in remote mode. In which case it will make APIs calls to get the information and then upload the results to a storage bucket.

### Remote mode
To run it just do the following and you should see similar output:

```bash
> export CSV_OUTPUT_FILE="out.csv"
> python3 main.py
Script running in remote mode
Wrote results to out.csv
Uploaded file out.csv to ${BUCKET_NAME}
```
And you can checkt out the contents of the file like so:

```
> gsutil cat gs://${GCS_BUCKET_NAME}/${CSV_OUTPUT_FILE}
```

### Local Mode
In local mode you need to generate the cloud asset outputs manually and pass them to the script:

```bash
# generate all the IAM Policies
> gcloud asset search-all-iam-policies --scope=organizations/${GCP_ORG_ID} --format json > all-iam-pol.json
# generate all the Service Accounts
gcloud asset search-all-resources --scope=organizations/${GCP_ORG_ID} --asset-types="iam.googleapis.com/ServiceAccount" --format json > all-sas.json
# run the script
> python3 main.py -l -i all-iam-pol.json -s all-sas.json -o out.csv
Script running in local mode
Wrote results to out.csv
```

And you can again check out the results:

```bash
> head -2 out.csv
First_Name,Last_Name,UniqueID,Entitlement,Email
service-PROJECT_NUM,service-PROJECT_NUM,service-PROJECT_NUM@compute-system.iam.gserviceaccount.com,roles/compute.serviceAgent -> Project (PROJECT_ID),service-PROJECT_NUM@compute-system.iam.gserviceaccount.com
```

#### Uploading to a Storage Bucket
In local mode you can optionally upload the results to a storage bucket as well:

```bash
> python3 main.py -l -i all-iam-pol.json -s all-sas.json -o out.csv -g ${GCS_BUCKET_NAME}
Script running in local mode
Wrote results to out.csv
Uploaded file out.csv to ${GCS_BUCKET_NAME}
```

## Execute it from a cloud function
The user creating the function will require the following role: `roles/cloudfunctions.admin`. And the following API has to be enabled: `cloudfunctions.googleapis.com`. Run the following to create the cloud function:

```bash
# setup all the variables
> export DOMAIN="YOUR_DOMAIN"
> export GCP_ORG_ID=$(gcloud organizations list --filter displayName=${DOMAIN} --format 'value(name)')
> export GCS_BUCKET_NAME="my-globally-unique-bucket"
> export CSV_OUTPUT_FILE="out.csv"
> export REGION="us-central1"
> export CLOUD_FN_NAME="asset-fn"
> export SA_NAME="asset-viewer"
> export SA_EMAIL=$(gcloud iam service-accounts list --filter="email:${SA_NAME}" --format='value(email)')
# check out the git repo
> git clone https://github.com/elatovg/gcp-asset-inventory
> cd gcp-asset-inventory
# deploy the function using the source in the current directory
> gcloud functions deploy ${CLOUD_FN_NAME} --runtime python39 \
  --set-env-vars "GCP_ORG_ID=${GCP_ORG_ID},GCS_BUCKET_NAME=${GCS_BUCKET_NAME},CSV_OUTPUT_FILE=${CSV_OUTPUT_FILE}" \
  --region ${REGION} --service-account ${SA_EMAIL} \
  --entry-point cf_entry_http --trigger-http --no-allow-unauthenticated
```

Then you can trigger the function manually:

```bash
> gcloud functions call ${CLOUD_FN_NAME} --data '{"test":"cool"}'
executionId: u4dyxx
result: Remote mode finished successfully
```

You can also check out the logs:

```bash
> gcloud functions logs read ${CLOUD_FN_NAME}
LEVEL  NAME      EXECUTION_ID  TIME_UTC                 LOG
D      asset-fn  u4dyzkf58yip  2022-03-05 19:58:57.547  Function execution took 2071 ms, finished with status code: 200
       asset-fn  u4dyzkf58yip  2022-03-05 19:58:57.545  Uploaded file /tmp/out.csv to ${GCS_BUCKET_NAME}
       asset-fn  u4dyzkf58yip  2022-03-05 19:58:57.083  Wrote results to /tmp/out.csv
       asset-fn  u4dyzkf58yip  2022-03-05 19:58:55.578  Script running in remote mode
       asset-fn  u4dyzkf58yip  2022-03-05 19:58:55.578  This Function was triggered by request <Request 'http://42ccd-dot-g10461acc672000ccp-tp.appspot.com/' [POST]>
D      asset-fn  u4dyzkf58yip  2022-03-05 19:58:55.477  Function execution started
```