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
import proto


def get_all_sas(org_id):
    """
    Get a list of Service Account and return them as a list of dictionaries
    """
    scope = f"organizations/{org_id}"
    asset_types = ['iam.googleapis.com/ServiceAccount']
    client = asset_v1.AssetServiceClient()
    response = client.search_all_resources(request={
        "scope": scope,
        "asset_types": asset_types
    })
    # all_sas = {}
    # for resource in response:
    #     # print(resource.name.split('/')[-1])
    #     gcp_sas_list.append(resource.name.split('/')[-1])
    ## converting protobuf to dictionary
    # https://github.com/googleapis/python-vision/issues/70#issuecomment-749135327
    serializable_assets = [proto.Message.to_dict(asset) for asset in response]
    # proto_contents = json.loads(serializable_assets)
    return serializable_assets


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
        # sa_permissions["bindings"] = MessageToDict(policy.policy)
        sa_permissions["asset_type"] = policy.asset_type
        sa_permissions["organization"] = policy.organization
        # print(sa_permissions)
        # print(policy)

    return sa_permissions


def get_all_iam_policies(org_id):
    """
    Given a service account get all the IAM policies attached to
    that service account
    """
    scope = f"organizations/{org_id}"
    client = asset_v1.AssetServiceClient()
    response = client.search_all_iam_policies(request={"scope": scope})
    ## converting protobuf to dictionary
    # https://github.com/googleapis/python-vision/issues/70#issuecomment-749135327
    serializable_assets = [proto.Message.to_dict(asset) for asset in response]
    return serializable_assets


def upload_content_gcp_bucket(gcp_bucket, dest_filename, file_contents):
    """Uploads a file to the bucket by using it's contents"""
    storage_client = storage.Client()
    bucket = storage_client.bucket(gcp_bucket)
    blob = bucket.blob(dest_filename)

    blob.upload_from_string(file_contents)


def upload_file_gcp_bucket(gcp_bucket, dest_filename, source_file):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(gcp_bucket)
    blob = bucket.blob(dest_filename)

    blob.upload_from_filename(source_file)


def import_json_as_dictionary(filename):
    """
    Given a json file import it and return the contents as a dictionary
    """
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

    return json_contents


