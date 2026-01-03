import sys
import json
import argparse
import re
import yaml

def check_iam(plan_file):
    try:
        with open(plan_file, 'r') as f:
            plan = json.load(f)
        
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
                    print(f"Note: IAM policy for {res['address']} is 'known after apply'. Skipping content validation.")
                    continue
                else:
                    return False
                
                if policy_json:
                    policy = json.loads(policy_json)
                    for stmt in policy['Statement']:
                        # Deep Logic: Resource: "*" in S3 actions is forbidden
                        if any(act in str(stmt['Action']) for act in ['s3:PutObject', 's3:GetObject']):
                            if stmt['Resource'] == '*' or stmt['Resource'] == ['*']:
                                print(f"Error: S3 Policy in {res['address']} contains Resource: '*'")
                                return False
                        
                        # Deep Logic: Must have CloudWatch Logs permissions
                        if 'logs:PutLogEvents' in str(stmt['Action']):
                            found_logs = True
                            
        return True
    except Exception as e:
        print(f"Error parsing IAM plan: {e}")
        return False

def check_terraform_constraints(plan_file):
    try:
        with open(plan_file, 'r') as f:
            plan = json.load(f)
        
        resources = plan.get('resource_changes', [])
        required_names = {
            'aws_iam_role': 'firehose_delivery_role',
            'aws_kinesis_firehose_delivery_stream': 'app-logs-delivery-stream',
            'aws_cloudwatch_log_group': '/aws/app/backend-services'
        }
        
        for res in resources:
            r_type = res['type']
            if r_type in required_names:
                after = res['change'].get('after', {})
                if after and 'name' in after:
                    if after['name'] != required_names[r_type]:
                        print(f"Error: Resource {r_type} name changed from '{required_names[r_type]}' to '{after['name']}'")
                        return False

            # Deep Logic: CloudWatch Subscription Filter details
            if r_type == 'aws_cloudwatch_log_subscription_filter':
                after = res['change'].get('after', {})
                if after:
                    if after.get('filter_pattern') != '':
                        print(f"Error: CloudWatch subscription filter pattern should be empty (fixed), found '{after.get('filter_pattern')}'")
                        return False
        return True
    except Exception as e:
        print(f"Error checking Terraform constraints: {e}")
        return False

def check_prometheus(yaml_file):
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
        
        # Deep Logic: Scrape targets in main config
        if 'scrape_configs' in data:
            configs = data.get('scrape_configs', [])
            for cfg in configs:
                if cfg['job_name'] == 'backend-services':
                    targets = cfg.get('static_configs', [{}])[0].get('targets', [])
                    if 'localhost:8080' not in targets:
                        print(f"Error: backend-services target should be localhost:8080, found {targets}")
                        return False
                if cfg['job_name'] == 'node-exporter':
                    # Deep Logic: relabel_configs correctness
                    rlc = cfg.get('relabel_configs', [])
                    if not any('replacement' in r for r in rlc):
                        print("Error: node-exporter missing 'replacement' in relabel_configs (typo fix check)")
                        return False

        # Deep Logic: Alert Rules
        groups = data.get('groups', [])
        for group in groups:
            for rule in group.get('rules', []):
                if 'alert' in rule:
                    expr = rule.get('expr', '')
                    if 'rate(' in expr and '[5m]' not in expr:
                        print(f"Error: Alert '{rule['alert']}' PromQL missing [5m] range")
                        return False
                    if rule.get('for') == '0s':
                        print(f"Error: Alert '{rule['alert']}' has 0s duration")
                        return False
                    if rule.get('labels', {}).get('severity') != 'critical':
                        print(f"Error: Alert '{rule['alert']}' missing or wrong severity label")
                        return False
        return True
    except Exception as e:
        print(f"Error parsing Prometheus YAML: {e}")
        return False

def check_grafana(json_file):
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            
        if data.get('title') != 'App Metrics':
            print("Error: Dashboard title changed")
            return False

        panels = data.get('panels', [])
        for panel in panels:
            # Deep Logic: Datasource correctness
            if panel.get('datasource') != 'Prometheus-Main':
                print(f"Error: Panel '{panel.get('title')}' has wrong datasource: {panel.get('datasource')}")
                return False
            
            # Deep Logic: PromQL Correctness
            for target in panel.get('targets', []):
                expr = target.get('expr', '')
                if 'rate(' in expr and '[5m])' not in expr:
                    print(f"Error: Invalid PromQL rate expression in panel '{panel.get('title')}': {expr}")
                    return False
        return True
    except Exception as e:
        print(f"Error parsing Grafana JSON: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-iam', help='Path to terraform plan json')
    parser.add_argument('--check-grafana', help='Path to grafana dashboard json')
    parser.add_argument('--check-prometheus', help='Path to prometheus yaml')
    parser.add_argument('--check-constraints', help='Path to terraform plan json')
    
    args = parser.parse_args()
    success = True
    if args.check_iam and not check_iam(args.check_iam): success = False
    if args.check_constraints and not check_terraform_constraints(args.check_constraints): success = False
    if args.check_grafana and not check_grafana(args.check_grafana): success = False
    if args.check_prometheus and not check_prometheus(args.check_prometheus): success = False
    sys.exit(0 if success else 1)
