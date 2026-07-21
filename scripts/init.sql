-- ─── Schema: PDF to EPUB converter ────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Tabela: books ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS books (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename        VARCHAR(500) NOT NULL,
    original_name   VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT,
    page_count      INTEGER,
    original_pdf    TEXT,           -- path/url no Supabase Storage
    full_epub       TEXT,           -- path/url do EPUB completo gerado
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
                    -- pending | processing | done | error
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Tabela: chapters ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chapters (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    book_id         UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    title           VARCHAR(1000) NOT NULL,
    chapter_number  INTEGER NOT NULL,
    start_page      INTEGER,
    end_page        INTEGER,
    epub_file       TEXT,           -- path/url do EPUB deste capítulo
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Tabela: conversions ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    book_id         UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    task_id         VARCHAR(255),   -- id de rastreio interno da conversão
    status          VARCHAR(50) NOT NULL DEFAULT 'queued',
                    -- queued | running | done | error
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    duration_ms     INTEGER,
    logs            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Tabela: users (login, cadastro, aprovação manual, LGPD) ────────────────
CREATE TABLE IF NOT EXISTS users (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name           VARCHAR(255) NOT NULL,
    email               VARCHAR(255) NOT NULL,
    password_hash       VARCHAR(255) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
                        -- pending | approved | revoked
    is_admin            BOOLEAN NOT NULL DEFAULT false,
    privacy_accepted_at TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at       TIMESTAMPTZ,
    -- Exclusão lógica: deleted_at marcado e email trocado por um valor
    -- anônimo (deleted_<uuid>@deleted.local); original_email guarda o
    -- valor real só pra auditoria. Libera o email original pra recadastro.
    deleted_at          TIMESTAMPTZ,
    original_email      VARCHAR(255)
);

-- ─── Tabela: user_app_access (permissão granular por app) ───────────────────
-- Só vale pra quem NÃO é admin — admin sempre tem acesso a tudo.
CREATE TABLE IF NOT EXISTS user_app_access (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app_key     VARCHAR(50) NOT NULL,
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, app_key)
);

-- ─── Índices ────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_books_status      ON books(status);
CREATE INDEX IF NOT EXISTS idx_books_created_at  ON books(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chapters_book_id  ON chapters(book_id);
CREATE INDEX IF NOT EXISTS idx_conversions_book  ON conversions(book_id);
CREATE INDEX IF NOT EXISTS idx_conversions_task  ON conversions(task_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(LOWER(email));
CREATE INDEX IF NOT EXISTS idx_users_deleted_at   ON users(deleted_at);
CREATE INDEX IF NOT EXISTS idx_user_app_access_user ON user_app_access(user_id);
CREATE INDEX IF NOT EXISTS idx_users_status       ON users(status);

-- ─── Trigger: atualiza updated_at automaticamente ───────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER books_updated_at
    BEFORE UPDATE ON books
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
