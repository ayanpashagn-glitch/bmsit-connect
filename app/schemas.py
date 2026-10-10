from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, EmailStr, HttpUrl, AwareDatetime, field_validator, StringConstraints

Short = Annotated[str, Field(min_length=1, max_length=100)]
Text = Annotated[str, Field(min_length=1, max_length=5000)]
class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
class Signup(Input):
    otp: Annotated[str, Field(pattern=r"^\d{6}$")]
    email: EmailStr
    usn: Annotated[str, Field(min_length=3, max_length=32)]
    name: Short
    password: Annotated[str, StringConstraints(strip_whitespace=False), Field(min_length=12, max_length=128)]
class Login(Input):
    email: EmailStr
    password: Annotated[str, StringConstraints(strip_whitespace=False), Field(min_length=1, max_length=128)]
class Profile(Input):
    name: Short
    branch: Short
    year: int = Field(ge=1, le=6)
    skills: str = Field(default='', max_length=500)
    bio: str = Field(default='', max_length=3000)
    github: HttpUrl | None = None
class UserAccess(Input):
    approved: bool
    active: bool
class ClubInput(Input):
    name: Short
    description: Text
    category: Short
class MemberInput(Input):
    role: Literal['member','coordinator']
class RecruitmentInput(Input):
    title: Short
    role: Short
    description: Text
    deadline: AwareDatetime
class OpenInput(Input):
    open: bool
class MessageInput(Input):
    message: Text
class Decision(Input):
    status: Literal['shortlisted','selected','rejected']
    private_notes: str = Field(default='', max_length=5000)
class InterviewInput(Input):
    starts_at: AwareDatetime
    location: Annotated[str, Field(min_length=1, max_length=200)]
    meeting_url: HttpUrl | None = None
    instructions: str = Field(default='', max_length=3000)
class EventInput(Input):
    title: Short
    description: Text
    kind: Short
    starts_at: AwareDatetime
    venue: Annotated[str, Field(min_length=1, max_length=200)]
    capacity: int = Field(ge=1, le=10000)
class Moderation(Input):
    status: Literal['approved','hidden']
class AnnouncementInput(Input):
    title: Short
    body: Text
class ProjectInput(Input):
    category: Short = "Other"
    title: Short
    description: Text
    skills: str = Field(max_length=500)
    link: HttpUrl | None = None
class Visibility(Input):
    visible: bool
class TeamInput(Input):
    kind: Literal["Project", "Hackathon"] = "Project"
    title: Short
    description: Text
    skills: str = Field(max_length=500)
    commitment: Annotated[str, Field(min_length=1, max_length=200)]
class RequestDecision(Input):
    status: Literal['accepted','declined']

class OTPInput(Input):
    email: EmailStr
class CoverInput(Input):
    image: str = Field(max_length=2800000)

class GoogleLogin(Input):
    credential: str = Field(min_length=1,max_length=16000)
    name: str = Field(default='',max_length=100)
    usn: str = Field(default='',max_length=32)
    existing_password: Annotated[str, StringConstraints(strip_whitespace=False), Field(max_length=128)] = ''
class ResetPasswordInput(Input):
    token: str = Field(min_length=32,max_length=128)
    password: Annotated[str, StringConstraints(strip_whitespace=False), Field(min_length=12,max_length=128)]
