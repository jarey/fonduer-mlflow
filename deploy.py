import mlflow.sagemaker as mfs

experiment_id = '0'
run_id = 'a904d110aafd452c9633d49dd4d2cf9a'
region = 'eu-west-1'
aws_id = '868167712403'
arn = 'arn:aws:iam::868167712403:role/SageMaker-role'

app_name = 'model-fonduer-emmental-model'
model_uri = f'artifacts/{experiment_id}/{run_id}/artifacts/fonduer_emmental_model'
tag_id = '1.23.0'

image_url = aws_id + '.dkr.ecr.' + region + '.amazonaws.com/mlflow-pyfunc:' + tag_id


mfs.deploy(app_name,
	model_uri=model_uri,
	region_name=region,
	mode='create',
	execution_role_arn=arn,
	image_url=image_url)