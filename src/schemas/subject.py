from pydantic import BaseModel, ConfigDict

from src.schemas.common import BoolField
from src.schemas.user import UserBriefSchema


class SubjectReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    created_by: int | None = None
    is_public: BoolField
    can_edit: BoolField = False


class SubjectStudentReadSchema(UserBriefSchema):
    access_all_topics: BoolField = False
    access_all_tasks: BoolField = False


class TopicReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    created_by: int | None = None
    subject_id: int | None = None
    is_public: BoolField


class TopicStudentReadSchema(UserBriefSchema):
    access_all_tasks: BoolField = False
