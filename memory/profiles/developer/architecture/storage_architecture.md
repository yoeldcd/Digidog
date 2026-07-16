# Archeitectural distribution patterns for Storage Structures

/{data_stores, e.g. database_stores}
├── /{relational_stores, e.g. relational}
│   ├── /{primary_database_repository, e.g. primary_databases}
│   │   └── (file struct e.g: data_stores/relational/primary_databases/...)
│   │       └── - [store_name]_relational_store.sqlite # MUST: store local relational database records for data persistency. MUST NOT: contain execution logic, run migrations automatically, or store raw upload streams.
│   │           - `[StoreName]RelationalStore` (Tables): database tables for relational transactions
│   └── /{transaction_log_repository, e.g. transaction_logs}
│       └── (file struct e.g: data_stores/relational/transaction_logs/...)
│           └── - [store_name]_transaction_journal.txnlog # MUST: store Append-Only transaction logging entries. MUST NOT: execute query projections or contain config parameters.
│               - `[StoreName]TransactionJournal` (Journal): journal logs for recording transactions
│
├── /{vector_stores, e.g. vector}
│   └── /{similarity_index_repository, e.g. similarity_indexes}
│       └── (file struct e.g: data_stores/vector/similarity_indexes/...)
│           └── - [index_name]_similarity_index.faiss # MUST: store vectors and embedding configurations for similarity retrievals. MUST NOT: contain plain text document fields or relational user profiles.
│               - `[IndexName]SimilarityIndex` (Index): vector index for storing spatial embeddings
│
└── /{document_stores, e.g. documents}
    ├── /{json_collection_repository, e.g. collections}
    │   └── (file struct e.g: data_stores/documents/collections/...)
    │       └── - [collection_name]_document_collection.jsonl # MUST: store JSON-LD or serialized document records. MUST NOT: run indexing queries by itself or contain encryption keys.
    │           - `[CollectionName]DocumentCollection` (Schema): document schema for records storage
    └── /{configuration_document_repository, e.g. configurations}
        └── (file struct e.g: data_stores/documents/configurations/...)
            └── - [config_name]_resolved_config.json # MUST: store resolved static local settings. MUST NOT: contain raw unredacted credentials or run runtime operations.
                - `[ConfigName]ResolvedConfig` (Schema): document schema for static configuration values
