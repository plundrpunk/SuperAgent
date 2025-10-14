"""
Unit tests for VectorClient module.

Tests embedding generation, similarity search, collection management,
test patterns, bug fixes, and HITL annotations storage/retrieval.

All tests use mocked vector DB to avoid external dependencies.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
import json
from agent_system.state.vector_client import (
    VectorClient,
    VectorConfig
)


class TestVectorConfig:
    """Test VectorConfig dataclass."""

    def test_default_config_values(self):
        """Verify default configuration values."""
        config = VectorConfig()
        assert config.persist_directory == './vector_db'
        assert config.collection_prefix == 'superagent'
        assert config.embedding_model == 'all-MiniLM-L6-v2'

    def test_custom_config_values(self):
        """Custom configuration values should be applied."""
        config = VectorConfig(
            persist_directory='/tmp/test_db',
            collection_prefix='test_prefix',
            embedding_model='custom-model'
        )
        assert config.persist_directory == '/tmp/test_db'
        assert config.collection_prefix == 'test_prefix'
        assert config.embedding_model == 'custom-model'

    def test_env_override_for_persist_directory(self):
        """Environment variable should override default persist directory."""
        import os
        original_value = os.environ.get('VECTOR_DB_PATH')
        try:
            os.environ['VECTOR_DB_PATH'] = '/custom/path'
            # Need to reimport to pick up the new env var
            from importlib import reload
            import agent_system.state.vector_client as vc_module
            reload(vc_module)
            config = vc_module.VectorConfig()
            assert config.persist_directory == '/custom/path'
        finally:
            # Restore original value
            if original_value is None:
                os.environ.pop('VECTOR_DB_PATH', None)
            else:
                os.environ['VECTOR_DB_PATH'] = original_value
            # Reload again to restore original state
            reload(vc_module)


class TestVectorClientInitialization:
    """Test VectorClient initialization."""

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_init_with_default_config(self, mock_transformer, mock_chroma):
        """Client should initialize with default config."""
        client = VectorClient()

        assert client.config is not None
        assert client.config.collection_prefix == 'superagent'

        # Verify ChromaDB client initialized
        mock_chroma.assert_called_once()

        # Verify embedder initialized
        mock_transformer.assert_called_once_with('all-MiniLM-L6-v2')

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_init_with_custom_config(self, mock_transformer, mock_chroma):
        """Client should initialize with custom config."""
        config = VectorConfig(
            persist_directory='/tmp/test',
            embedding_model='custom-model'
        )
        client = VectorClient(config)

        assert client.config == config
        mock_transformer.assert_called_once_with('custom-model')

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_collection_names_set_correctly(self, mock_transformer, mock_chroma):
        """Collection names should include prefix."""
        client = VectorClient()

        assert client.collections['test_success'] == 'superagent_test_success'
        assert client.collections['common_bugs'] == 'superagent_common_bugs'
        assert client.collections['hitl_annotations'] == 'superagent_hitl_annotations'


class TestEmbeddingGeneration:
    """Test embedding generation from text."""

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_generate_embedding_returns_list(self, mock_transformer, mock_chroma):
        """Embedding should be a list of floats."""
        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        embedding = client._generate_embedding("test text")

        assert isinstance(embedding, list)
        assert len(embedding) == 3
        assert embedding == [0.1, 0.2, 0.3]

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_generate_embedding_correct_dimensions(self, mock_transformer, mock_chroma):
        """Embedding should have expected dimensions (384 for all-MiniLM-L6-v2)."""
        mock_embedder = Mock()
        # all-MiniLM-L6-v2 produces 384-dimensional vectors
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.0] * 384
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        embedding = client._generate_embedding("test text")

        assert len(embedding) == 384

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_generate_embedding_with_empty_text(self, mock_transformer, mock_chroma):
        """Empty text should still generate an embedding."""
        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.0] * 384
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        embedding = client._generate_embedding("")

        assert isinstance(embedding, list)
        assert len(embedding) == 384

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_generate_embedding_with_special_characters(self, mock_transformer, mock_chroma):
        """Text with special characters should be handled."""
        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.1, 0.2]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        embedding = client._generate_embedding("test @#$% text 测试")

        assert isinstance(embedding, list)
        mock_embedder.encode.assert_called_once_with("test @#$% text 测试")


class TestCollectionManagement:
    """Test collection management operations."""

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_get_collection_creates_if_not_exists(self, mock_transformer, mock_chroma):
        """Should create collection if it doesn't exist."""
        mock_client = Mock()
        mock_collection = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        client = VectorClient()
        collection = client._get_collection('test_success')

        mock_client.get_or_create_collection.assert_called_once_with(
            name='superagent_test_success',
            metadata={'type': 'test_success'}
        )
        assert collection == mock_collection

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_get_collection_invalid_type_raises_error(self, mock_transformer, mock_chroma):
        """Invalid collection type should raise ValueError."""
        client = VectorClient()

        with pytest.raises(ValueError, match="Unknown collection type"):
            client._get_collection('invalid_type')

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_get_collection_all_types(self, mock_transformer, mock_chroma):
        """Should support all collection types."""
        mock_client = Mock()
        mock_chroma.return_value = mock_client

        client = VectorClient()
        collection_types = ['test_success', 'common_bugs', 'hitl_annotations']

        for col_type in collection_types:
            client._get_collection(col_type)

        assert mock_client.get_or_create_collection.call_count == 3

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_delete_collection_success(self, mock_transformer, mock_chroma):
        """Should successfully delete collection."""
        mock_client = Mock()
        mock_chroma.return_value = mock_client

        client = VectorClient()
        result = client.delete_collection('test_success')

        assert result is True
        mock_client.delete_collection.assert_called_once_with(
            name='superagent_test_success'
        )

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_delete_collection_invalid_type(self, mock_transformer, mock_chroma):
        """Invalid collection type should return False."""
        client = VectorClient()
        result = client.delete_collection('invalid_type')

        assert result is False

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_delete_collection_handles_exception(self, mock_transformer, mock_chroma):
        """Should handle exceptions during deletion."""
        mock_client = Mock()
        mock_client.delete_collection.side_effect = Exception("Delete failed")
        mock_chroma.return_value = mock_client

        client = VectorClient()
        result = client.delete_collection('test_success')

        assert result is False

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_get_collection_count_returns_count(self, mock_transformer, mock_chroma):
        """Should return correct document count."""
        mock_collection = Mock()
        mock_collection.count.return_value = 42
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        client = VectorClient()
        count = client.get_collection_count('test_success')

        assert count == 42

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_get_collection_count_handles_exception(self, mock_transformer, mock_chroma):
        """Should return 0 on exception."""
        mock_client = Mock()
        mock_client.get_or_create_collection.side_effect = Exception("Error")
        mock_chroma.return_value = mock_client

        client = VectorClient()
        count = client.get_collection_count('test_success')

        assert count == 0