def parse_assets_output(all_iam_policies_dictionary, all_sas_dictionary):
    """
    Take input from `gcloud asset search-all-iam-policies` and
    `gcloud asset search-all-resources --asset-types='iam.googleapis.com/ServiceAccount'`
    and produce a dictionary of those files merged
    """
    output_dict = {}
    ignored_sa_types = set(
        ('projectOwner', 'projectEditor', 'projectViewer', 'group'))
    # ignored_sa_accounts = set(('deleted'))
    for iam_policy in all_iam_policies_dictionary:
        if iam_policy['policy']['bindings']:
            for binding in iam_policy['policy']['bindings']:
                for member in binding['members']:
                    # print(member)
                    colon_counter = member.count(':')
                    if colon_counter == 1:
                        sa_type, sa_name = member.split(':')
                        sa_other = "notUsed"
                    elif colon_counter == 2:
                        sa_other, sa_type, sa_name = member.split(':')
                    else:
                        ## Usually no colons means it's allUsers,
                        # which is not in email format
                        sa_name = member
                        sa_type = member
                        sa_other = "notUsed"

                    if sa_type not in ignored_sa_types and sa_other != "deleted":
                        if sa_type != "allUsers":
                            f_name = sa_name.split('@')[0]
                            l_name = sa_name.split('@')[0]
                        else:
                            f_name = l_name = sa_name
                        email = sa_name
                        for svc_account in all_sas_dictionary:
                            # print(svc_account)
                            ## Looks like gcloud assets --format json and
                            # python client libraries uses different
                            # formatting for keys, gcloud uses camelCase
                            # and api use under_scores, manually checking
                            # for both to support both use cases
                            if 'additional_attributes' in svc_account:
                                if svc_account['additional_attributes'][
                                        'email'] == email:
                                    if 'display_name' in svc_account:
                                        if svc_account['display_name']:
                                            uid = svc_account['display_name']
                                            # print(svc_account)
                                        else:
                                            uid = sa_name
                                        ## Stop traversing the dictionary we
                                        ## determined the service account
                                        break
                            elif 'additionalAttributes' in svc_account:
                                if svc_account['additionalAttributes'][
                                        'email'] == email:
                                    if 'displayName' in svc_account:
                                        uid = svc_account['displayName']
                                        ## Stop traversing the dictionary we
                                        ## found service account
                                        break
                        else:
                            ## the DisplayName/Description is not
                            # defined for the service so using email
                            # for unique id
                            uid = sa_name
                        if 'assetType' in iam_policy:
                            rsc_type = iam_policy['assetType'].split('/')[-1]
                        elif 'asset_type' in iam_policy:
                            rsc_type = iam_policy['asset_type'].split('/')[-1]
                        rsc_name = iam_policy['resource'].split('/')[-1]
                        rsc = f"{rsc_type} ({rsc_name})"

                        if email in output_dict:
                            output_dict[email]['Entitlement'].append(
                                f"{binding['role']} -> {rsc}")
                        else:
                            output_dict[email] = {
                                "First_Name": f_name,
                                "Last_Name": l_name,
                                "UniqueID": uid,
                                "Email": email,
                                "Entitlement": [f"{binding['role']} -> {rsc}"]
                            }
        # print (json.dumps(output_dict, indent=2, default=str))
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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-l', '--local', action='store_true')
    group.add_argument('-r', '--remote', action='store_true')
    parser.add_argument('-g',
                        '--gcs_bucket',
                        help='upload results to gcs bucket')
    parser.add_argument('-i',
                        '--iam_file',
                        help='file containing all the iam policies')
    parser.add_argument('-s',
                        '--sas_file',
                        help='file containing all the service account')
    parser.add_argument('-o',
                        '--output_file',
                        help='name of file to write results to')
    args = parser.parse_args()

    if args.remote:
        if os.getenv("GCP_ORG_ID"):
            GCP_ORG_ID = os.getenv("GCP_ORG_ID")
        else:
            print("Pass in GCP ORG ID by setting an env var " +
                  "called 'GCP_ORG_ID'")
            exit(0)
        if os.getenv("GCS_BUCKET_NAME"):
            GCS_BUCKET = os.getenv("GCS_BUCKET_NAME")
        else:
            print("Pass in GCS Bucket by setting an env var " +
                  "called 'GCS_BUCKET_NAME'")
            exit(0)

        if os.getenv("CSV_OUTPUT_FILE"):
            CSV_FILENAME = os.getenv("CSV_OUTPUT_FILE")
        else:
            print("Pass in output filename by setting an env var " +
                  "called 'CSV_OUTPUT_FILE'")
            exit(0)

    ## If --remote is passed ignore the local variables
    if args.remote and (args.iam_file or args.sas_file):
        print("-r is specified but local files are passed in " +
              "either switch to local mode or remove the file arguements")
        exit(0)

    if args.local:
        ## We are in local mode, read in local json files
        IAM_JSON_FILENAME = args.iam_file
        SAS_JSON_FILENAME = args.sas_file
        ALL_IAM_POLICIES = import_json_as_dictionary(IAM_JSON_FILENAME)
        ALL_SVC_ACCTS = import_json_as_dictionary(SAS_JSON_FILENAME)
        if args.output_file:
            CSV_FILENAME = args.output_file
        else:
            CSV_FILENAME = IAM_JSON_FILENAME.replace('json', 'csv')
    else:
        ## Else we are in remote mode, use APIs to get assets results
        ALL_IAM_POLICIES = get_all_iam_policies(GCP_ORG_ID)
        ALL_SVC_ACCTS = get_all_sas(GCP_ORG_ID)

    ## Write out CSV from the Dictionary
    merged_iam_sa_dictionary = parse_assets_output(ALL_IAM_POLICIES,
                                                   ALL_SVC_ACCTS)
    write_dictionary_to_csv(merged_iam_sa_dictionary, CSV_FILENAME)
    print(f"Wrote results to {CSV_FILENAME}")

    if args.local:
        if args.gcs_bucket:
            GCS_BUCKET = args.gcs_bucket
            upload_file_gcp_bucket(GCS_BUCKET, CSV_FILENAME, CSV_FILENAME)
            print(f"uploaded file {CSV_FILENAME} to {GCS_BUCKET}")
    else:
        # we are in the remote mode, values should be obtained from env vars
        upload_file_gcp_bucket(GCS_BUCKET, CSV_FILENAME, CSV_FILENAME)
        print(f"uploaded file {CSV_FILENAME} to {GCS_BUCKET}")
