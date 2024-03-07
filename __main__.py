# Copyright 2016-2024, Pulumi Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pulumi
import json
import pulumi_aws as aws
import pulumi_docker as docker

config = pulumi.Config()
container_context = config.get("container-context")
if container_context is None:
    container_context = "."
container_file = config.get("container-file")
if container_file is None:
    container_file = "./Dockerfile"
open_api_key = config.get("open-api-key")
if open_api_key is None:
    open_api_key = "CHANGEME"
pulumi_project = pulumi.get_project()
pulumi_stack = pulumi.get_stack()
langserve_ecr_repository = aws.ecr.Repository("langserve-ecr-repository",
    name=f"{pulumi_project}-{pulumi_stack}",
    force_delete=True)
token = aws.ecr.get_authorization_token_output(registry_id=langserve_ecr_repository.registry_id)
langserve_ecr_image = docker.Image("langserve-ecr-image",
    build=docker.DockerBuildArgs(
        platform="linux/amd64",
        context=container_context,
        dockerfile=container_file,
    ),
    image_name=langserve_ecr_repository.repository_url,
    registry=docker.RegistryArgs(
        server=langserve_ecr_repository.repository_url,
        username=token.user_name,
        password=pulumi.Output.secret(token.password),
    ))

# Create the role for the Lambda to assume
lambda_role = aws.iam.Role("lambdaRole", 
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
                "Action": "sts:AssumeRole",
                "Principal": {
                    "Service": "lambda.amazonaws.com",
                },
                "Effect": "Allow",
                "Sid": "",
            }]
    }))

# Attach the fullaccess policy to the Lambda role created above
role_policy_attachment = aws.iam.RolePolicyAttachment("lambdaRoleAttachment",
    role=lambda_role,
    policy_arn=aws.iam.ManagedPolicy.AWS_LAMBDA_BASIC_EXECUTION_ROLE)

# Create the lambda to execute
lambda_function = aws.lambda_.Function("lambdaFunction", 
    image_uri=langserve_ecr_image.repo_digest,
    package_type="Image",
    role=lambda_role.arn,
    environment={
        "variables": {
            'OPENAI_API_KEY': open_api_key,
        }
    })

# Give API Gateway permissions to invoke the Lambda
lambda_permission = aws.lambda_.Permission("lambdaPermission", 
    action="lambda:InvokeFunction",
    principal="apigateway.amazonaws.com",
    function=lambda_function)

# Set up the API Gateway
apigw = aws.apigatewayv2.Api("httpApiGateway", 
    protocol_type="HTTP",
    target=lambda_function.invoke_arn)

# Export the API endpoint for easy access
pulumi.export("endpoint", apigw.api_endpoint)
