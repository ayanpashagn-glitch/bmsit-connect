BEGIN;

CREATE TABLE bc_alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT bc_alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> e887dc2f39f3

CREATE TABLE bc_clubs (
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(80) NOT NULL,
    active BOOLEAN NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (name)
);

CREATE TABLE bc_users (
    email VARCHAR(254) NOT NULL,
    usn VARCHAR(32) NOT NULL,
    name VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    approved BOOLEAN NOT NULL,
    active BOOLEAN NOT NULL,
    admin BOOLEAN NOT NULL,
    branch VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    skills VARCHAR(500) NOT NULL,
    bio TEXT NOT NULL,
    github VARCHAR(500),
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (email),
    UNIQUE (usn)
);

CREATE TABLE bc_announcements (
    club_id VARCHAR(36) NOT NULL,
    title VARCHAR(100) NOT NULL,
    body TEXT NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(club_id) REFERENCES bc_clubs (id)
);

CREATE INDEX ix_bc_announcements_club_id ON bc_announcements (club_id);

CREATE TABLE bc_audit (
    actor_id VARCHAR(36) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource_id VARCHAR(36) NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(actor_id) REFERENCES bc_users (id)
);

CREATE INDEX ix_bc_audit_actor_id ON bc_audit (actor_id);

CREATE TABLE bc_events (
    club_id VARCHAR(36) NOT NULL,
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    kind VARCHAR(80) NOT NULL,
    starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
    venue VARCHAR(200) NOT NULL,
    capacity INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CHECK (status IN ('pending','approved','hidden')),
    CHECK (capacity > 0),
    FOREIGN KEY(club_id) REFERENCES bc_clubs (id)
);

CREATE INDEX ix_bc_events_club_id ON bc_events (club_id);

CREATE TABLE bc_memberships (
    club_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CHECK (role IN ('member','coordinator')),
    FOREIGN KEY(club_id) REFERENCES bc_clubs (id),
    FOREIGN KEY(user_id) REFERENCES bc_users (id),
    UNIQUE (club_id, user_id)
);

CREATE INDEX ix_bc_memberships_club_id ON bc_memberships (club_id);

CREATE INDEX ix_bc_memberships_user_id ON bc_memberships (user_id);

CREATE TABLE bc_notifications (
    user_id VARCHAR(36) NOT NULL,
    message TEXT NOT NULL,
    resource_id VARCHAR(36) NOT NULL,
    read BOOLEAN NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES bc_users (id)
);

CREATE INDEX ix_bc_notifications_user_id ON bc_notifications (user_id);

CREATE TABLE bc_projects (
    owner_id VARCHAR(36) NOT NULL,
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    skills VARCHAR(500) NOT NULL,
    link VARCHAR(500),
    visible BOOLEAN NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(owner_id) REFERENCES bc_users (id)
);

CREATE INDEX ix_bc_projects_owner_id ON bc_projects (owner_id);

CREATE TABLE bc_recruitments (
    club_id VARCHAR(36) NOT NULL,
    title VARCHAR(100) NOT NULL,
    role VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    deadline TIMESTAMP WITH TIME ZONE NOT NULL,
    open BOOLEAN NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(club_id) REFERENCES bc_clubs (id)
);

CREATE INDEX ix_bc_recruitments_club_id ON bc_recruitments (club_id);

CREATE TABLE bc_sessions (
    token_hash VARCHAR(64) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (token_hash),
    FOREIGN KEY(user_id) REFERENCES bc_users (id)
);

CREATE INDEX ix_bc_sessions_user_id ON bc_sessions (user_id);

CREATE TABLE bc_teams (
    owner_id VARCHAR(36) NOT NULL,
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    skills VARCHAR(500) NOT NULL,
    commitment VARCHAR(200) NOT NULL,
    open BOOLEAN NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(owner_id) REFERENCES bc_users (id)
);

CREATE INDEX ix_bc_teams_owner_id ON bc_teams (owner_id);

CREATE TABLE bc_applications (
    recruitment_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,
    private_notes TEXT NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CHECK (status IN ('submitted','shortlisted','interview','selected','rejected','withdrawn')),
    FOREIGN KEY(recruitment_id) REFERENCES bc_recruitments (id),
    FOREIGN KEY(user_id) REFERENCES bc_users (id),
    UNIQUE (recruitment_id, user_id)
);

CREATE INDEX ix_bc_applications_recruitment_id ON bc_applications (recruitment_id);

CREATE INDEX ix_bc_applications_user_id ON bc_applications (user_id);

CREATE TABLE bc_registrations (
    event_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(event_id) REFERENCES bc_events (id),
    FOREIGN KEY(user_id) REFERENCES bc_users (id),
    UNIQUE (event_id, user_id)
);

CREATE INDEX ix_bc_registrations_event_id ON bc_registrations (event_id);

CREATE INDEX ix_bc_registrations_user_id ON bc_registrations (user_id);

CREATE TABLE bc_team_members (
    team_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(team_id) REFERENCES bc_teams (id),
    FOREIGN KEY(user_id) REFERENCES bc_users (id),
    UNIQUE (team_id, user_id)
);

CREATE INDEX ix_bc_team_members_team_id ON bc_team_members (team_id);

