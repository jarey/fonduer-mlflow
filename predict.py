import logging
import pickle
import sys

import mlflow.pyfunc
import numpy as np
import pandas as pd
import torch

from fonduer import Meta, init_logging
from fonduer.candidates import CandidateExtractor, MentionExtractor
from fonduer.features import Featurizer
from fonduer.learning import LogisticRegression
from fonduer.parser import Parser
from fonduer.parser.preprocessors import HTMLDocPreprocessor

ABSTAIN = 0
FALSE = 1
TRUE = 2

# Configure logging for Fonduer
init_logging(log_dir="logs")
logger = logging.getLogger(__name__)

PARALLEL = 4 # assuming a quad-core machine

def get_entity_relation(candidate):
    return tuple(([m.context.get_span() for m in candidate.get_mentions()]))


def get_unique_entity_relations(candidates):
    unique_entity_relation = set()
    for candidate in candidates:
        entity_relation = get_entity_relation(candidate)
        unique_entity_relation.add(entity_relation)
    return unique_entity_relation


class FonduerModel(mlflow.pyfunc.PythonModel):

    def __init__(self, conn_string):
        session = Meta.init(conn_string).Session()
        from fonduerconfig import matchers, mention_classes, mention_spaces, candidate_classes  # isort:skip

        self.corpus_parser = Parser(session, structural=True, lingual=True)
        self.mention_extractor = MentionExtractor(
            session,
            mention_classes, mention_spaces, matchers
        )
        self.candidate_extractor = CandidateExtractor(session, candidate_classes)

        self.featurizer = Featurizer(session, candidate_classes)
        with open('feature_keys.pkl', 'rb') as f:
            key_names = pickle.load(f)
        self.featurizer.drop_keys(key_names)
        self.featurizer.upsert_keys(key_names)

        disc_model = LogisticRegression()

        # Workaround to https://github.com/HazyResearch/fonduer/issues/208
        checkpoint = torch.load("./best_model.pt")
        disc_model.settings = checkpoint["config"]
        disc_model.cardinality = checkpoint["cardinality"]
        disc_model._build_model()

        disc_model.load(model_file="best_model.pt", save_dir="./")
        self.disc_model = disc_model

    def predict(self, context, model_input):
        for index, row in model_input.iterrows():
            self._process(row['filename'])

    def _process(self, filename):
        # Parse docs
        docs_path = filename
        doc_preprocessor = HTMLDocPreprocessor(docs_path)
        # clear=False otherwise gets stuck.
        self.corpus_parser.apply(doc_preprocessor, clear=False, parallelism=PARALLEL)
        test_docs = self.corpus_parser.get_last_documents()

        self.mention_extractor.apply(test_docs, clear=False, parallelism=PARALLEL)

        # Candidate
        self.candidate_extractor.apply(test_docs, split=2, clear=True, parallelism=PARALLEL)
        test_cands = self.candidate_extractor.get_candidates(split=2)

        # Featurization
        self.featurizer.apply(test_docs, clear=False)
        F_test = self.featurizer.get_feature_matrices(test_cands)

        test_score = self.disc_model.predict((test_cands[0], F_test[0]), b=0.6, pos_label=TRUE)
        true_preds = [test_cands[0][_] for _ in np.nditer(np.where(test_score == TRUE))]

        for entity_relation in get_unique_entity_relations(true_preds):
            print(entity_relation)


if __name__ == '__main__':
    DB = "pob_presidents"
    conn_string = 'postgresql://localhost:5432/' + DB
    model = FonduerModel(conn_string)

    filename = sys.argv[1]
    model_input = pd.DataFrame({'filename': [filename]})
    model.predict(None, model_input)
