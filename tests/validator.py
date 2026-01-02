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
        for res in resources:
            if res['type'] == 'aws_iam_role_policy':
                policy_json = res['change']['after']['policy']
                policy = json.loads(policy_json)
                
                for stmt in policy['Statement']:
                    # Check for "Resource": "*" in S3 actions
                    if 's3:PutObject' in stmt['Action'] or 's3:GetObject' in stmt['Action']:
                        if stmt['Resource'] == '*':
                            print("Error: S3 Policy contains Resource: '*'")
                            return False
                            
                    # Check for Missing logs actions
                    # We expect something like logs:PutLogEvents or kinesis:* 
                    # Just basic check if they fixed the logs permission
        return True
    except Exception as e:
        print(f"Error parsing IAM plan: {e}")
        return False

def check_prometheus(yaml_file):
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
        
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
        return True
    except Exception as e:
        print(f"Error parsing Prometheus YAML: {e}")
        return False

def check_grafana(json_file):
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            
        panels = data.get('panels', [])
        for panel in panels:
            targets = panel.get('targets', [])
            for target in targets:
                expr = target.get('expr', '')
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
    
    args = parser.parse_args()
    
    success = True
    if args.check_iam:
        if not check_iam(args.check_iam):
            success = False
            
    if args.check_grafana:
        if not check_grafana(args.check_grafana):
            success = False
            
    if args.check_prometheus:
        if not check_prometheus(args.check_prometheus):
            success = False
            
    sys.exit(0 if success else 1)
