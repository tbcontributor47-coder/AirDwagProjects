import sys
import json
import argparse
import re
import yaml

def check_iam(plan_file):
    try:
        with open(plan_file, 'r') as f:
            plan = json.load(f)
        
        # Look for aws_iam_role_policy resources
        resources = plan.get('resource_changes', [])
        found_policy = False
        for res in resources:
            if res['type'] == 'aws_iam_role_policy':
                found_policy = True
                change = res['change']
                
                # Check for "policy" in 'after'. If it's unknown, it may be in 'after_unknown'
                policy_json = None
                after = change.get('after', {})
                if after and 'policy' in after:
                    policy_json = after['policy']
                elif 'after_unknown' in change and 'policy' in change['after_unknown']:
                    print(f"Note: IAM policy for {res['address']} is 'known after apply'. Skipping content validation but verifying existence.")
                    continue
                else:
                    print(f"Debug: Resource change for {res['address']}: {json.dumps(change, indent=2)}")
                    print(f"Error: Could not find 'policy' attribute in 'after' or 'after_unknown' for {res['address']}")
                    return False
                
                if policy_json:
                    policy = json.loads(policy_json)
                    for stmt in policy['Statement']:
                        # Check for "Resource": "*" in S3 actions
                        if 's3:PutObject' in stmt['Action'] or 's3:GetObject' in stmt['Action']:
                            if stmt['Resource'] == '*' or stmt['Resource'] == ['*']:
                                print(f"Error: S3 Policy in {res['address']} contains Resource: '*'")
                                return False
                            
        if not found_policy:
            print("Warning: No aws_iam_role_policy found in plan.")
        return True
    except Exception as e:
        print(f"Error parsing IAM plan: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_terraform_constraints(plan_file):
    try:
        with open(plan_file, 'r') as f:
            plan = json.load(f)
        
        resources = plan.get('resource_changes', [])
        # Required names from baseline
        required_names = {
            'aws_iam_role': 'firehose_delivery_role',
            'aws_kinesis_firehose_delivery_stream': 'app-logs-delivery-stream',
            'aws_cloudwatch_log_group': '/aws/app/logs'
        }
        
        found_names = {}
        for res in resources:
            r_type = res['type']
            if r_type in required_names:
                # Check the 'after' name
                after = res['change'].get('after', {})
                if after:
                    if 'name' in after:
                        found_names[r_type] = after['name']
                else:
                    # If after is missing, it might be an 'update' or no-change that we can't see easily here
                    # but usually for new/changed resources it should be there.
                    pass
                    
        for r_type, req_name in required_names.items():
            if r_type in found_names and found_names[r_type] != req_name:
                print(f"Error: Resource {r_type} name changed from '{req_name}' to '{found_names[r_type]}'")
                return False
        return True
    except Exception as e:
        print(f"Error checking Terraform constraints: {e}")
        return False

def check_prometheus(yaml_file):
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
        
        # Check constraints (job names)
        scrape_configs = data.get('scrape_configs', [])
        required_jobs = ['backend-services', 'node-exporter']
        found_jobs = [j.get('job_name') for j in scrape_configs]
        for job in required_jobs:
            if job not in found_jobs:
                print(f"Error: Job '{job}' missing or renamed in Prometheus config")
                return False

        groups = data.get('groups', [])
        for group in groups:
            rules = group.get('rules', [])
            for rule in rules:
                if 'alert' in rule:
                    expr = rule.get('expr', '')
                    # Check for rate() with range vector
                    if 'rate(' in expr and '[' not in expr:
                        print(f"Error: Prometheus alert '{rule['alert']}' has rate() without range vector")
                        return False
                    
                    # Check for duration
                    duration = rule.get('for', '0s')
                    if duration == '0s':
                        print(f"Error: Prometheus alert '{rule['alert']}' has 0s duration")
                        return False
                    
                    # Check for severity label (Constraint fix)
                    labels = rule.get('labels', {})
                    if 'severity' not in labels:
                        print(f"Error: Prometheus alert '{rule['alert']}' is missing 'severity' label")
                        return False
                    if labels['severity'] not in ['critical', 'warning']:
                        print(f"Error: Prometheus alert '{rule['alert']}' has invalid severity '{labels['severity']}'")
                        return False
        return True
    except Exception as e:
        print(f"Error parsing Prometheus YAML: {e}")
        return False

def check_grafana(json_file):
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            
        # Check constraints (title)
        if data.get('title') != 'App Metrics':
            print(f"Error: Dashboard title changed from 'App Metrics' to '{data.get('title')}'")
            return False

        panels = data.get('panels', [])
        if not panels:
            # Check for newer Grafana dashboard structure
            panels = data.get('rows', [])
            # Flatten if needed, but for now just basic existence
            
        found_query = False
        for panel in panels:
            targets = panel.get('targets', [])
            for target in targets:
                expr = target.get('expr', '')
                if expr:
                    found_query = True
                # Basic PromptQL syntax check: opening bracket must have closing
                if '[' in expr and ']' not in expr:
                    print(f"Error: Invalid PromQL expression: {expr}")
                    return False
                if '(' in expr and ')' not in expr:
                    print(f"Error: Invalid PromQL expression: {expr}")
                    return False
        return True
    except Exception as e:
        print(f"Error parsing Grafana JSON: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-iam', help='Path to terraform plan json')
    parser.add_argument('--check-grafana', help='Path to grafana dashboard json')
    parser.add_argument('--check-prometheus', help='Path to prometheus alerts yaml')
    parser.add_argument('--check-constraints', help='Path to terraform plan json for architectural checks')
    
    args = parser.parse_args()
    
    success = True
    if args.check_iam:
        if not check_iam(args.check_iam):
            success = False
            
    if args.check_constraints:
        if not check_terraform_constraints(args.check_constraints):
            success = False

    if args.check_grafana:
        if not check_grafana(args.check_grafana):
            success = False
            
    if args.check_prometheus:
        if not check_prometheus(args.check_prometheus):
            success = False
            
    sys.exit(0 if success else 1)
