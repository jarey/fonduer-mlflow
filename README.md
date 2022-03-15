# Overview

This project aims at managing the lifecycle of a Fonduer-based application.
Roughly a Fonduer-based app lifecycle has three phases: development, training, and serving.

| Phase | Framework / Interface
| --- | --- |
| Development | Jupyter Notebook / Web GUI |
| Training | MLflow Project / CLI |
| Serving | MLflow Model / Rest API |

In the development phase, a developer writes Python codes in that a parser, mention/candidate extractors, labeling functions, and a classifier are defined.
Once they are defined, a model can be trained using a training document set.
A trained model will be deployed and will serve to extract knowledge from a new document.

Jupyter Notebook might be good for development but not always good for training and serving.
This project uses MLflow in the training phase for reproducibility (of training) and in the serving phase for packageability (of a trained model).

Contributions to the Fonduer project include

- Defined a Fonduer model: what it includes, which parts are common/different for different apps.
- Created a custom MLflow model for Fonduer, which can be used to package a trained Fonduer model, deploy it, and let it serve.

# Prerequisites

- MLflow (v1.1.0 or higher)
- Anaconda or Miniconda
- Docker
- Docker-compose

# Development

`fonduer_model.py` defines `FonduerModel` that is a custom MLflow model (see [here](https://www.mlflow.org/docs/latest/python_api/mlflow.pyfunc.html#creating-custom-pyfunc-models) for details) for Fonduer.
A developer is supposed to create a class, say `MyFonduerModel`, that inherits `FonduerModel` and implements `_classify(self, doc: Document) -> DataFrame`.

Also, a developer is supposed to create `fonduer_subclasses.py` and `fonduer_lfs.py`, each of which defines mention/candidate subclasses and labeling functions, respectively.

# Training

## Prepare

Download data.

```
$ ./download_data.sh
```

Deploy a PostgreSQL if you don't have one.

```
docker-compose up -d
```

Create a database.

```
docker exec fonduer-mlflow_postgres_1 createdb -U postgres pob_presidents
```

Create a folder for artifact storage

```
mkdir artifacts
```

Start the mlflow server 
The Mlflow server can use the postgres backend store (same of different database) or for example any other backend store
like sqlite for example

- postgres with same db as for the model
```
mlflow server --backend-store-uri postgresql://postgres:secure_pass_here@localhost:5432/pob_presidents --default-artifact-root ./artifacts --host 0.0.0.0
``` 
- sqlite:

```
mlflow server --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./artifacts --host 0.0.0.0
```
You can access the MLflow UI throught: http://localhost:5000 . There you will be able to follow the next actions,
while running experiments (training a model) and to store a model as a result of a run.

Export env variable so mlflow operations point to the running mlflow server

```
export MLFLOW_TRACKING_URI='http://0.0.0.0:5000'
```

## Train a model
The --experiment-id identifier has to match an existing experiment ID created from the MlFlow UI. By default the 0 is already created,
but you can choose to create a new one and spricy it by command line.
```
mlflow run ./ -P conn_string=postgresql://postgres:secure_pass_here@localhost:5432/pob_presidents --experiment-id 0
```

## Check the trained model

Two trained Fonduer models will be saved at `./fonduer_emmental_model` and `./fonduer_label_model with the following contents.

```bash
$ tree fonduer_emmental_model
fonduer_model
├── MLmodel
├── code
│   ├── fonduer_model.py
│   ├── fonduer_subclasses.py
│   └── my_fonduer_model.py
├── conda.yaml
└── mention_classes.pkl
└── candidate_classes.pkl
└── model.pkl
```

```bash
$ tree fonduer_label_model
fonduer_model
├── MLmodel
├── code
│   ├── fonduer_model.py
│   ├── fonduer_subclasses.py
│   └── my_fonduer_model.py
├── conda.yaml
└── mention_classes.pkl
└── candidate_classes.pkl
└── model.pkl
```

This two folders, conforming to the MLflow Model, is portable and can be deployed anywhere.

Note that the trained model can also be found under `./mlruns/<experiment-id>/<run-id>/artifacts`.

# Serving

There are a few ways to deploy a MLflow-compatible model (see [here](https://mlflow.org/docs/latest/models.html#deploy-mlflow-models) for details).
Let me show you one of the ways.

## Deploys the model as a local REST API server
We pass the --port flag to set deploying port to 5001 since the 5000 port is already in use by the mlflow server
```
mlflow models serve -m fonduer_emmental_model --port 5001 -w 1
```

```
$ mlflow models serve -m fonduer_label_model --port 5001 -w 1
```

or alternatively,

```
$ mlflow models serve -m runs:/<run-id>/fonduer_model -w 1
```

You can check model deployment availabilty using the ping endpoint with curl or with a browser:
```
curl -i http://127.0.0.1:5001/ping
``` 

You should see a 200 OK responsse code is eveything went OK.

If you send the following request to the API endpoint (`http://127.0.0.1:5001/invocations` in this case)

```
$ curl -X POST -H "Content-Type:application/json; format=pandas-split" \
  --data '{"columns":["html_path"], "data":["data/new/Al_Gore.html"]}' \
  http://127.0.0.1:5001/invocations
```

You will get a response like below (note that the response has been hardcoded in order to always reply with the same data, whatever the request content is):

```json
[
   {
      "A":1.0,
      "B":"2013-01-02T00:00:00",
      "C":1.0,
      "D":3,
      "E":"test",
      "F":"foo"
   },
   {
      "A":1.0,
      "B":"2013-01-02T00:00:00",
      "C":1.0,
      "D":3,
      "E":"train",
      "F":"foo"
   },
   {
      "A":1.0,
      "B":"2013-01-02T00:00:00",
      "C":1.0,
      "D":3,
      "E":"test",
      "F":"foo"
   },
   {
      "A":1.0,
      "B":"2013-01-02T00:00:00",
      "C":1.0,
      "D":3,
      "E":"train",
      "F":"foo"
   }
]
```

# Docker (experimental)

MLflow should be v1.8.0 or higher (mlflow/mlflow#2691, mlflow/mlflow#2699).

Build a Docker image

```
$ mlflow models build-docker -m fonduer_emmental_model -n fonduer_emmental_model
```

Deploy

```
$ docker run -p 5000:8080 -v "$(pwd)"/data:/opt/mlflow/data fonduer_emmental_model
```

# Acknowledgement

Most of the initial codes were derived from the wiki tutorial of [fonduer-tutorials](https://github.com/HazyResearch/fonduer-tutorials).
The Jupyter Notebook was converted to a Python script as follows:

```
$ jupyter nbconvert --to script some.ipynb
$ sed -i -e "s/get_ipython().run_line_magic('matplotlib', 'inline')/import matplotlib\nmatplotlib.use('Agg')/" some.py
```