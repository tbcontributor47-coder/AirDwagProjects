import sys
import json
import argparse
import yaml

def check_iam(plan_file):
    try:
        with open(plan_file, 'r') as f:
            plan = json.load(f)
        
        resources = plan.get('resource_changes', [])
        found_policy = False
        found_logs_permission = False
        
        for res in resources:
            change = res['change']
            after = change.get('after', {})
            
            # 1. Verify AssumeRole Service Principal (Architecture Constraint)
            if res['type'] == 'aws_iam_role':
                if after:
                    policy = json.loads(after.get('assume_role_policy', '{}'))
                    statements = policy.get('Statement', [])
                    if not any(s.get('Principal', {}).get('Service') == 'firehose.amazonaws.com' for s in statements):
                        print("Error: Firehose role missing correct service principal")
                        return False

            # 2. Verify Policy Contents (Least Privilege)
            if res['type'] == 'aws_iam_role_policy':
                found_policy = True
                policy_json = after.get('policy')
                if not policy_json and 'after_unknown' in change and 'policy' in change['after_unknown']:
                    print(f"Note: Policy for {res['address']} is known after apply. Skipping content verify.")
                    continue
                
                if policy_json:
                    policy = json.loads(policy_json)
                    for stmt in policy.get('Statement', []):
                        # Strict S3 scoping
                        if any(act in str(stmt['Action']) for act in ['s3:PutObject', 's3:GetObject']):
                            res_val = stmt.get('Resource', '')
                            if res_val == '*' or res_val == ['*']:
                                print(f"Error: S3 action in {res['address']} is not restricted to specific bucket")
                                return False
                        
                        # Verify CloudWatch Logs addition
                        if 'logs:PutLogEvents' in str(stmt['Action']):
                            found_logs_permission = True
                            # Must be scoped to the log group
                            res_val = str(stmt.get('Resource', ''))
                            if 'app_logs' not in res_val and 'backend-services' not in res_val:
                                print(f"Error: logs:PutLogEvents in {res['address']} lacks proper Resource scoping")
                                return False
                                
        if not found_policy:
            print("Error: No IAM role policy found")
            return False
        if not found_logs_permission:
            print("Error: Missing logs:PutLogEvents permission in Firehose policy")
            return False
            
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
            after = res['change'].get('after', {})
            if r_type in required_names and after:
                if after.get('name') != required_names[r_type]:
                    print(f"Error: Resource {r_type} name changed from '{required_names[r_type]}' to '{after.get('name')}'")
                    return False

            # Strict check for Subscription Filter
            if r_type == 'aws_cloudwatch_log_subscription_filter' and after:
                # Must fix the filter_pattern to be empty or valid
                if after.get('filter_pattern') != '':
                    print("Error: CloudWatch subscription filter pattern not empty/reset")
                    return False
        return True
    except Exception as e:
        print(f"Error checking Terraform constraints: {e}")
        return False

def check_prometheus(yaml_file):
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
        
        # 1. Scrape Config Logic
        if 'scrape_configs' in data:
            for cfg in data.get('scrape_configs', []):
                if cfg['job_name'] == 'backend-services':
                    t = cfg.get('static_configs', [{}])[0].get('targets', [])
                    if 'localhost:8080' not in t:
                        print(f"Error: backend-services target wrong: {t}")
                        return False
                if cfg['job_name'] == 'node-exporter':
                    rlc = str(cfg.get('relabel_configs', ''))
                    if 'replacement' not in rlc:
                        print("Error: node-exporter missing relabel typo fix")
                        return False

        # 2. Alert Rule Logic (Threshold & Duration)
        for group in data.get('groups', []):
            for rule in group.get('rules', []):
                if 'alert' in rule:
                    expr = rule.get('expr', '')
                    # MUST verify threshold logic
                    if '> 0.05' not in expr:
                        print(f"Error: Alert '{rule['alert']}' has wrong threshold/logic: {expr}")
                        return False
                    if '[5m]' not in expr:
                        print(f"Error: Alert '{rule['alert']}' missing [5m] range vector")
                        return False
                    if rule.get('for') != '1m':
                        print(f"Error: Alert '{rule['alert']}' must have '1m' duration (found {rule.get('for')})")
                        return False
                    if rule.get('labels', {}).get('severity') != 'critical':
                        print(f"Error: Alert '{rule['alert']}' missing critical severity")
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
            if panel.get('datasource') != 'Prometheus-Main':
                print(f"Error: Panel '{panel.get('title')}' uses wrong datasource")
                return False
            
            for target in panel.get('targets', []):
                expr = target.get('expr', '')
                # Verify PromQL functional correctness
                if 'rate(http_requests_total[5m])' not in expr:
                    print(f"Error: Invalid RPS query in panel '{panel.get('title')}': {expr}")
                    return False
        return True
    except Exception as e:
        print(f"Error parsing Grafana JSON: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-iam', help='Path to plan json')
    parser.add_argument('--check-grafana', help='Path to grafana json')
    parser.add_argument('--check-prometheus', help='Path to prometheus/alerts yaml')
    parser.add_argument('--check-constraints', help='Path to plan json')
    
    args = parser.parse_args()
    success = True
    if args.check_iam and not check_iam(args.check_iam): success = False
    if args.check_constraints and not check_terraform_constraints(args.check_constraints): success = False
    if args.check_grafana and not check_grafana(args.check_grafana): success = False
    if args.check_prometheus and not check_prometheus(args.check_prometheus): success = False
    sys.exit(0 if success else 1)