CREATE INDEX ix_bc_team_members_user_id ON bc_team_members (user_id);

CREATE TABLE bc_team_requests (
    team_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CHECK (status IN ('pending','accepted','declined')),
    FOREIGN KEY(team_id) REFERENCES bc_teams (id),
    FOREIGN KEY(user_id) REFERENCES bc_users (id),
    UNIQUE (team_id, user_id)
);

CREATE INDEX ix_bc_team_requests_team_id ON bc_team_requests (team_id);

CREATE INDEX ix_bc_team_requests_user_id ON bc_team_requests (user_id);

CREATE TABLE bc_interviews (
    application_id VARCHAR(36) NOT NULL,
    starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
    location VARCHAR(200) NOT NULL,
    meeting_url VARCHAR(500),
    instructions TEXT NOT NULL,
    cancelled BOOLEAN NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(application_id) REFERENCES bc_applications (id),
    UNIQUE (application_id)
);

INSERT INTO bc_alembic_version (version_num) VALUES ('e887dc2f39f3') RETURNING bc_alembic_version.version_num;

-- Running upgrade e887dc2f39f3 -> 3e0efcbd6df3

CREATE TABLE bc_follows (
    club_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(club_id) REFERENCES bc_clubs (id),
    FOREIGN KEY(user_id) REFERENCES bc_users (id),
    UNIQUE (club_id, user_id)
);

CREATE INDEX ix_bc_follows_club_id ON bc_follows (club_id);

CREATE INDEX ix_bc_follows_user_id ON bc_follows (user_id);

CREATE TABLE bc_saved_projects (
    project_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(project_id) REFERENCES bc_projects (id),
    FOREIGN KEY(user_id) REFERENCES bc_users (id),
    UNIQUE (project_id, user_id)
);

CREATE INDEX ix_bc_saved_projects_project_id ON bc_saved_projects (project_id);

CREATE INDEX ix_bc_saved_projects_user_id ON bc_saved_projects (user_id);

UPDATE bc_alembic_version SET version_num='3e0efcbd6df3' WHERE bc_alembic_version.version_num = 'e887dc2f39f3';

-- Running upgrade 3e0efcbd6df3 -> dcd6babc803a

ALTER TABLE bc_projects ADD COLUMN category VARCHAR(80) DEFAULT 'Other' NOT NULL;

ALTER TABLE bc_teams ADD COLUMN kind VARCHAR(30) DEFAULT 'Project' NOT NULL;

UPDATE bc_alembic_version SET version_num='dcd6babc803a' WHERE bc_alembic_version.version_num = '3e0efcbd6df3';

-- Running upgrade dcd6babc803a -> b81c7ad48d12

CREATE TABLE bc_cover_images (
    content BYTEA NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE bc_email_otps (
    email VARCHAR(254) NOT NULL,
    code_hash VARCHAR(255) NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    attempts INTEGER NOT NULL,
    PRIMARY KEY (email)
);

CREATE TABLE bc_coordinator_requests (
    club_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    CHECK (status IN ('pending','accepted','declined')),
    FOREIGN KEY(club_id) REFERENCES bc_clubs (id),
    FOREIGN KEY(user_id) REFERENCES bc_users (id),
    UNIQUE (club_id, user_id)
);

CREATE INDEX ix_bc_coordinator_requests_club_id ON bc_coordinator_requests (club_id);

CREATE INDEX ix_bc_coordinator_requests_user_id ON bc_coordinator_requests (user_id);

ALTER TABLE bc_clubs ADD COLUMN cover_url VARCHAR(100);

ALTER TABLE bc_users ADD COLUMN cover_url VARCHAR(100);

UPDATE bc_alembic_version SET version_num='b81c7ad48d12' WHERE bc_alembic_version.version_num = 'dcd6babc803a';

-- Running upgrade b81c7ad48d12 -> 738630c7b772

CREATE TABLE bc_google_challenges (
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    attempts INTEGER NOT NULL,
    PRIMARY KEY (token_hash)
);

CREATE TABLE bc_storage_deletions (
    storage_backend VARCHAR(20) NOT NULL,
    storage_key VARCHAR(100) NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE bc_password_resets (
    user_id VARCHAR(36) NOT NULL,
    token_hash VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used BOOLEAN NOT NULL,
    id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES bc_users (id),
    UNIQUE (token_hash)
);

CREATE INDEX ix_bc_password_resets_user_id ON bc_password_resets (user_id);

ALTER TABLE bc_cover_images ADD COLUMN storage_backend VARCHAR(20) DEFAULT 'database' NOT NULL;

ALTER TABLE bc_cover_images ADD COLUMN storage_key VARCHAR(100);

ALTER TABLE bc_cover_images ADD COLUMN size_bytes INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE bc_cover_images ALTER COLUMN content DROP NOT NULL;

ALTER TABLE bc_users ADD COLUMN google_sub VARCHAR(255);

CREATE UNIQUE INDEX ix_bc_users_google_sub ON bc_users (google_sub);

UPDATE bc_alembic_version SET version_num='738630c7b772' WHERE bc_alembic_version.version_num = 'b81c7ad48d12';

COMMIT;

