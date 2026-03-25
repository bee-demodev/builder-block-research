PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  source_type TEXT NOT NULL,
  title TEXT NOT NULL,
  canonical_url TEXT NOT NULL UNIQUE,
  author TEXT,
  published_at TEXT,
  topic_hint TEXT,
  summary TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  artifact_type TEXT NOT NULL,
  path TEXT NOT NULL,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
  UNIQUE(source_id, artifact_type, path)
);

CREATE TABLE IF NOT EXISTS concepts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  description TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS frameworks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  framework_type TEXT NOT NULL,
  style_family TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  description TEXT NOT NULL,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_topics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  topic_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'planned',
  description TEXT NOT NULL,
  rulebook_path TEXT,
  examples_path TEXT,
  open_questions_path TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_topic_aliases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL,
  alias TEXT NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES research_topics(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS topic_dependencies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL,
  dependency_topic_id INTEGER NOT NULL,
  dependency_kind TEXT NOT NULL,
  rationale TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
  FOREIGN KEY (dependency_topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
  CHECK(topic_id <> dependency_topic_id),
  UNIQUE(topic_id, dependency_topic_id, dependency_kind)
);

CREATE TABLE IF NOT EXISTS trade_models (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  model_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  description TEXT NOT NULL,
  source_notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trade_model_aliases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_model_id INTEGER NOT NULL,
  alias TEXT NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (trade_model_id) REFERENCES trade_models(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trade_model_topics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_model_id INTEGER NOT NULL,
  topic_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 2,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (trade_model_id) REFERENCES trade_models(id) ON DELETE CASCADE,
  FOREIGN KEY (topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
  UNIQUE(trade_model_id, topic_id, role)
);

CREATE TABLE IF NOT EXISTS trade_model_topic_requirements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_model_id INTEGER NOT NULL,
  topic_id INTEGER NOT NULL,
  introduced_by_topic_id INTEGER NOT NULL,
  requirement_type TEXT NOT NULL,
  relation_role TEXT,
  dependency_depth INTEGER NOT NULL DEFAULT 0,
  dependency_path TEXT NOT NULL,
  dependency_chain TEXT,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (trade_model_id) REFERENCES trade_models(id) ON DELETE CASCADE,
  FOREIGN KEY (topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
  FOREIGN KEY (introduced_by_topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
  UNIQUE(trade_model_id, topic_id, introduced_by_topic_id, requirement_type)
);

CREATE TABLE IF NOT EXISTS framework_topic_terms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  framework_id INTEGER NOT NULL,
  topic_id INTEGER NOT NULL,
  term TEXT NOT NULL,
  term_kind TEXT NOT NULL DEFAULT 'native',
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (framework_id) REFERENCES frameworks(id) ON DELETE CASCADE,
  FOREIGN KEY (topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
  UNIQUE(framework_id, topic_id, term)
);

CREATE TABLE IF NOT EXISTS framework_trade_model_terms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  framework_id INTEGER NOT NULL,
  trade_model_id INTEGER NOT NULL,
  term TEXT NOT NULL,
  term_kind TEXT NOT NULL DEFAULT 'native',
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (framework_id) REFERENCES frameworks(id) ON DELETE CASCADE,
  FOREIGN KEY (trade_model_id) REFERENCES trade_models(id) ON DELETE CASCADE,
  UNIQUE(framework_id, trade_model_id, term)
);

CREATE TABLE IF NOT EXISTS source_topics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  topic_id INTEGER NOT NULL,
  relation_type TEXT NOT NULL DEFAULT 'primary_hint',
  confidence REAL NOT NULL DEFAULT 1.0,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
  FOREIGN KEY (topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
  UNIQUE(source_id, topic_id, relation_type)
);

CREATE TABLE IF NOT EXISTS source_frameworks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  framework_id INTEGER NOT NULL,
  relation_type TEXT NOT NULL DEFAULT 'primary',
  confidence REAL NOT NULL DEFAULT 1.0,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
  FOREIGN KEY (framework_id) REFERENCES frameworks(id) ON DELETE CASCADE,
  UNIQUE(source_id, framework_id, relation_type)
);

CREATE TABLE IF NOT EXISTS source_trade_models (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  trade_model_id INTEGER NOT NULL,
  relation_type TEXT NOT NULL DEFAULT 'primary_hint',
  confidence REAL NOT NULL DEFAULT 1.0,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
  FOREIGN KEY (trade_model_id) REFERENCES trade_models(id) ON DELETE CASCADE,
  UNIQUE(source_id, trade_model_id, relation_type)
);

CREATE TABLE IF NOT EXISTS claims (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  concept_id INTEGER,
  source_id INTEGER NOT NULL,
  claim_key TEXT NOT NULL UNIQUE,
  claim_text TEXT NOT NULL,
  claim_type TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0.5,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE SET NULL,
  FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_slug TEXT NOT NULL,
  rule_key TEXT NOT NULL UNIQUE,
  rule_name TEXT NOT NULL,
  rule_json TEXT NOT NULL,
  determinism_score REAL DEFAULT 0.0,
  pine_translatability_score REAL DEFAULT 0.0,
  ambiguity_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rule_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rule_id INTEGER NOT NULL,
  source_id INTEGER NOT NULL,
  claim_id INTEGER,
  evidence_ref TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (rule_id) REFERENCES rules(id) ON DELETE CASCADE,
  FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
  FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS chart_markup_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_slug TEXT NOT NULL,
  source_id INTEGER,
  attempt_ref TEXT NOT NULL,
  environment TEXT NOT NULL,
  objective TEXT NOT NULL,
  result TEXT NOT NULL,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL,
  UNIQUE(topic_slug, attempt_ref)
);

CREATE TABLE IF NOT EXISTS trader_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  profile_type TEXT NOT NULL DEFAULT 'trader',
  status TEXT NOT NULL DEFAULT 'active',
  notes TEXT,
  style_json TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trader_profile_frameworks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trader_profile_id INTEGER NOT NULL,
  framework_id INTEGER NOT NULL,
  relation_type TEXT NOT NULL DEFAULT 'primary_framework',
  confidence REAL NOT NULL DEFAULT 1.0,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (trader_profile_id) REFERENCES trader_profiles(id) ON DELETE CASCADE,
  FOREIGN KEY (framework_id) REFERENCES frameworks(id) ON DELETE CASCADE,
  UNIQUE(trader_profile_id, framework_id, relation_type)
);

CREATE TABLE IF NOT EXISTS trader_profile_trade_models (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trader_profile_id INTEGER NOT NULL,
  trade_model_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 2,
  indicator_ready INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (trader_profile_id) REFERENCES trader_profiles(id) ON DELETE CASCADE,
  FOREIGN KEY (trade_model_id) REFERENCES trade_models(id) ON DELETE CASCADE,
  UNIQUE(trader_profile_id, trade_model_id, role)
);

CREATE TABLE IF NOT EXISTS trader_profile_topics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trader_profile_id INTEGER NOT NULL,
  topic_id INTEGER NOT NULL,
  emphasis TEXT NOT NULL DEFAULT 'core',
  priority INTEGER NOT NULL DEFAULT 2,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (trader_profile_id) REFERENCES trader_profiles(id) ON DELETE CASCADE,
  FOREIGN KEY (topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
  UNIQUE(trader_profile_id, topic_id, emphasis)
);

CREATE TABLE IF NOT EXISTS trader_annotations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trader_profile_id INTEGER NOT NULL,
  topic_slug TEXT NOT NULL,
  source_id INTEGER,
  case_ref TEXT NOT NULL UNIQUE,
  symbol TEXT,
  timeframe TEXT,
  chart_context_json TEXT NOT NULL,
  annotation_json TEXT NOT NULL,
  outcome_json TEXT,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (trader_profile_id) REFERENCES trader_profiles(id) ON DELETE CASCADE,
  FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS trader_annotation_trade_models (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trader_annotation_id INTEGER NOT NULL,
  trade_model_id INTEGER NOT NULL,
  relation_type TEXT NOT NULL DEFAULT 'primary_execution_model',
  confidence REAL NOT NULL DEFAULT 1.0,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (trader_annotation_id) REFERENCES trader_annotations(id) ON DELETE CASCADE,
  FOREIGN KEY (trade_model_id) REFERENCES trade_models(id) ON DELETE CASCADE,
  UNIQUE(trader_annotation_id, trade_model_id, relation_type)
);

CREATE TABLE IF NOT EXISTS indicator_specs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_slug TEXT NOT NULL,
  spec_key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  target_language TEXT NOT NULL DEFAULT 'pine',
  status TEXT NOT NULL DEFAULT 'draft',
  spec_json TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  topic_slug TEXT NOT NULL,
  grounding_score REAL NOT NULL,
  determinism_score REAL NOT NULL,
  visual_verification_score REAL NOT NULL,
  pine_translatability_score REAL NOT NULL,
  contradiction_penalty INTEGER NOT NULL,
  weighted_score REAL NOT NULL,
  status TEXT NOT NULL,
  description TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_claims_source ON claims(source_id);
CREATE INDEX IF NOT EXISTS idx_claims_concept ON claims(concept_id);
CREATE INDEX IF NOT EXISTS idx_frameworks_status ON frameworks(status);
CREATE INDEX IF NOT EXISTS idx_research_topics_status ON research_topics(status);
CREATE INDEX IF NOT EXISTS idx_research_topic_aliases_topic ON research_topic_aliases(topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_dependencies_topic ON topic_dependencies(topic_id);
CREATE INDEX IF NOT EXISTS idx_trade_model_aliases_model ON trade_model_aliases(trade_model_id);
CREATE INDEX IF NOT EXISTS idx_trade_model_topics_model ON trade_model_topics(trade_model_id);
CREATE INDEX IF NOT EXISTS idx_trade_model_topic_requirements_model ON trade_model_topic_requirements(trade_model_id);
CREATE INDEX IF NOT EXISTS idx_trade_model_topic_requirements_topic ON trade_model_topic_requirements(topic_id);
CREATE INDEX IF NOT EXISTS idx_framework_topic_terms_framework ON framework_topic_terms(framework_id);
CREATE INDEX IF NOT EXISTS idx_framework_topic_terms_topic ON framework_topic_terms(topic_id);
CREATE INDEX IF NOT EXISTS idx_framework_trade_model_terms_framework ON framework_trade_model_terms(framework_id);
CREATE INDEX IF NOT EXISTS idx_framework_trade_model_terms_model ON framework_trade_model_terms(trade_model_id);
CREATE INDEX IF NOT EXISTS idx_rules_topic ON rules(topic_slug);
CREATE INDEX IF NOT EXISTS idx_research_runs_topic ON research_runs(topic_slug);
CREATE INDEX IF NOT EXISTS idx_source_frameworks_source ON source_frameworks(source_id);
CREATE INDEX IF NOT EXISTS idx_source_frameworks_framework ON source_frameworks(framework_id);
CREATE INDEX IF NOT EXISTS idx_source_topics_source ON source_topics(source_id);
CREATE INDEX IF NOT EXISTS idx_source_topics_topic ON source_topics(topic_id);
CREATE INDEX IF NOT EXISTS idx_source_trade_models_source ON source_trade_models(source_id);
CREATE INDEX IF NOT EXISTS idx_source_trade_models_model ON source_trade_models(trade_model_id);
CREATE INDEX IF NOT EXISTS idx_trader_profiles_status ON trader_profiles(status);
CREATE INDEX IF NOT EXISTS idx_trader_profile_frameworks_profile ON trader_profile_frameworks(trader_profile_id);
CREATE INDEX IF NOT EXISTS idx_trader_profile_frameworks_framework ON trader_profile_frameworks(framework_id);
CREATE INDEX IF NOT EXISTS idx_trader_profile_trade_models_profile ON trader_profile_trade_models(trader_profile_id);
CREATE INDEX IF NOT EXISTS idx_trader_profile_trade_models_model ON trader_profile_trade_models(trade_model_id);
CREATE INDEX IF NOT EXISTS idx_trader_profile_topics_profile ON trader_profile_topics(trader_profile_id);
CREATE INDEX IF NOT EXISTS idx_trader_profile_topics_topic ON trader_profile_topics(topic_id);
CREATE INDEX IF NOT EXISTS idx_trader_annotations_topic ON trader_annotations(topic_slug);
CREATE INDEX IF NOT EXISTS idx_trader_annotations_profile ON trader_annotations(trader_profile_id);
CREATE INDEX IF NOT EXISTS idx_trader_annotation_trade_models_annotation ON trader_annotation_trade_models(trader_annotation_id);
CREATE INDEX IF NOT EXISTS idx_trader_annotation_trade_models_model ON trader_annotation_trade_models(trade_model_id);
