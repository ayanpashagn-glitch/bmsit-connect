from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def now():
    return datetime.now(timezone.utc)

def uid():
    return str(uuid4())

class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class User(Record, Base):
    __tablename__ = 'bc_users'
    email: Mapped[str] = mapped_column(String(254), unique=True)
    usn: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    admin: Mapped[bool] = mapped_column(Boolean, default=False)
    branch: Mapped[str] = mapped_column(String(100), default='')
    year: Mapped[int] = mapped_column(Integer, default=1)
    skills: Mapped[str] = mapped_column(String(500), default='')
    bio: Mapped[str] = mapped_column(Text, default='')
    github: Mapped[str | None] = mapped_column(String(500))
    cover_url: Mapped[str | None] = mapped_column(String(100))

class LoginSession(Base):
    __tablename__ = 'bc_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Club(Record, Base):
    cover_url: Mapped[str | None] = mapped_column(String(100))
    __tablename__ = 'bc_clubs'
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Membership(Record, Base):
    __tablename__ = 'bc_memberships'
    __table_args__ = (UniqueConstraint('club_id','user_id'), CheckConstraint("role IN ('member','coordinator')"))
    club_id: Mapped[str] = mapped_column(ForeignKey('bc_clubs.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)
    role: Mapped[str] = mapped_column(String(20), default='member')

class Recruitment(Record, Base):
    __tablename__ = 'bc_recruitments'
    club_id: Mapped[str] = mapped_column(ForeignKey('bc_clubs.id'), index=True)
    title: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open: Mapped[bool] = mapped_column(Boolean, default=True)

class Application(Record, Base):
    __tablename__ = 'bc_applications'
    __table_args__ = (UniqueConstraint('recruitment_id','user_id'), CheckConstraint("status IN ('submitted','shortlisted','interview','selected','rejected','withdrawn')"))
    recruitment_id: Mapped[str] = mapped_column(ForeignKey('bc_recruitments.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='submitted')
    private_notes: Mapped[str] = mapped_column(Text, default='')

class Interview(Record, Base):
    __tablename__ = 'bc_interviews'
    application_id: Mapped[str] = mapped_column(ForeignKey('bc_applications.id'), unique=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(200))
    meeting_url: Mapped[str | None] = mapped_column(String(500))
    instructions: Mapped[str] = mapped_column(Text, default='')
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)

class Notification(Record, Base):
    __tablename__ = 'bc_notifications'
    user_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)
    message: Mapped[str] = mapped_column(Text)
    resource_id: Mapped[str] = mapped_column(String(36))
    read: Mapped[bool] = mapped_column(Boolean, default=False)

class Event(Record, Base):
    __tablename__ = 'bc_events'
    __table_args__ = (CheckConstraint('capacity > 0'), CheckConstraint("status IN ('pending','approved','hidden')"))
    club_id: Mapped[str] = mapped_column(ForeignKey('bc_clubs.id'), index=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(80))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    venue: Mapped[str] = mapped_column(String(200))
    capacity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='pending')

class Registration(Record, Base):
    __tablename__ = 'bc_registrations'
    __table_args__ = (UniqueConstraint('event_id','user_id'),)
    event_id: Mapped[str] = mapped_column(ForeignKey('bc_events.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)

class Announcement(Record, Base):
    __tablename__ = 'bc_announcements'
    club_id: Mapped[str] = mapped_column(ForeignKey('bc_clubs.id'), index=True)
    title: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(Text)

class Project(Record, Base):
    __tablename__ = 'bc_projects'
    category: Mapped[str] = mapped_column(String(80), default='Other', server_default='Other')
    owner_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    skills: Mapped[str] = mapped_column(String(500))
    link: Mapped[str | None] = mapped_column(String(500))
    visible: Mapped[bool] = mapped_column(Boolean, default=True)

class Team(Record, Base):
    __tablename__ = 'bc_teams'
    kind: Mapped[str] = mapped_column(String(30), default='Project', server_default='Project')
    owner_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    skills: Mapped[str] = mapped_column(String(500))
    commitment: Mapped[str] = mapped_column(String(200))
    open: Mapped[bool] = mapped_column(Boolean, default=True)

class TeamRequest(Record, Base):
    __tablename__ = 'bc_team_requests'
    __table_args__ = (UniqueConstraint('team_id','user_id'), CheckConstraint("status IN ('pending','accepted','declined')"))
    team_id: Mapped[str] = mapped_column(ForeignKey('bc_teams.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='pending')

class TeamMember(Record, Base):
    __tablename__ = 'bc_team_members'
    __table_args__ = (UniqueConstraint('team_id','user_id'),)
    team_id: Mapped[str] = mapped_column(ForeignKey('bc_teams.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)

class Audit(Record, Base):
    __tablename__ = 'bc_audit'
    actor_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)
    action: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(36))

class Follow(Record, Base):
    __tablename__ = 'bc_follows'
    __table_args__ = (UniqueConstraint('club_id','user_id'),)
    club_id: Mapped[str] = mapped_column(ForeignKey('bc_clubs.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)

class SavedProject(Record, Base):
    __tablename__ = 'bc_saved_projects'
    __table_args__ = (UniqueConstraint('project_id','user_id'),)
    project_id: Mapped[str] = mapped_column(ForeignKey('bc_projects.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)

class EmailOTP(Base):
    __tablename__ = 'bc_email_otps'
    email: Mapped[str] = mapped_column(String(254), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)

class CoordinatorRequest(Record, Base):
    __tablename__ = 'bc_coordinator_requests'
    __table_args__ = (UniqueConstraint('club_id','user_id'), CheckConstraint("status IN ('pending','accepted','declined')"))
    club_id: Mapped[str] = mapped_column(ForeignKey('bc_clubs.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='pending')

class CoverImage(Record, Base):
    __tablename__ = 'bc_cover_images'
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    storage_backend: Mapped[str] = mapped_column(String(20), default='database', server_default='database')
    storage_key: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default='0')

class GoogleChallenge(Base):
    __tablename__ = 'bc_google_challenges'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)

class PasswordReset(Record, Base):
    __tablename__ = 'bc_password_resets'
    user_id: Mapped[str] = mapped_column(ForeignKey('bc_users.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)

class StorageDeletion(Record, Base):
    __tablename__ = 'bc_storage_deletions'
    storage_backend: Mapped[str] = mapped_column(String(20))
    storage_key: Mapped[str] = mapped_column(String(100))
