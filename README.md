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

Now run a simple command to make sure you have permissions as the org level:

```bash
> gcloud asset search-all-resources --scope=organizations/${GCP_ORG_ID} --asset-types="iam.googleapis.com/ServiceAccount" --limit 1
```

Else if you are allowed to impersonate the account you can run the following without generating a service account key file:

```bash
> gcloud asset search-all-resources --scope=organizations/278534702455 --asset-types="iam.googleapis.com/ServiceAccount" --limit 1 --impersonate-service-account ${SA_EMAIL}

WARNING: This command is using service account impersonation. All API calls will be executed as [asset-viewer@<PROJECT_ID>o.iam.gserviceaccount.com].
```

And lastly enable the **cloud asset** API:

```bash
> gcloud services enable cloudasset.googleapis.com
```

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
> gcloud projects add-iam-policy-binding ${PROJECT_ID} --member ${SA_EMAIL} --role roles/storage.objectAdmin
```

## Execute it
To run it just do the following and you should see similar output:

```bash
 > python3 main.py
created hns-onprem.json
created vault-server.json
created cfmgr-sa.json
created cloudfn-tf.json
created secretmgr-sa.json
created secretmanager-tf.json
created dataproc-tf.json
created test-sa.json
created terraf-limited.json
```

Then check out one of the files to confirm you can see the policy:

```bash
 > cat test-sa.json
{
  "resource": "//cloudresourcemanager.googleapis.com/projects/hns-spoke",
  "project": "projects/6421XXXXX",
  "bindings": {
    "bindings": [
      {
        "role": "roles/pubsub.editor",
        "members": [
          "serviceAccount:test-sa@hns-spoke.iam.gserviceaccount.com"
        ]
      }
    ]
  },
  "asset_type": "cloudresourcemanager.googleapis.com/Project",
  "organization": "organizations/278XXXX"
}%
```

### Uploading to a Storage Bucket
You can pass in the `-g` flag and it will upload the results to a storage bucket, here is how it will look:

```bash
> python3 main.py -g my-bucket
uploaded file ci-account.json to my-bucket
uploaded file tf-testing.json to my-bucket
uploaded file onprem.json to my-bucket
uploaded file vault-server.json to my-bucket
uploaded file cfmgr-sa.json to my-bucket
uploaded file cloudfn-tf.json to my-bucket
uploaded file secretmgr-sa.json to my-bucket
uploaded file test-sa.json to my-bucket
```

You will also see the files in the storage bucket:

```bash
> gsutil ls "gs://my-bucket/*.json"
gs://my-bucket/cfmgr-sa.json
gs://my-bucket/ci-account.json
gs://my-bucket/cloudfn-tf.json
gs://my-bucket/hns-onprem.json
gs://my-bucket/secretmgr-sa.json
gs://my-bucket/tf-testing.json
gs://my-bucket/vault-server.json
gs://my-bucket/test-sa.json
```

And lastly you can also confirm the contents of the file:

```bash
> gsutil cat gs://my-bucket/test-sa.json
{
  "resource": "//cloudresourcemanager.googleapis.com/projects/hns-spoke",
  "project": "projects/6421XXXXX",
  "bindings": {
    "bindings": [
      {
        "role": "roles/pubsub.editor",
        "members": [
          "serviceAccount:test-sa@hns-spoke.iam.gserviceaccount.com"
        ]
      }
    ]
  },
  "asset_type": "cloudresourcemanager.googleapis.com/Project",
  "organization": "organizations/278XXXX"
}%
```

### Reading output from a JSON File
Another approach you can take is generate the asset inventory output with `gcloud asset` CLI as JSONand then pass that JSON file as input to this script by using the `-r` flag. First generate the JSON file:

```bash
gcloud asset search-all-iam-policies --scope=organizations/${GCP_ORG_ID} --format json > all-iam-policies.json
```

Then pass that to the script to generate a CSV file:

```bash
> python3 main.py -r all-iam-policies.json
Wrote results to all-iam-policies.csv
```
