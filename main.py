#!/usr/bin/env python3
"""
Script to get a list of service accounts and their IAM policy
with GCP asset inventory
"""
import os
import json
from google.cloud import asset_v1
from google.protobuf.json_format import MessageToDict

def get_sas(org_id):
    """
    Get a list of Service Account and return them as a list
    """
    scope = f"organizations/{org_id}"
    asset_types = ['iam.googleapis.com/ServiceAccount']
    client = asset_v1.AssetServiceClient()
    response = client.search_all_resources(
        request = {
            "scope": scope,
            "asset_types": asset_types
        }
    )
    gcp_sas_list = []
    for resource in response:
        # print(resource.name.split('/')[-1])
        gcp_sas_list.append(resource.name.split('/')[-1])

    return gcp_sas_list

def get_iam_policies(svc_account,org_id):
    """
    Given a service account get all the IAM policies attached to
    that service account
    """
    scope = f"organizations/{org_id}"
    query = f"policy:{svc_account}"
    client = asset_v1.AssetServiceClient()
    response = client.search_all_iam_policies(
        request={"scope": scope, "query": query}
    )
    sa_permissions = {}
    for policy in response:
        sa_permissions["resource"] = policy.resource
        sa_permissions["project"] = policy.project
        sa_permissions["bindings"] = MessageToDict(policy.policy)
        sa_permissions["asset_type"] = policy.asset_type
        sa_permissions["organization"] = policy.organization
        # print(sa_permissions)
        # print(policy)
        # print(json.dumps(MessageToDict(policy.policy)))

    return sa_permissions
if __name__ == "__main__":
    if os.getenv("GCP_ORG_ID"):
        GCP_ORG_ID = os.getenv("GCP_ORG_ID")
    else:
        print("Pass in GCP ORG ID by setting an env var called 'GCP_ORG_ID'")
        exit(0)
    gcp_sas = get_sas(GCP_ORG_ID)
    if len(gcp_sas) > 0:
        for sa in gcp_sas[:10]:
            sa_policy = get_iam_policies(sa,GCP_ORG_ID)
            if sa_policy:
                filename = f"{sa.split('@')[0]}.json"
                with open(filename, "w") as wfh:
                    json_string = json.dumps(sa_policy, indent=2)
                    wfh.write(json_string)
                print(f"created {filename}")

    else:
        print("List of Service Accounts is 0, confirm your permissions")
        exit(0)
    # get_sas(GCP_ORG_ID)
