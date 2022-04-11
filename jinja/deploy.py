import boto3
import logging
from botocore.exceptions import ClientError
import os

import jinja2
import yaml


logging.getLogger().setLevel(logging.INFO)
client = boto3.client('cloudformation')


def create_stack(stack_name, template_body, **kwargs):
    """
    Create a CloudFormation stack.

    :param stack_name: Name of the stack.
    :param template_body: CloudFormation template.
    :param parameters: Parameters to pass to the CloudFormation template.
    :return:
    """
    try:
        client.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'],
            TimeoutInMinutes=30,
            OnFailure='ROLLBACK'
        )

        client.get_waiter('stack_create_complete').wait(
            StackName=stack_name,
            WaiterConfig={'Delay': 5, 'MaxAttempts': 600}
        )

        client.get_waiter('stack_exists').wait(StackName=stack_name)
        logging.info('Stack {} created successfully'.format(stack_name))

    except ClientError as e:
        logging.error(e)


def update_stack(stack_name, template_body, **kwargs):
    try:
        client.update_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
        )

    except ClientError as e:
        if 'No updates are to be performed' in str(e):
            logging.info(
                f'Skipping update at stack {stack_name}: No updates are to be performed')

    client.get_waiter('stack_update_complete').wait(
        StackName=stack_name,
        WaiterConfig={'Delay': 5, 'MaxAttempts': 600}
    )

    client.get_waiter('stack_exists').wait(StackName=stack_name)
    logging.info('Stack {} updated successfully'.format(stack_name))


def get_existing_stack():
    response = client.list_stacks(
        StackStatusFilter=['CREATE_COMPLETE',
                           'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE']
    )

    return [stack['StackName'] for stack in response['StackSummaries']]


def _get_abs_path(path):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), path)


def create_or_update_stack():
    stack_name = 'raw-actions-fernando-bucket'
    with open(_get_abs_path('../infra/bucket.yaml'), 'r') as f:
        template_body = f.read()

    existing_stacks = get_existing_stack()

    if stack_name in existing_stacks:
        logging.info('Updating stack {}'.format(stack_name))
        update_stack(stack_name, template_body)
    else:
        logging.info('Creating stack {}'.format(stack_name))
        create_stack(stack_name, template_body)


def renderize_template():
    logging.ifno(f'Rendering JINJA template')
    with open('redshift.yaml.j2', 'r') as f:
        redshift_yaml = f.read()

    with open('config.yaml', 'r') as f:
        config_yaml = yaml.safe_load(f)

    redshift_template = jinja2.Template(redshift_yaml)
    redshift_rendered = redshift_template.render({**config_yaml, **os.environ})

    with open('redshift.yaml', 'w') as f:
        f.write(redshift_rendered)
    logging.info(f'JINJA template rendered successfully')


if __name__ == '__main__':
    create_or_update_stack()
