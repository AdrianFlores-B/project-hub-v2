-- The application schema written by hand, no ORM involved.
-- Mirrors exactly what the alembic migrations produce; the task asks for the
-- database to be creatable both with an ORM (app/models.py + alembic) and
-- without one (this file + create_db_no_orm.py).

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    login VARCHAR(50) NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX ix_users_login ON users (login);

CREATE TYPE member_role AS ENUM ('owner', 'participant');

CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    -- denormalized sum of the project's document sizes, kept fresh by the
    -- size-calculator lambda
    total_size_bytes BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE project_members (
    project_id INTEGER NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role member_role NOT NULL,
    PRIMARY KEY (project_id, user_id)
);

-- "list my projects" looks members up by user_id; the composite primary key
-- above only covers lookups that start with project_id
CREATE INDEX ix_project_members_user_id ON project_members (user_id);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    s3_key VARCHAR(500) NOT NULL UNIQUE,
    content_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_documents_project_id ON documents (project_id);