class TestTestPatternStorage:
    """Test storing and retrieving test patterns."""

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_store_test_pattern_success(self, mock_transformer, mock_chroma):
        """Should successfully store test pattern."""
        mock_collection = Mock()
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        test_code = "test('login', async ({ page }) => { ... })"
        metadata = {'feature': 'login', 'complexity': 'hard'}

        result = client.store_test_pattern('test_123', test_code, metadata)

        assert result is True
        mock_collection.add.assert_called_once_with(
            ids=['test_123'],
            embeddings=[[0.1, 0.2, 0.3]],
            documents=[test_code],
            metadatas=[metadata]
        )

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_store_test_pattern_handles_exception(self, mock_transformer, mock_chroma):
        """Should handle exceptions during storage."""
        mock_collection = Mock()
        mock_collection.add.side_effect = Exception("Storage failed")
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.1]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        result = client.store_test_pattern('test_123', 'code', {})

        assert result is False

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_search_test_patterns_returns_matches(self, mock_transformer, mock_chroma):
        """Should return matching test patterns."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [['test_1', 'test_2']],
            'documents': [['code1', 'code2']],
            'metadatas': [[{'feature': 'login'}, {'feature': 'signup'}]],
            'distances': [[0.1, 0.3]]
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5, 0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_test_patterns('login test', n_results=2)

        assert len(results) == 2
        assert results[0]['id'] == 'test_1'
        assert results[0]['code'] == 'code1'
        assert results[0]['metadata']['feature'] == 'login'
        assert results[0]['similarity'] == 0.9  # 1 - 0.1

        assert results[1]['id'] == 'test_2'
        assert results[1]['similarity'] == 0.7  # 1 - 0.3

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_search_test_patterns_empty_results(self, mock_transformer, mock_chroma):
        """Should handle empty search results."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [[]],
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_test_patterns('nonexistent')

        assert results == []

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_search_test_patterns_with_high_similarity(self, mock_transformer, mock_chroma):
        """Should find patterns with high similarity score (0.9+)."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [['test_exact']],
            'documents': [['exact_match_code']],
            'metadatas': [[{'feature': 'exact'}]],
            'distances': [[0.05]]  # Very close = high similarity
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_test_patterns('exact test')

        assert len(results) == 1
        assert results[0]['similarity'] == 0.95  # 1 - 0.05


class TestBugFixStorage:
    """Test storing and retrieving bug fixes."""

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_store_bug_fix_success(self, mock_transformer, mock_chroma):
        """Should successfully store bug fix."""
        mock_collection = Mock()
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.1, 0.2]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        error_msg = "TypeError: Cannot read property 'click' of null"
        fix_code = "await page.waitForSelector(selector)"
        metadata = {'root_cause': 'element_not_ready', 'strategy': 'wait_for_selector'}

        result = client.store_bug_fix('fix_123', error_msg, fix_code, metadata)

        assert result is True
        expected_doc = f"ERROR: {error_msg}\nFIX: {fix_code}"
        mock_collection.add.assert_called_once_with(
            ids=['fix_123'],
            embeddings=[[0.1, 0.2]],
            documents=[expected_doc],
            metadatas=[metadata]
        )

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_store_bug_fix_handles_exception(self, mock_transformer, mock_chroma):
        """Should handle exceptions during bug fix storage."""
        mock_collection = Mock()
        mock_collection.add.side_effect = Exception("Storage failed")
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.1]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        result = client.store_bug_fix('fix_123', 'error', 'fix', {})

        assert result is False

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_search_bug_fixes_returns_matches(self, mock_transformer, mock_chroma):
        """Should return matching bug fixes."""
        error1 = "TypeError: Cannot read property 'click'"
        fix1 = "await page.waitForSelector()"
        doc1 = f"ERROR: {error1}\nFIX: {fix1}"

        error2 = "Element not found"
        fix2 = "Use data-testid selector"
        doc2 = f"ERROR: {error2}\nFIX: {fix2}"

        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [['fix_1', 'fix_2']],
            'documents': [[doc1, doc2]],
            'metadatas': [[
                {'root_cause': 'timing'},
                {'root_cause': 'selector'}
            ]],
            'distances': [[0.2, 0.4]]
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_bug_fixes("TypeError: Cannot read property", n_results=2)

        assert len(results) == 2
        assert results[0]['id'] == 'fix_1'
        assert results[0]['error'] == error1
        assert results[0]['fix'] == fix1
        assert results[0]['similarity'] == 0.8  # 1 - 0.2

        assert results[1]['id'] == 'fix_2'
        assert results[1]['error'] == error2
        assert results[1]['fix'] == fix2

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_search_bug_fixes_empty_results(self, mock_transformer, mock_chroma):
        """Should handle empty bug fix search results."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [[]],
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_bug_fixes('unknown error')

        assert results == []

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_search_bug_fixes_with_threshold_filtering(self, mock_transformer, mock_chroma):
        """Should support filtering by similarity threshold."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [['fix_high', 'fix_medium', 'fix_low']],
            'documents': [['ERROR: e1\nFIX: f1', 'ERROR: e2\nFIX: f2', 'ERROR: e3\nFIX: f3']],
            'metadatas': [[{}, {}, {}]],
            'distances': [[0.1, 0.3, 0.6]]  # similarities: 0.9, 0.7, 0.4
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_bug_fixes('error', n_results=3)

        # All results returned
        assert len(results) == 3

        # Manual filtering for similarity >= 0.7
        high_similarity = [r for r in results if r['similarity'] >= 0.7]
        assert len(high_similarity) == 2
        assert high_similarity[0]['similarity'] == 0.9
        assert high_similarity[1]['similarity'] == 0.7


class TestHITLAnnotationStorage:
    """Test storing and retrieving HITL annotations."""

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_store_hitl_annotation_success(self, mock_transformer, mock_chroma):
        """Should successfully store HITL annotation."""
        mock_collection = Mock()
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.1, 0.2]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        task_desc = "Fix login test failure"
        annotation = {
            'root_cause': 'selector_changed',
            'fix_strategy': 'update_selector',
            'notes': 'Button ID changed to data-testid',
            'patch_diff': '- page.click("#login")\n+ page.click("[data-testid=login]")'
        }

        result = client.store_hitl_annotation('ann_123', task_desc, annotation)

        assert result is True
        mock_collection.add.assert_called_once()
        call_args = mock_collection.add.call_args
        assert call_args[1]['ids'] == ['ann_123']
        assert call_args[1]['embeddings'] == [[0.1, 0.2]]

        # Verify document is JSON-serialized annotation
        stored_doc = call_args[1]['documents'][0]
        assert json.loads(stored_doc) == annotation

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_store_hitl_annotation_handles_exception(self, mock_transformer, mock_chroma):
        """Should handle exceptions during annotation storage."""
        mock_collection = Mock()
        mock_collection.add.side_effect = Exception("Storage failed")
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.1]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        result = client.store_hitl_annotation('ann_123', 'task', {})

        assert result is False

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_search_hitl_annotations_returns_matches(self, mock_transformer, mock_chroma):
        """Should return matching HITL annotations."""
        annotation1 = {'root_cause': 'selector', 'fix': 'use_data_testid'}
        annotation2 = {'root_cause': 'timing', 'fix': 'add_wait'}

        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [['ann_1', 'ann_2']],
            'documents': [[json.dumps(annotation1), json.dumps(annotation2)]],
            'metadatas': [[
                {'task_description': 'Fix selector issue'},
                {'task_description': 'Fix timing issue'}
            ]],
            'distances': [[0.15, 0.35]]
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_hitl_annotations('selector problem', n_results=2)

        assert len(results) == 2
        assert results[0]['id'] == 'ann_1'
        assert results[0]['annotation'] == annotation1
        assert results[0]['similarity'] == 0.85  # 1 - 0.15

        assert results[1]['id'] == 'ann_2'
        assert results[1]['annotation'] == annotation2
        assert results[1]['similarity'] == 0.65

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_search_hitl_annotations_handles_json_error(self, mock_transformer, mock_chroma):
        """Should skip annotations with invalid JSON."""
        annotation1 = {'root_cause': 'valid'}

        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [['ann_1', 'ann_2', 'ann_3']],
            'documents': [[json.dumps(annotation1), 'invalid json', json.dumps(annotation1)]],
            'metadatas': [[
                {'task_description': 'Valid 1'},
                {'task_description': 'Invalid'},
                {'task_description': 'Valid 2'}
            ]],
            'distances': [[0.1, 0.2, 0.3]]
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_hitl_annotations('query')

        # Should only return valid entries
        assert len(results) == 2
        assert results[0]['id'] == 'ann_1'
        assert results[1]['id'] == 'ann_3'

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_search_hitl_annotations_empty_results(self, mock_transformer, mock_chroma):
        """Should handle empty annotation search results."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [[]],
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_hitl_annotations('unknown task')

        assert results == []


