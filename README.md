# gcp-asset-inventory

## Prereqs
First let's install the necessary libraries for python:

```bash
pip3 install -U google-cloud-asset protobuf
```

Now let's set the necessary environment variable:

```bash
export DOMAIN="YOUR_DOMAIN"
export GCP_ORG_ID=$(gcloud organizations list --filter displayName=${DOMAIN} --format 'value(name)')
```

Confirm it's set:

```bash
> echo $GCP_ORG_ID
2785XXXXXX
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