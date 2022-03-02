#!/usr/bin/env python3
"""
Script to get a list of service accounts and their IAM policy
with GCP asset inventory
"""
import os
import json
import codecs
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

    try:
        # Check if file is utf-8 encoded
        codecs.open(filename, encoding="utf-8", errors="strict").readline()
        utf_8 = True
        utf_16 = False
    except UnicodeDecodeError:
        utf_8 = False

    if not utf_8:
        try:
            # Check if file is utf-16-le encoded
            codecs.open(filename, encoding="utf-16-le",
                        errors="strict").readline()
            utf_16 = True
        except UnicodeDecodeError:
            utf_16 = False

    if utf_16:
        with open(filename, 'r', encoding='utf-16-le') as json_file_handler:
            data = json_file_handler.read()
            json_contents = json.loads(data.encode().decode('utf-8-sig'))
    elif utf_8:
        with open(filename, 'r') as json_file_handler:
            data = json_file_handler.read()
            json_contents = json.loads(data)
    else:
        print("Unable to determine file encoding, it's not utf-8 or utf-16-le")
        exit(0)
    for iam_policy in json_contents:
        if iam_policy['policy']['bindings']:
            for binding in iam_policy['policy']['bindings']:
                for member in binding['members']:
                    colon_counter = member.count(':')
                    if colon_counter == 1:
                        sa_type,sa_name = member.split(':')
                        sa_deleted = False
                    else:
                        sa_deleted,sa_type,sa_name = member.split(':')
                    if sa_type == "serviceAccount" and not sa_deleted:
                        f_name = sa_name.split('@')[0]
                        l_name = sa_name.split('@')[0]
                        uid = sa_name
                        email = sa_name
                        rsc_type = iam_policy['assetType'].split('/')[-1]
                        rsc_name = iam_policy['resource'].split('/')[-1]
                        rsc = f"{rsc_type} ({rsc_name})"

                        if email in output_dict:
                            output_dict[email]['Entitlement'].append(
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
        CSV_FILENAME = JSON_FILENAME.replace('json', 'csv')
        write_dictionary_to_csv(sa_dictionary, CSV_FILENAME)
        print(f"Wrote results to {CSV_FILENAME}")
    else:
        if os.getenv("GCP_ORG_ID"):
            GCP_ORG_ID = os.getenv("GCP_ORG_ID")
        else:
            print(
                "Pass in GCP ORG ID by setting an env var called 'GCP_ORG_ID'")
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
                        upload_results_gcp_bucket(GCS_BUCKET, sa_filename,
                                                  json_string)
                        print(f"uploaded file {sa_filename} to {GCS_BUCKET}")
                    else:
                        with open(sa_filename, "w") as wfh:
                            wfh.write(json_string)
                        print(f"created {sa_filename}")

        else:
            print("List of Service Accounts is 0, confirm your permissions")
            exit(0)