class TestSimilarityThresholds:
    """Test similarity search with different threshold values."""

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_high_similarity_threshold_0_9(self, mock_transformer, mock_chroma):
        """Test filtering results with 0.9 similarity threshold."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [['id1', 'id2', 'id3']],
            'documents': [['doc1', 'doc2', 'doc3']],
            'metadatas': [[{}, {}, {}]],
            'distances': [[0.05, 0.15, 0.5]]  # similarities: 0.95, 0.85, 0.5
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_test_patterns('query')

        # Filter for 0.9+ similarity
        high_sim = [r for r in results if r['similarity'] >= 0.9]
        assert len(high_sim) == 1
        assert high_sim[0]['similarity'] == 0.95

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_medium_similarity_threshold_0_8(self, mock_transformer, mock_chroma):
        """Test filtering results with 0.8 similarity threshold."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [['id1', 'id2', 'id3']],
            'documents': [['doc1', 'doc2', 'doc3']],
            'metadatas': [[{}, {}, {}]],
            'distances': [[0.05, 0.15, 0.5]]  # similarities: 0.95, 0.85, 0.5
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_test_patterns('query')

        # Filter for 0.8+ similarity
        medium_sim = [r for r in results if r['similarity'] >= 0.8]
        assert len(medium_sim) == 2
        assert all(r['similarity'] >= 0.8 for r in medium_sim)

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_low_similarity_threshold_0_7(self, mock_transformer, mock_chroma):
        """Test filtering results with 0.7 similarity threshold."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [['id1', 'id2', 'id3', 'id4']],
            'documents': [['doc1', 'doc2', 'doc3', 'doc4']],
            'metadatas': [[{}, {}, {}, {}]],
            'distances': [[0.05, 0.25, 0.35, 0.6]]  # similarities: 0.95, 0.75, 0.65, 0.4
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_test_patterns('query')

        # Filter for 0.7+ similarity
        low_sim = [r for r in results if r['similarity'] >= 0.7]
        assert len(low_sim) == 2


class TestConnectionFailures:
    """Test error handling for connection failures."""

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_chroma_connection_failure_on_init(self, mock_transformer, mock_chroma):
        """Should raise exception if ChromaDB connection fails."""
        mock_chroma.side_effect = Exception("Connection refused")

        with pytest.raises(Exception, match="Connection refused"):
            VectorClient()

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_embedder_loading_failure(self, mock_transformer, mock_chroma):
        """Should raise exception if embedding model fails to load."""
        mock_transformer.side_effect = Exception("Model not found")

        with pytest.raises(Exception, match="Model not found"):
            VectorClient()

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_query_connection_timeout(self, mock_transformer, mock_chroma):
        """Should handle connection timeout during query."""
        mock_collection = Mock()
        mock_collection.query.side_effect = Exception("Connection timeout")
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()

        with pytest.raises(Exception, match="Connection timeout"):
            client.search_test_patterns('query')


class TestMetadataFiltering:
    """Test metadata-based filtering in searches."""

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_search_returns_metadata(self, mock_transformer, mock_chroma):
        """Search results should include full metadata."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [['test_1']],
            'documents': [['code']],
            'metadatas': [[{
                'feature': 'login',
                'complexity': 'hard',
                'author': 'scribe',
                'tags': ['auth', 'critical']
            }]],
            'distances': [[0.1]]
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        results = client.search_test_patterns('query')

        assert len(results) == 1
        metadata = results[0]['metadata']
        assert metadata['feature'] == 'login'
        assert metadata['complexity'] == 'hard'
        assert metadata['author'] == 'scribe'
        assert metadata['tags'] == ['auth', 'critical']


