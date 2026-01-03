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
            
            # 1. Verify AssumeRole Service Principal
            if res['type'] == 'aws_iam_role' and after:
                policy_json = after.get('assume_role_policy')
                if policy_json:
                    policy = json.loads(policy_json)
                    statements = policy.get('Statement', [])
                    if not any(s.get('Principal', {}).get('Service') == 'firehose.amazonaws.com' for s in statements):
                        print("Error: Firehose role missing correct service principal")
                        return False

            # 2. Verify Policy Contents (Least Privilege)
            if res['type'] == 'aws_iam_role_policy':
                found_policy = True
                policy_json = after.get('policy')
                
                # Handle "known after apply"
                if not policy_json:
                    if 'after_unknown' in change and 'policy' in change['after_unknown']:
                        print(f"Note: Policy for {res['address']} is known after apply. Scoping check bypassed.")
                        found_logs_permission = True 
                        continue
                
                if policy_json:
                    policy = json.loads(policy_json)
                    for stmt in policy.get('Statement', []):
                        # Strict S3 scoping
                        if any(act in str(stmt['Action']) for act in ['s3:PutObject', 's3:GetObject']):
                            res_val = str(stmt.get('Resource', ''))
                            if res_val == '*' or res_val == "['*']" or res_val == "['*']":
                                print(f"Error: S3 action in {res['address']} is not restricted to specific bucket")
                                return False
                        
                        # Verify CloudWatch Logs addition
                        if 'logs:PutLogEvents' in str(stmt['Action']):
                            found_logs_permission = True
                            # Must be scoped
                            res_val = str(stmt.get('Resource', ''))
                            if '*' == res_val or res_val == "['*']":
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
        
        found_sub_filter = False
        for res in resources:
            r_type = res['type']
            after = res['change'].get('after', {})
            if r_type in required_names and after:
                if after.get('name') != required_names[r_type]:
                    print(f"Error: Resource {r_type} name changed from '{required_names[r_type]}' to '{after['name']}'")
                    return False

            # Deep Link Logic: Verify Firehose/CloudWatch Integration
            if r_type == 'aws_cloudwatch_log_subscription_filter':
                found_sub_filter = True
                change = res['change']
                a_un = change.get('after_unknown', {})
                a = change.get('after', {})
                
                # Ensure it points to Firehose
                if not (a.get('destination_arn') or a_un.get('destination_arn')):
                    print("Error: Subscription filter missing destination_arn")
                    return False
                if not (a.get('role_arn') or a_un.get('role_arn')):
                    print("Error: Subscription filter missing role_arn")
                    return False
                if a.get('filter_pattern') != '':
                    print("Error: CloudWatch subscription filter pattern not empty/reset")
                    return False
        
        if not found_sub_filter:
            print("Error: Missing CloudWatch subscription filter")
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
            found_backend = False
            for cfg in data.get('scrape_configs', []):
                if cfg['job_name'] == 'backend-services':
                    found_backend = True
                    targets = cfg.get('static_configs', [{}])[0].get('targets', [])
                    if 'localhost:8080' not in targets:
                        print(f"Error: backend-services target wrong: {targets}")
                        return False
                if cfg['job_name'] == 'node-exporter':
                    rlc = str(cfg.get('relabel_configs', ''))
                    if 'replacement' not in rlc:
                        print("Error: node-exporter relabeling missing replacement fix")
                        return False
            if not found_backend:
                print("Error: Missing backend-services job")
                return False

        # 2. Alert Rule Logic (Functional Verification)
        if 'groups' in data:
            for group in data.get('groups', []):
                for rule in group.get('rules', []):
                    if 'alert' in rule:
                        expr = rule.get('expr', '')
                        if 'rate(' in expr and '[5m]' not in expr:
                            print(f"Error: Alert '{rule['alert']}' PromQL missing [5m]")
                            return False
                        if '> 0.05' not in expr:
                            print(f"Error: Alert '{rule['alert']}' has wrong logic")
                            return False
                        if rule.get('for') != '1m':
                            print(f"Error: Alert '{rule['alert']}' must have 1m duration")
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

        # 1. Variable Syntax (Required Fix)
        templating = data.get('templating', {}).get('list', [])
        # Since instructions mention variable fix, we expect at least one variable defined
        if len(templating) == 0:
            print("Error: Dashboard missing variables (as required by instructions)")
            return False
            
        for var in templating:
            if not var.get('name') or not var.get('type'):
                print("Error: Broken variable definition in Grafana")
                return False
            if var.get('type') == 'query' and 'label_values' not in var.get('query', {}).get('query', ''):
                print(f"Error: Invalid query variable syntax for '{var.get('name')}'")
                return False

        # 2. PromQL Logic
        panels = data.get('panels', [])
        for panel in panels:
            if panel.get('datasource') != 'Prometheus-Main':
                print(f"Error: Panel '{panel.get('title')}' uses wrong datasource")
                return False
            for target in panel.get('targets', []):
                expr = target.get('expr', '')
                if 'rate(http_requests_total[5m])' not in expr:
                    print(f"Error: Invalid RPS query: {expr}")
                    return False
        return True
    except Exception as e:
        print(f"Error parsing Grafana JSON: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-iam', help='Path to plan json')
    parser.add_argument('--check-grafana', help='Path to grafana json')
    parser.add_argument('--check-prometheus', help='Path to prometheus yaml')
    parser.add_argument('--check-constraints', help='Path to plan json')
    
    args = parser.parse_args()
    success = True
    if args.check_iam and not check_iam(args.check_iam): success = False
    if args.check_constraints and not check_terraform_constraints(args.check_constraints): success = False
    if args.check_grafana and not check_grafana(args.check_grafana): success = False
    if args.check_prometheus and not check_prometheus(args.check_prometheus): success = False
    sys.exit(0 if success else 1)
