#!/usr/bin/env python3
"""
Script to get a list of service accounts and their IAM policy
with GCP asset inventory
"""
import os
import json
import csv
import argparse
from google.cloud import asset_v1
from google.cloud import storage
from google.protobuf.json_format import MessageToDict


def get_sas(org_id):
    """
    Get a list of Service Account and return them as a list
    """
    scope = f"organizations/{org_id}"
    asset_types = ['iam.googleapis.com/ServiceAccount']
    client = asset_v1.AssetServiceClient()
    response = client.search_all_resources(request={
        "scope": scope,
        "asset_types": asset_types
    })
    gcp_sas_list = []
    for resource in response:
        # print(resource.name.split('/')[-1])
        gcp_sas_list.append(resource.name.split('/')[-1])

    return gcp_sas_list


def get_iam_policies(svc_account, org_id):
    """
    Given a service account get all the IAM policies attached to
    that service account
    """
    scope = f"organizations/{org_id}"
    query = f"policy:{svc_account}"
    client = asset_v1.AssetServiceClient()
    response = client.search_all_iam_policies(request={
        "scope": scope,
        "query": query
    })
    sa_permissions = {}
    for policy in response:
        sa_permissions["resource"] = policy.resource
        sa_permissions["project"] = policy.project
        sa_permissions["bindings"] = MessageToDict(policy.policy)
        sa_permissions["asset_type"] = policy.asset_type
        sa_permissions["organization"] = policy.organization
        # print(sa_permissions)
        # print(policy)

    return sa_permissions


def upload_results_gcp_bucket(gcp_bucket, dest_filename, file_contents):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(gcp_bucket)
    blob = bucket.blob(dest_filename)

    blob.upload_from_string(file_contents)


def parse_json(filename):
    """
    Take output from 'gcloud asset search-all-iam-policies' and
    organize by service accounts
    """
    output_dict = {}
    json_file_handler = open(filename)
    json_contents = json.load(json_file_handler)
    for iam_policy in json_contents:
        if iam_policy['policy']['bindings']:
            for binding in iam_policy['policy']['bindings']:
                for member in binding['members']:
                    f_name = member.split('@')[0]
                    l_name = member.split('@')[0]
                    uid = member
                    email = member
                    rsc_type = iam_policy['assetType'].split('/')[-1]
                    rsc_name = iam_policy['resource'].split('/')[-1]
                    rsc = f"{rsc_type} ({rsc_name})"

                    if member in output_dict:
                        output_dict[member]['Entitlement'].append(
                            f"{binding['role']} -> {rsc}")
                    else:
                        output_dict[member] = {
                            "First_Name": f_name,
                            "Last_Name": l_name,
                            "UniqueID": uid,
                            "Email": email,
                            "Entitlement": [f"{binding['role']} -> {rsc}"]
                        }
                    # print(
                    #     f"{member} -> {binding['role']} -> {iam_policy['assetType']}"
                    # )

    return output_dict


def write_dictionary_to_csv(dictionary, filename):
    '''
    Write the dictionary out to a csv file
    '''
    csv_columns = [
        'First_Name', 'Last_Name', 'UniqueID', 'Entitlement', 'Email'
    ]
    csv_file = filename
    try:
        with open(csv_file, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for _sa, sa_value in dictionary.items():
                sa_value['Entitlement'] = ";".join(sa_value['Entitlement'])
                writer.writerow(sa_value)
    except IOError:
        print("I/O error, can't write out CSV file")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-g',
                        '--gcs_bucket',
                        help='upload results to gcs bucket')
    parser.add_argument('-r',
                    '--read_file',
                    help='read json input from gcloud asset CLI output')
    args = parser.parse_args()
    if args.read_file:
        JSON_FILENAME = args.read_file
        sa_dictionary = parse_json(JSON_FILENAME)
        CSV_FILENAME = JSON_FILENAME.replace('json','csv')
        write_dictionary_to_csv(sa_dictionary,CSV_FILENAME)
        print(f"Wrote results to {CSV_FILENAME}")
    else:
        if os.getenv("GCP_ORG_ID"):
            GCP_ORG_ID = os.getenv("GCP_ORG_ID")
        else:
            print("Pass in GCP ORG ID by setting an env var called 'GCP_ORG_ID'")
            exit(0)
        gcp_sas = get_sas(GCP_ORG_ID)
        if len(gcp_sas) > 0:
            for sa in gcp_sas[:10]:
                sa_policy = get_iam_policies(sa, GCP_ORG_ID)
                if sa_policy:
                    sa_filename = f"{sa.split('@')[0]}.json"
                    json_string = json.dumps(sa_policy, indent=2)
                    if args.gcs_bucket:
                        GCS_BUCKET = args.gcs_bucket
                        upload_results_gcp_bucket(GCS_BUCKET, sa_filename, json_string)
                        print(f"uploaded file {sa_filename} to {GCS_BUCKET}")
                    else:
                        with open(sa_filename, "w") as wfh:
                            wfh.write(json_string)
                        print(f"created {sa_filename}")

        else:
            print("List of Service Accounts is 0, confirm your permissions")
            exit(0)