class TestRetrievalWorkflows:
    """Test complete retrieval workflows."""

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_workflow_store_and_retrieve_test_pattern(self, mock_transformer, mock_chroma):
        """Test complete workflow: store then retrieve test pattern."""
        # Setup mocks
        mock_collection = Mock()
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.1, 0.2, 0.3]
        mock_transformer.return_value = mock_embedder

        # Store pattern
        client = VectorClient()
        test_code = "test('checkout', async ({ page }) => { ... })"
        metadata = {'feature': 'checkout', 'complexity': 'hard'}

        store_result = client.store_test_pattern('test_456', test_code, metadata)
        assert store_result is True

        # Mock retrieval
        mock_collection.query.return_value = {
            'ids': [['test_456']],
            'documents': [[test_code]],
            'metadatas': [[metadata]],
            'distances': [[0.05]]
        }

        # Retrieve pattern
        search_results = client.search_test_patterns('checkout test')
        assert len(search_results) == 1
        assert search_results[0]['code'] == test_code
        assert search_results[0]['metadata'] == metadata

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_workflow_store_and_retrieve_bug_fix(self, mock_transformer, mock_chroma):
        """Test complete workflow: store then retrieve bug fix."""
        mock_collection = Mock()
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        # Store bug fix
        client = VectorClient()
        error = "Timeout: waiting for selector"
        fix = "Increase timeout to 30s"
        metadata = {'strategy': 'increase_timeout'}

        store_result = client.store_bug_fix('fix_789', error, fix, metadata)
        assert store_result is True

        # Mock retrieval
        doc = f"ERROR: {error}\nFIX: {fix}"
        mock_collection.query.return_value = {
            'ids': [['fix_789']],
            'documents': [[doc]],
            'metadatas': [[metadata]],
            'distances': [[0.1]]
        }

        # Retrieve bug fix
        search_results = client.search_bug_fixes('Timeout waiting')
        assert len(search_results) == 1
        assert search_results[0]['error'] == error
        assert search_results[0]['fix'] == fix

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_workflow_multiple_collections(self, mock_transformer, mock_chroma):
        """Test working with multiple collections."""
        mock_collections = {}

        def get_or_create(name, metadata):
            if name not in mock_collections:
                mock_collections[name] = Mock()
            return mock_collections[name]

        mock_client = Mock()
        mock_client.get_or_create_collection.side_effect = get_or_create
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()

        # Access different collections
        client.store_test_pattern('test_1', 'code', {})
        client.store_bug_fix('fix_1', 'error', 'fix', {})
        client.store_hitl_annotation('ann_1', 'task', {})

        # Verify three different collections were accessed
        assert len(mock_collections) == 3
        assert 'superagent_test_success' in mock_collections
        assert 'superagent_common_bugs' in mock_collections
        assert 'superagent_hitl_annotations' in mock_collections


class TestEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions."""

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_very_long_document(self, mock_transformer, mock_chroma):
        """Should handle very long documents."""
        mock_collection = Mock()
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        long_code = "test code " * 10000  # Very long

        result = client.store_test_pattern('test_long', long_code, {})
        assert result is True

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_unicode_and_special_chars_in_documents(self, mock_transformer, mock_chroma):
        """Should handle unicode and special characters."""
        mock_collection = Mock()
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()
        special_code = "test('测试 🚀 @#$%', async ({ page }) => {})"

        result = client.store_test_pattern('test_unicode', special_code, {})
        assert result is True

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_n_results_boundary(self, mock_transformer, mock_chroma):
        """Test boundary conditions for n_results parameter."""
        mock_collection = Mock()
        mock_collection.query.return_value = {
            'ids': [['id1']],
            'documents': [['doc1']],
            'metadatas': [[{}]],
            'distances': [[0.1]]
        }
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()

        # Test with different n_results values
        client.search_test_patterns('query', n_results=1)
        client.search_test_patterns('query', n_results=10)
        client.search_test_patterns('query', n_results=100)

        assert mock_collection.query.call_count == 3

    @patch('agent_system.state.vector_client.chromadb.PersistentClient')
    @patch('agent_system.state.vector_client.SentenceTransformer')
    def test_empty_metadata(self, mock_transformer, mock_chroma):
        """Should handle empty metadata."""
        mock_collection = Mock()
        mock_client = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        mock_embedder = Mock()
        mock_embedder.encode.return_value = Mock()
        mock_embedder.encode.return_value.tolist.return_value = [0.5]
        mock_transformer.return_value = mock_embedder

        client = VectorClient()

        # Store with empty metadata
        result = client.store_test_pattern('test_1', 'code', {})
        assert result is True

        call_args = mock_collection.add.call_args
        assert call_args[1]['metadatas'] == [{}]
