from packages.narrative_compiler.adapters.ettin import EttinRerankerIdentityScorer
from packages.narrative_compiler.adapters.gliner2 import GLiNER25SemanticLexer
from packages.narrative_compiler.model_manifest import ETTIN_RERANKER_68M_V1, GLINER25_BASE_V1


def test_v30_challengers_use_exact_revisions_by_default():
    lexer = GLiNER25SemanticLexer(model=object())
    scorer = EttinRerankerIdentityScorer(model=object())
    assert lexer.descriptor.model_id == GLINER25_BASE_V1.model_id
    assert lexer.descriptor.revision == GLINER25_BASE_V1.revision
    assert scorer.descriptor.model_id == ETTIN_RERANKER_68M_V1.model_id
    assert scorer.descriptor.revision == ETTIN_RERANKER_68M_V1.revision
    assert len(lexer.descriptor.revision) == 40
    assert len(scorer.descriptor.revision) == 40
